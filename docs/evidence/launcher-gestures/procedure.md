# Injected gesture acceptance procedure

Run this only with the board operator holding the serial and graphical-session reservation. It is a board-local helper: it uses the existing `tools/inject-tap.sh` virtual touchscreen and captures native Wayland PNGs with `grim`.

The helper alternates 20 left and 20 right drags from the Apps card region, waiting at least 250 ms after every drag. It captures an explicitly shown keyboard, explicitly hides it before overview/Back, counts current windows through a read-only command, opens the overview with an upward drag, and taps its Back control. It writes `acceptance.json`, native PNGs, copied metrics if supplied, and optional `/proc/<launcher-pid>` memory snapshots.

The persistent bar controls `wvkbd-mobintl` with:

```sh
pkill -RTMIN -x wvkbd-mobintl
```

That signal is a toggle. The pinned wvkbd `main.c` signal handlers also define `SIGUSR2` as show and `SIGUSR1` as hide; use those explicit commands in automated runs. The helper deliberately has no default show/hide command.

Copy this helper and `tools/inject-tap.sh` into `/run` first. The interpreter and
metadata helper are closure dependencies referenced by the installed wrappers;
they need not have their own system-profile symlinks.

```sh
K230_TEST_PYTHON=$(sed -n 's/^exec \([^ ]*\/python3\) .*/\1/p' /run/current-system/sw/bin/k230-video-session)
K230_TEST_WINDOW_CATALOG=$(sed -n 's/^export K230_WINDOW_CATALOG=//p' /run/current-system/sw/bin/k230-touch-launcher)
"$K230_TEST_PYTHON" /run/gesture-acceptance.py --execute \
  --device /dev/input/eventN \
  --inject-script /path/to/inject-tap.sh \
  --keyboard-show-command 'pkill -USR2 -x wvkbd-mobintl' \
  --keyboard-hide-command 'pkill -USR1 -x wvkbd-mobintl' \
  --window-catalog-command "$K230_TEST_WINDOW_CATALOG" \
  --launcher-pid "$(pidof k230-touch-launcher)" \
  --metrics-file /run/shell/launcher-metrics.txt \
  --output-dir docs/evidence/launcher-gestures/UTC-run
```

The execution mode refuses a catalog with fewer than two rows, so an empty or single-card overview is not accepted as a multi-card result. It retains only that row count: do not save or publish raw window titles or the catalog command output.

Start the native launcher with `K230_LAUNCHER_METRICS=/run/shell/launcher-metrics.txt` before the run. The fields distinguish **wall-clock** render and release-to-submit intervals from `CLOCK_PROCESS_CPUTIME_ID` CPU time since release. They also record transient snapshot bytes, live Wayland buffer count, direction, page and overview mode. These do not measure display scanout or physical presentation. Check settled page/direction records against all 40 requested swipes before claiming no missed or duplicate transition; the helper records requested actions, not that acceptance verdict.

The default is plan-only: it writes a plan but makes no board, uinput, `grim`, or physical-touch claim. `--self-test` is a host-only mocked subprocess check of action order, the 42 injected drags, settle waits, and before/after resource snapshots.

This is injected-touch evidence only. A separate real-finger camera trial must show left/right paging, overview entry/exit, a card tap, and Back before the physical-glass task can close. Do not tick any hardware task from this procedure alone.
