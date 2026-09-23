#!/usr/bin/env python3
"""Bounded root-owned Sway scene diagnostic, never the normal shell session.

Run on the reserved board after importing the opt-in compositor and a trusted
Wayland probe. This replaces the active shell temporarily; no device permission
or persistent unit is changed. A watchdog is armed before shell replacement.
"""
import argparse
import grp
import json
import os
from pathlib import Path
import pwd
import shutil
import signal
import stat
import subprocess
import sys
import time
import uuid

CONFIG = """swaynag_command -
swaybg_command -
xwayland disable
output DSI-1 mode 568x1232 transform normal scale 1 render_bit_depth 6
default_border none
"""


class Commands:
    def run(self, args, *, check=True, timeout=30):
        print("COMMAND " + json.dumps(args), flush=True)
        return subprocess.run(args, check=check, timeout=timeout, text=True)

    def active(self, unit):
        return subprocess.run(["systemctl", "is-active", "--quiet", unit], check=False).returncode == 0

    def wait_active(self, unit, seconds=15):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self.active(unit):
                return True
            time.sleep(0.2)
        return False

    def wait_socket(self, directory, seconds=10):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            for candidate in directory.glob("wayland-*"):
                info = candidate.lstat()
                if stat.S_ISSOCK(info.st_mode) and info.st_uid == 0:
                    return candidate
            time.sleep(0.1)
        raise RuntimeError("diagnostic Wayland socket did not appear")

    def share_socket(self, path, gid):
        info = path.lstat()
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != 0:
            raise RuntimeError("refusing to share an unexpected socket")
        # Only this root-created Wayland socket is shared. Never /dev/vg_lite,
        # the root runtime directory's control subdirectory, or Sway IPC.
        os.chown(path, 0, gid)
        path.chmod(0o660)


def trusted_program(value):
    path = Path(value).resolve(strict=True)
    info = path.stat()
    if not str(path).startswith("/nix/store/") or info.st_uid != 0 or not stat.S_ISREG(info.st_mode) or info.st_mode & 0o022 or not os.access(path, os.X_OK):
        raise ValueError("program must be an executable root-owned Nix store path")
    return str(path)


