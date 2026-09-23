#!/usr/bin/env python3
"""Optional privileged HOST test; never opens DRM or VG-Lite.

A real systemd client unit must run as a non-root account, connect only to the
shared Wayland fixture, and fail to reach private IPC, the GPU fixture, or the
root process's fixture descriptor. Requires host root; reports SKIP otherwise.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import pwd
import socket
import struct
import subprocess
import sys
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--user", default="nobody")
args = parser.parse_args()
if os.geteuid() != 0:
    print("SKIP: real systemd multi-UID credential/isolation test requires host root")
    sys.exit(77)
account = pwd.getpwnam(args.user)
assert account.pw_uid != 0 and account.pw_gid != 0
source = Path(__file__).resolve().parents[2] / "tools/vglite-root-scene-trial.py"
spec = importlib.util.spec_from_file_location("trial", source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
with tempfile.TemporaryDirectory(dir="/run") as parent:
    os.chmod(parent, 0o711)
    trial = module.Trial(Path(parent) / "trial", "/unused", [], 10, account.pw_gid)
    trial.prepare()
    gpu = trial.control / "gpu-fixture"
    gpu.write_text("private GPU descriptor fixture")
    gpu.chmod(0o600)
    ipc_path = trial.control / "sway-ipc.sock"
    wayland_path = trial.display / "wayland-1"
    with socket.socket(socket.AF_UNIX) as wayland, socket.socket(socket.AF_UNIX) as ipc, gpu.open() as held:
        wayland.bind(str(wayland_path)); wayland.listen(1); wayland.settimeout(15)
        ipc.bind(str(ipc_path)); ipc.listen(1)
        module.Commands().share_socket(wayland_path, account.pw_gid)
        code = '''import json, os, socket, sys
uid, gid = int(sys.argv[1]), int(sys.argv[2])
assert os.getuid() == uid and os.geteuid() == uid
assert os.getgid() == gid and os.getegid() == gid
assert os.environ.get("SWAYSOCK") is None
for path in sys.argv[4:]:
    try:
        if path.endswith(".sock"):
            s=socket.socket(socket.AF_UNIX); s.connect(path)
        else:
            os.open(path, os.O_RDONLY)
    except PermissionError:
        pass
    else:
        raise AssertionError("private resource accessible: " + path)
status=dict(line.rstrip().split(":",1) for line in open("/proc/self/status") if ":" in line)
assert int(status["NoNewPrivs"].strip()) == 1
assert int(status["CapEff"].strip(),16) == 0
s=socket.socket(socket.AF_UNIX); s.connect(sys.argv[3]); s.send(json.dumps({"uid":os.getuid(),"gid":os.getgid(),"private_resources":"denied","NoNewPrivs":1,"CapEff":0}).encode())
'''
        trial.client = [sys.executable, "-c", code, str(account.pw_uid), str(account.pw_gid), str(wayland_path),
                        str(ipc_path), str(gpu), f"/proc/{os.getpid()}/fd/{held.fileno()}"]
        command = trial.client_command(wayland_path)
        # The production plan is fixed to shell. A root host may not have that
        # account; replace only its identity with this fixture's non-root user.
        command = [f"--property=User={account.pw_uid}" if x == "--property=User=shell" else
                   f"--property=Group={account.pw_gid}" if x == "--property=Group=shell" else x for x in command]
        process = subprocess.Popen(command)
        try:
            connection, _ = wayland.accept()
            with connection:
                _, uid, gid = struct.unpack("3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                assert (uid, gid) == (account.pw_uid, account.pw_gid)
                report = json.loads(connection.recv(4096))
            assert process.wait(timeout=15) == 0
            print("PASS: actual systemd client credentials, capabilities, private IPC/GPU/proc-fd denial, shared Wayland socket", report)
        finally:
            subprocess.run(["systemctl", "stop", trial.client_unit + ".service"], check=False)
