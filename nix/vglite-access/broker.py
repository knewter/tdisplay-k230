#!/usr/bin/env python3
"""Give the private VG-Lite descriptor only to one systemd compositor MainPID.

Socket-activated, fixed policy from root-owned unit arguments. No ioctl proxy,
user-supplied paths, or UID-wide authorization. Missing checks deny access.
"""
import argparse
import array
import os
from pathlib import Path
import pwd
import select
import socket
import stat
import struct
import subprocess
import sys

SO_PEERPIDFD = 77  # Linux 6.5+, present in the pinned K230 6.6 UAPI.


class Denied(Exception):
    pass


class Policy:
    def __init__(self, unit, executable, uid):
        if not unit.endswith(".service") or "/" in unit or uid == 0:
            raise ValueError("expected a fixed system service and non-root compositor UID")
        self.unit, self.executable, self.uid = unit, str(Path(executable).resolve()), uid
        self.granted_pidfd = None

    def main_pid(self):
        result = subprocess.run(["systemctl", "show", self.unit, "--property=MainPID", "--value"],
                                check=True, capture_output=True, text=True, timeout=2)
        return int(result.stdout.strip())

    def process(self, pid):
        proc = Path("/proc") / str(pid)
        status = dict(line.split(":", 1) for line in (proc / "status").read_text().splitlines() if ":" in line)
        return {
            "uids": [int(x) for x in status["Uid"].split()],
            "parent": int(status["PPid"]), "tracer": int(status["TracerPid"]),
            "executable": os.readlink(proc / "exe"),
            # proc inode ownership switches to root for non-dumpable tasks.
            # This is checked in addition to the expected non-root real UID.
            "fd_owner": (proc / "fd").stat().st_uid,
        }

    def ptrace_scope(self):
        return int(Path("/proc/sys/kernel/yama/ptrace_scope").read_text().strip())

    def authorize(self, pid, uid, pidfd):
        if self.granted_pidfd is not None:
            if alive(self.granted_pidfd):
                raise Denied("device already granted to a live compositor")
            os.close(self.granted_pidfd)
            self.granted_pidfd = None
        if uid != self.uid or not alive(pidfd):
            raise Denied("wrong UID or expired socket peer")
        # A non-dumpable request alone leaves an earlier startup ptrace window.
        # Yama blocks sibling clients before prctl; parent PID 1 rules out an
        # app launching this same executable as its own traceable descendant.
        if self.ptrace_scope() not in (1, 2, 3):
            raise Denied("Yama startup protection unavailable")
        if pid != self.main_pid():
            raise Denied("peer is not compositor MainPID")
        process = self.process(pid)
        if process != {"uids": [self.uid] * 4, "parent": 1, "tracer": 0,
                       "executable": self.executable, "fd_owner": 0}:
            raise Denied("compositor executable, credentials or non-dumpability mismatch")
        if not alive(pidfd) or pid != self.main_pid():
            raise Denied("compositor changed during authorization")


def alive(pidfd):
    poll = select.poll()
    poll.register(pidfd, select.POLLIN | select.POLLHUP | select.POLLERR)
    return not poll.poll(0)


def open_device():
    fd = os.open("/dev/vg_lite", os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW)
    info = os.fstat(fd)
    if not stat.S_ISCHR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o066:
        os.close(fd)
        raise Denied("VG-Lite device must already be root-owned and private")
    return fd


def serve_connection(connection, policy, device_opener=open_device):
    device = pidfd = -1
    try:
        connection.settimeout(3)
        pid, uid, _ = struct.unpack("3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        if uid != policy.uid:
            raise Denied("wrong peer UID")
        # Unlike pidfd_open(peer_pid), this binds to the original socket peer
        # even if a socket is passed to another process and its creator exits.
        pidfd = struct.unpack("i", connection.getsockopt(socket.SOL_SOCKET, SO_PEERPIDFD, 4))[0]
        os.set_inheritable(pidfd, False)
        if connection.recv(4, socket.MSG_WAITALL) != b"VG1\n":
            raise Denied("invalid request")
        policy.authorize(pid, uid, pidfd)
        device = device_opener()
        policy.granted_pidfd = os.dup(pidfd)
        if not alive(pidfd):
            raise Denied("compositor exited before grant")
        if connection.sendmsg([b"G"], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array("i", [device]))]) != 1:
            raise Denied("descriptor reply failed")
        print("VG-Lite descriptor granted to compositor MainPID", pid, flush=True)
        return True
    except (Denied, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print("VG-Lite descriptor denied:", type(error).__name__, str(error), file=sys.stderr, flush=True)
        return False
    finally:
        if device >= 0:
            os.close(device)
        if pidfd >= 0:
            os.close(pidfd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit", required=True)
    parser.add_argument("--executable", required=True)
    parser.add_argument("--user", default="shell")
    args = parser.parse_args()
    if os.geteuid() != 0 or os.environ.get("LISTEN_PID") != str(os.getpid()) or os.environ.get("LISTEN_FDS") != "1":
        parser.error("requires root and exactly one systemd activation socket")
    policy = Policy(args.unit, args.executable, pwd.getpwnam(args.user).pw_uid)
    listener = socket.socket(fileno=3)
    listener.set_inheritable(False)
    if listener.family != socket.AF_UNIX or listener.type != socket.SOCK_STREAM:
        parser.error("requires a Unix stream activation socket")
    while True:
        connection, _ = listener.accept()
        with connection:
            serve_connection(connection, policy)


if __name__ == "__main__":
    main()
