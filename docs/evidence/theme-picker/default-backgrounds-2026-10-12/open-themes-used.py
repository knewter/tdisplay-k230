"""Task 19.2 check (board, root): open Settings -> Themes with one injected tap, then capture natively.
Software input through a virtual 'K230 injected touchscreen'; no finger. Leaves no unit or device behind."""
import os, re, struct, subprocess, sys, time
from pathlib import Path
NAME = "K230 injected touchscreen"; UNIT = "k230-bg-check-touch"
SH = ["runuser", "-u", "shell", "--", "env", "XDG_RUNTIME_DIR=/run/shell", "WAYLAND_DISPLAY=wayland-1"]
EVENT = struct.Struct("@llHHi")
def call(a, **k): return subprocess.run(a, check=True, capture_output=True, text=True, **k).stdout
def devices(): return [p.parent.parent.name for p in Path("/sys/class/input").glob("event*/device/name")
                      if p.read_text().strip() == NAME and str(p.resolve()).startswith("/sys/devices/virtual/input/")]
def tap(dev, x, y):
    dx, dy = x * 1024 // 568, y * 2400 // 1232
    fd = os.open(dev, os.O_WRONLY)
    pos = [(3, 53, dx), (3, 54, dy), (3, 0, dx), (3, 1, dy)]
    def frame(ev): os.write(fd, b"".join(EVENT.pack(0, 0, *v) for v in [*ev, (0, 0, 0)]))
    frame([(3, 47, 0), (3, 57, 1), *pos, (1, 330, 1)]); time.sleep(0.08)
    frame([(3, 57, -1), (1, 330, 0)]); os.close(fd)
out = Path(sys.argv[1]); wrapper = sys.argv[2]
desc = re.sub(r"^N:.*$", "N: " + NAME, call(["evemu-describe", "/dev/input/event1"]), count=1, flags=re.M)
Path("/run/k230-bg-check.desc").write_text(desc)
call(["systemd-run", "--unit=" + UNIT, "--collect", "--property=Type=exec", "--property=RuntimeMaxSec=300s", "evemu-device", "/run/k230-bg-check.desc"])
try:
    for _ in range(100):
        if len(devices()) == 1: break
        time.sleep(0.1)
    dev = "/dev/input/" + devices()[0]
    time.sleep(1.5)
    call(SH + [wrapper, "--surface", "settings"], timeout=30); time.sleep(3)
    tap(dev, 480, 130); time.sleep(15)
    call(SH + ["grim", "-s", "0.5", "/run/shell/bg-check.png"])
    out.write_bytes(Path("/run/shell/bg-check.png").read_bytes()); Path("/run/shell/bg-check.png").unlink()
    print("ACTIVE", call(SH + ["k230-theme", "list"]).split('"active"', 1)[1][:80].replace("\n", " "))
finally:
    subprocess.run(["systemctl", "stop", UNIT], capture_output=True); Path("/run/k230-bg-check.desc").unlink(missing_ok=True)
