# PMU power key events on the mainline image (task 1.3), 2026-10-14

Board-read over SSH on the landscape image (`k230-mainline-drm-shell-landscape`,
mainline 7.3.0-rc5 with the ported `k230-pmu-pwrkey` driver). Limit: the
task names a serial `tools/console.py /dev/ttyACM0` read. On this bench
`/dev/ttyACM0` is now a different device, not the K230, so the same reads were
taken over SSH instead.

`/proc/bus/input/devices`:

```
N: Name="K230 PMU Power Key"
P: Phys=k230-pmu-pwrkey/input0
S: Sysfs=/devices/platform/soc/91000000.pmu-pwrkey/input/input0
H: Handlers=kbd event0
```

`shell-power-key.service` was stopped for the window (it grabs the device), and
`evemu-record /dev/input/event0` ran for 180 s while the operator tapped the
key twice:

```
E: 0.000001 0001 0074 0001	# EV_KEY / KEY_POWER            1
E: 0.000001 0000 0000 0000	# ------------ SYN_REPORT (0) ---------- +0ms
E: 0.195543 0001 0074 0000	# EV_KEY / KEY_POWER            0
E: 0.195543 0000 0000 0000	# ------------ SYN_REPORT (0) ---------- +195ms
E: 0.973287 0001 0074 0001	# EV_KEY / KEY_POWER            1
E: 0.973287 0000 0000 0000	# ------------ SYN_REPORT (0) ---------- +778ms
E: 1.133189 0001 0074 0000	# EV_KEY / KEY_POWER            0
E: 1.133189 0000 0000 0000	# ------------ SYN_REPORT (0) ---------- +160ms
```

Window `2026-10-14T16:24:49-05:00` (uptime 7739.26) to `16:27:49` (uptime
7919.31), boot ID `ccd3f704-478b-4eff-b187-1c7bde3ae50f` throughout: each
press has its release, and the system kept running. The service was started
again afterwards.