class Trial:
    def __init__(self, directory, compositor, client, seconds, shell_gid, commands=None, token=None):
        self.directory = Path(directory)
        self.control = self.directory / "control"
        self.display = self.directory / "display"
        self.compositor = compositor
        self.client = client
        self.seconds = seconds
        self.shell_gid = shell_gid
        self.commands = commands or Commands()
        suffix = token or uuid.uuid4().hex[:12]
        if not suffix.isalnum():
            raise ValueError("invalid unit suffix")
        self.unit = "k230-vglite-scene-" + suffix
        self.client_unit = "k230-vglite-client-" + suffix
        self.watchdog = "k230-vglite-recovery-" + suffix
        self.python = sys.executable
        self.restored = False

    def prepare(self):
        self.directory.mkdir(mode=0o711)
        self.control.mkdir(mode=0o700)
        self.display.mkdir(mode=0o711)
        self.directory.chmod(0o711)
        self.display.chmod(0o711)
        (self.control / "sway.conf").write_text(CONFIG)
        (self.control / "sway.conf").chmod(0o600)
        # Fixed unit names are generated above, never supplied as shell text.
        # ExecStopPost queues shell restart: blocking there would deadlock on
        # Conflicts/After until the compositor's stop job itself completes.
        recovery = f'''import subprocess, sys
if len(sys.argv) > 1 and sys.argv[1] == "watchdog":
    try:
        subprocess.run(["systemctl", "stop", {self.client_unit + '.service'!r}, {self.unit + '.service'!r}], check=False, timeout=20)
    finally:
        subprocess.run(["systemctl", "start", "shell.service"], check=True, timeout=30)
else:
    try:
        subprocess.run(["systemctl", "stop", {self.client_unit + '.service'!r}], check=False, timeout=10)
    finally:
        subprocess.run(["systemctl", "--no-block", "start", "shell.service"], check=True, timeout=10)
'''
        (self.control / "recover.py").write_text(recovery)
        (self.control / "recover.py").chmod(0o600)

    def watchdog_command(self):
        return ["systemd-run", "--unit=" + self.watchdog, "--collect",
                "--on-active=" + str(self.seconds + 30) + "s", "--timer-property=AccuracySec=1s",
                "--property=Type=exec", self.python, str(self.control / "recover.py"), "watchdog"]

    def compositor_command(self):
        return ["systemd-run", "--unit=" + self.unit, "--collect", "--service-type=exec",
                "--property=User=root", "--property=Group=root", "--property=UMask=0077",
                "--property=Conflicts=shell.service", "--property=After=shell.service seatd.service",
                "--property=Requires=seatd.service", "--property=KillMode=control-group",
                "--property=TimeoutStopSec=5s", "--property=RuntimeMaxSec=" + str(self.seconds + 15) + "s",
                "--property=NoNewPrivileges=yes", "--property=CapabilityBoundingSet=",
                "--property=ExecStopPost=" + self.python + " " + str(self.control / "recover.py"),
                "--setenv=HOME=" + str(self.control), "--setenv=XDG_RUNTIME_DIR=" + str(self.display),
                "--setenv=SWAYSOCK=" + str(self.control / "sway-ipc.sock"),
                "--setenv=WLR_BACKENDS=drm", "--setenv=LIBSEAT_BACKEND=seatd", "--setenv=XDG_SEAT=seat0",
                "--setenv=WLR_RENDERER=vglite", "--setenv=K230_VGLITE_ALLOW_UNPROVEN_CACHE=1",
                self.compositor, "-d", "-c", str(self.control / "sway.conf")]

    def client_command(self, wayland_socket):
        return ["systemd-run", "--unit=" + self.client_unit, "--collect", "--wait", "--pipe", "--service-type=exec",
                "--property=User=shell", "--property=Group=shell", "--property=UMask=0077",
                "--property=NoNewPrivileges=yes", "--property=CapabilityBoundingSet=", "--property=AmbientCapabilities=",
                "--property=PrivateDevices=yes", "--property=PrivateTmp=yes", "--property=KillMode=control-group",
                "--property=RuntimeDirectory=" + self.client_unit, "--property=RuntimeDirectoryMode=0700",
                "--property=RuntimeMaxSec=" + str(self.seconds) + "s", "--property=TimeoutStopSec=3s",
                "--property=UnsetEnvironment=SWAYSOCK WLR_RENDERER K230_VGLITE_ALLOW_UNPROVEN_CACHE DBUS_SESSION_BUS_ADDRESS DISPLAY XAUTHORITY WAYLAND_SOCKET",
                "--setenv=XDG_RUNTIME_DIR=/run/" + self.client_unit,
                "--setenv=WAYLAND_DISPLAY=" + str(wayland_socket), "--", *self.client]

    def run(self):
        if not self.commands.active("shell.service"):
            raise RuntimeError("normal shell must be active before a diagnostic replacement")
        self.prepare()
        armed = False
        try:
            # Arm first. If this controller is SIGKILLed, systemd still owns the
            # runtime limit, compositor cgroup, ExecStopPost and recovery timer.
            self.commands.run(self.watchdog_command())
            armed = True
            self.commands.run(self.compositor_command())
            wayland_socket = self.commands.wait_socket(self.display)
            self.commands.share_socket(wayland_socket, self.shell_gid)
            self.commands.run(self.client_command(wayland_socket), timeout=self.seconds + 10)
        finally:
            if armed:
                # systemd stop waits for the entire compositor cgroup, not only
                # its leader; only then can normal Sway regain DRM ownership.
                for command, timeout in [
                    (["systemctl", "stop", self.client_unit + ".service", self.unit + ".service"], 20),
                    (["systemctl", "start", "shell.service"], 30),
                ]:
                    try:
                        self.commands.run(command, check=False, timeout=timeout)
                    except (OSError, subprocess.SubprocessError) as error:
                        print("Recovery command failed: " + str(error), file=sys.stderr)
                self.restored = (self.commands.wait_active("shell.service")
                                 and not self.commands.active(self.unit + ".service")
                                 and not self.commands.active(self.client_unit + ".service"))
                try:
                    self.commands.run(["journalctl", "--no-pager", "-o", "short-iso", "-u", self.unit + ".service"], check=False)
                except (OSError, subprocess.SubprocessError) as error:
                    print("Journal capture failed: " + str(error), file=sys.stderr)
            else:
                self.restored = self.commands.active("shell.service")
            if self.restored:
                self.commands.run(["systemctl", "stop", self.watchdog + ".timer"], check=False)
                shutil.rmtree(self.directory)
                print("RESTORED shell.service active; diagnostic compositor cgroup stopped", flush=True)
            else:
                print("RESTORATION FAILED; recovery timer and root-owned files retained at " + str(self.directory), file=sys.stderr)
        if not self.restored:
            raise RuntimeError("normal shell restoration requires operator recovery")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compositor", required=True, help="imported opt-in Sway executable in /nix/store")
    parser.add_argument("--seconds", type=int, default=20, help="client maximum lifetime, 1–120 seconds")
    parser.add_argument("client", nargs=argparse.REMAINDER, help="-- followed by trusted Wayland probe and arguments")
    args = parser.parse_args()
    client = args.client[1:] if args.client[:1] == ["--"] else args.client
    if os.geteuid() != 0 or not 1 <= args.seconds <= 120 or not client:
        parser.error("requires board operator root, 1–120 seconds, and a client command")
    account = pwd.getpwnam("shell")
    shell_gid = grp.getgrnam("shell").gr_gid
    if account.pw_uid == 0 or shell_gid == 0:
        parser.error("shell client must have non-root UID and GID")
    compositor = trusted_program(args.compositor)
    client[0] = trusted_program(client[0])
    # The interrupted controller unwinds normally; SIGKILL is handled by the
    # already-armed recovery timer and service stop hooks instead.
    def interrupted(signum, _frame):
        raise RuntimeError("diagnostic interrupted by signal " + str(signum))
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    directory = Path("/run") / ("k230-vglite-trial-" + uuid.uuid4().hex[:12])
    Trial(directory, compositor, client, args.seconds, shell_gid).run()


if __name__ == "__main__":
    main()
