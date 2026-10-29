"""Launch Files like the drawer does; sample per-thread CPU ticks every 2 s."""
import os, subprocess, sys, time, glob
dur = float(sys.argv[1]) if len(sys.argv) > 1 else 90
env = ["env", "XDG_RUNTIME_DIR=/run/shell", "WAYLAND_DISPLAY=wayland-1",
       "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/shell-bus/bus", "HOME=/home/shell"]
log = open("/var/tmp/files-probe.log", "w")
t0 = time.monotonic()
subprocess.Popen(["sudo", "-u", "shell"] + env + [(sys.argv[2] if len(sys.argv) > 2 else "/nix/store/z39jlc9wcx98wjnprp2c1gbqwdk6chdv-k230-nautilus/bin/k230-nautilus"), "/home/shell"], stdout=log, stderr=log)
pid = None
last = None
quiet = 0
while time.monotonic() - t0 < dur:
    if pid is None:
        out = [d for d in os.listdir("/proc") if d.isdigit() and open(f"/proc/{d}/comm").read().strip() == ".nautilus-wrapp"] if True else []
        if out: pid = out[0]; print(f"t={time.monotonic()-t0:.1f} pid={pid}", flush=True)
    if pid:
        row = []
        for t in sorted(glob.glob(f"/proc/{pid}/task/*")):
            try:
                s = open(t + "/stat").read(); name = s[s.index("(")+1:s.rindex(")")]
                f = s[s.rindex(")")+2:].split()
                row.append(f"{name}:{f[0]}:{int(f[11])+int(f[12])}")
            except OSError: pass
        try: rss = [l for l in open(f"/proc/{pid}/status") if l.startswith("VmRSS")][0].split()[1]
        except OSError: rss = "gone"
        main = int(row[0].split(":")[2]) if row else 0
        print(f"t={time.monotonic()-t0:.1f} rss={rss}k " + " ".join(row[:1]), flush=True)
        if last is not None and main - last < 10:
            quiet += 1
            if quiet >= 2:
                print(f"IDLE at t={time.monotonic()-t0:.1f} main_ticks={main}", flush=True); break
        else:
            quiet = 0
        last = main
    time.sleep(2)
