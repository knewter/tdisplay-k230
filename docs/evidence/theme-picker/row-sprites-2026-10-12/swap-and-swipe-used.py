"""Board (root): run shell-ui on a given k230-shell-rust ELF through a /run drop-in (a reboot restores the
installed unit), optionally with counters-only tracing and eight injected theme-row swipes.
usage: swap-and-swipe.py EXE LABEL {measure|leave}. Software input only; no finger."""
import os, pwd, re, struct, subprocess, sys, time
from pathlib import Path
exe, label, mode = sys.argv[1:4]
assert re.fullmatch(r"/nix/store/[a-z0-9]{32}-[^/ \n]+/bin/k230-shell-rust", exe) and Path(exe).exists()
NAME = "K230 injected touchscreen"; UNIT = "k230-row-paint-touch"; DROPIN = Path("/run/systemd/system/shell-ui.service.d/93-row-paint.conf")
SH = ["runuser", "-u", "shell", "--", "env", "XDG_RUNTIME_DIR=/run/shell", "WAYLAND_DISPLAY=wayland-1"]
EVENT = struct.Struct("@llHHi")
def call(a, **k): return subprocess.run(a, check=True, capture_output=True, text=True, **k).stdout
shell = pwd.getpwnam("shell")
root = Path("/run/shell/row-paint"); root.mkdir(mode=0o700, exist_ok=True); os.chown(root, shell.pw_uid, shell.pw_gid)
out = root / label; out.mkdir(mode=0o700, exist_ok=True); os.chown(out, shell.pw_uid, shell.pw_gid)
DROPIN.unlink(missing_ok=True); call(["systemctl", "daemon-reload"])
normal = call(["systemctl", "show", "shell-ui", "-p", "ExecStart", "--value"])
original = Path(re.search(r"path=(/nix/store/[^ ;]+/bin/k230-shell-rust)", normal)[1]).read_text()
text, n = re.subn(r"(?m)^exec /nix/store/[^ ]+/bin/k230-shell-rust", "exec " + exe, original); assert n == 1
wrapper = out / "wrapper"; wrapper.write_text(text); wrapper.chmod(0o555); os.chown(wrapper, shell.pw_uid, shell.pw_gid)
trace = out / "trace.json"; trace.unlink(missing_ok=True)
env = (f"Environment=K230_TRACE_PATH={trace}\nEnvironment=K230_TRACE_SECONDS=55\nEnvironment=K230_TRACE_COUNTERS_ONLY=1\n"
       if mode == "measure" else "")
DROPIN.parent.mkdir(exist_ok=True); DROPIN.write_text("[Service]\n" + env + f"ExecStart=\nExecStart={wrapper} --serve\n")
call(["systemctl", "daemon-reload"]); call(["systemctl", "restart", "shell-ui"], timeout=90); t0 = time.monotonic()
time.sleep(5); assert call(["systemctl", "is-active", "shell-ui"]).strip() == "active"
pid = call(["systemctl", "show", "shell-ui", "-p", "MainPID", "--value"]).strip()
print("RUNNING", Path(f"/proc/{pid}/exe").resolve())
if mode == "leave":
    raise SystemExit(0)
def devices(): return [p.parent.parent.name for p in Path("/sys/class/input").glob("event*/device/name")
                      if p.read_text().strip() == NAME and str(p.resolve()).startswith("/sys/devices/virtual/input/")]
desc = re.sub(r"^N:.*$", "N: " + NAME, call(["evemu-describe", "/dev/input/event1"]), count=1, flags=re.M)
Path("/run/k230-row-paint.desc").write_text(desc)
call(["systemd-run", "--unit=" + UNIT, "--collect", "--property=Type=exec", "--property=RuntimeMaxSec=300s", "evemu-device", "/run/k230-row-paint.desc"])
try:
    for _ in range(100):
        if len(devices()) == 1: break
        time.sleep(0.1)
    fd = os.open("/dev/input/" + devices()[0], os.O_WRONLY); time.sleep(1.5)
    def frame(ev): os.write(fd, b"".join(EVENT.pack(0, 0, *v) for v in [*ev, (0, 0, 0)]))
    def pos(x, y):
        dx, dy = int(x) * 1024 // 568, int(y) * 2400 // 1232
        return [(3, 53, dx), (3, 54, dy), (3, 0, dx), (3, 1, dy)]
    def stroke(x0, x1, y, ms, steps):
        frame([(3, 47, 0), (3, 57, 1), *pos(x0, y), (1, 330, 1)])
        for i in range(1, steps + 1):
            time.sleep(ms / 1000 / steps); frame(pos(x0 + (x1 - x0) * i / steps, y))
        time.sleep(0.01); frame([(3, 57, -1), (1, 330, 0)])
    call(SH + [str(wrapper), "--surface", "settings"], timeout=30); time.sleep(3)
    stroke(480, 480, 130, 80, 1); time.sleep(12)
    if mode == "measure":
        for i in range(8):
            a, b = (430, 190) if i % 2 == 0 else (190, 430)
            stroke(a, b, 430, 200, 20); time.sleep(1.2)
        while not (trace.exists() and trace.stat().st_size > 0) and time.monotonic() - t0 < 90: time.sleep(1)
        print("TRACE bytes", trace.stat().st_size if trace.exists() else 0)
    os.close(fd)
finally:
    subprocess.run(["systemctl", "stop", UNIT], capture_output=True); Path("/run/k230-row-paint.desc").unlink(missing_ok=True)
