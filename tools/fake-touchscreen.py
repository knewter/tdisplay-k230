# Fake Goodix touchscreen (protocol B) for driving a second k230-touch-trackpad
# instance. Usage: fake-touchscreen.py REAL_EVENT_DEV 'script'
#   wait MS | tap X Y [MS] | tap2 X Y [MS] | swipe2 X1 Y1 X2 Y2 MS | hold2 X Y MS
# Coordinates are fractions 0..1 of the panel's raw X/Y ranges.
import fcntl, os, struct, sys, time
EV_SYN, EV_KEY, EV_ABS = 0, 1, 3
BTN_TOUCH = 0x14a
ABS_X, ABS_Y = 0, 1
SLOT, MAJOR, PX, PY, TID = 0x2f, 0x30, 0x35, 0x36, 0x39
AXES = [ABS_X, ABS_Y, SLOT, MAJOR, PX, PY, TID]
def absinfo(fd, axis):
    buf = bytearray(24)
    fcntl.ioctl(fd, 0x80184540 + axis, buf)
    return struct.unpack("6i", buf)  # value min max fuzz flat res
real = os.open(sys.argv[1], os.O_RDONLY)
info = {a: absinfo(real, a) for a in AXES}
os.close(real)
fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
for bit in (EV_SYN, EV_KEY, EV_ABS): fcntl.ioctl(fd, 0x40045564, bit)
fcntl.ioctl(fd, 0x40045565, BTN_TOUCH)
for a in AXES: fcntl.ioctl(fd, 0x40045567, a)
fcntl.ioctl(fd, 0x4004556e, 1)  # INPUT_PROP_DIRECT
mx, mn = [0]*64, [0]*64
for a, i in info.items(): mn[a], mx[a] = i[1], i[2]
dev = struct.pack("80sHHHHi", b"Fake Goodix TouchScreen", 0x18, 0, 0, 0, 0)
dev += struct.pack("64i", *mx) + struct.pack("64i", *mn) + struct.pack("64i", *[0]*64) * 2
os.write(fd, dev); fcntl.ioctl(fd, 0x5501)
print("fake ranges", {hex(a): info[a][1:3] for a in AXES}, flush=True)
print("FAKE_READY", flush=True)
def emit(t, c, v):
    now = time.time(); s = int(now)
    os.write(fd, struct.pack("llHHi", s, int((now - s) * 1e6), t, c, v))
def syn(): emit(EV_SYN, 0, 0)
tid = [100]
def raw(ax, f): lo, hi = info[ax][1], info[ax][2]; return int(lo + f * (hi - lo))
def contacts_down(pts):
    for i, (x, y) in enumerate(pts):
        tid[0] += 1
        emit(EV_ABS, SLOT, i); emit(EV_ABS, TID, tid[0]); emit(EV_ABS, MAJOR, 20)
        emit(EV_ABS, PX, raw(PX, x)); emit(EV_ABS, PY, raw(PY, y))
    emit(EV_KEY, BTN_TOUCH, 1); emit(EV_ABS, ABS_X, raw(ABS_X, pts[0][0])); emit(EV_ABS, ABS_Y, raw(ABS_Y, pts[0][1])); syn()
def contacts_move(pts):
    for i, (x, y) in enumerate(pts):
        emit(EV_ABS, SLOT, i); emit(EV_ABS, PX, raw(PX, x)); emit(EV_ABS, PY, raw(PY, y))
    emit(EV_ABS, ABS_X, raw(ABS_X, pts[0][0])); emit(EV_ABS, ABS_Y, raw(ABS_Y, pts[0][1])); syn()
def contacts_up(n):
    for i in range(n): emit(EV_ABS, SLOT, i); emit(EV_ABS, TID, -1)
    emit(EV_KEY, BTN_TOUCH, 0); syn()
def pair(x, y): return [(x - 0.06, y), (x + 0.06, y)]
time.sleep(3.0)
for step in sys.argv[2].split(";"):
    w = step.split()
    if not w: continue
    print("step", step.strip(), flush=True)
    if w[0] == "wait": time.sleep(int(w[1]) / 1000)
    elif w[0] in ("tap", "tap2"):
        x, y = float(w[1]), float(w[2]); ms = int(w[3]) if len(w) > 3 else 80
        pts = [(x, y)] if w[0] == "tap" else pair(x, y)
        contacts_down(pts); t = time.time()
        while time.time() - t < ms / 1000: time.sleep(0.012); contacts_move(pts)
        contacts_up(len(pts))
    elif w[0] == "hold2":
        x, y, ms = float(w[1]), float(w[2]), int(w[3]); pts = pair(x, y)
        contacts_down(pts); t = time.time()
        while time.time() - t < ms / 1000: time.sleep(0.012); contacts_move(pts)
        contacts_up(2)
    elif w[0] == "swipe2":
        x1, y1, x2, y2, ms = map(float, w[1:6]); n = max(2, int(ms / 12))
        contacts_down(pair(x1, y1))
        for k in range(1, n + 1):
            time.sleep(ms / 1000 / n); f = k / n
            contacts_move(pair(x1 + (x2 - x1) * f, y1 + (y2 - y1) * f))
        time.sleep(0.03); contacts_up(2)
time.sleep(0.5)
fcntl.ioctl(fd, 0x5502); os.close(fd)
