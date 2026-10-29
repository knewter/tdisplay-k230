#!/usr/bin/env python3
"""files_idle.py: wait for Files (comm .nautilus-wrapp) to start, then sample its
main thread's CPU ticks every 2 s until two consecutive samples add < 3 ticks
or 300 s pass. Times are from the moment the process is first seen."""
import os, time
def find():
    for p in os.listdir('/proc'):
        if p.isdigit():
            try:
                if open(f'/proc/{p}/comm').read().strip() == '.nautilus-wrapp': return int(p)
            except OSError: pass
start = time.time()
while (pid := find()) is None:
    if time.time() - start > 120: print('NO FILES PROCESS'); raise SystemExit(1)
    time.sleep(0.5)
t0 = time.time(); print(f'SEEN pid={pid} after {t0-start:.1f}s of waiting', flush=True)
def ticks():
    f = open(f'/proc/{pid}/task/{pid}/stat').read().rsplit(')', 1)[1].split()
    return int(f[11]) + int(f[12])
prev, quiet = ticks(), 0
while time.time() - t0 < 300:
    time.sleep(2); now = ticks(); d = now - prev; prev = now
    print(f't={time.time()-t0:.1f} dticks={d} total={now}', flush=True)
    quiet = quiet + 1 if d < 3 else 0
    if quiet == 2: print(f'IDLE by t={time.time()-t0-2:.1f} main_ticks={now}'); break
else: print('STILL BUSY at 300 s')
