# Injected gesture acceptance procedure

Run this only with the board operator holding the serial and graphical-session reservation. It is a board-local helper: it uses the existing `tools/inject-tap.sh` virtual touchscreen and captures native Wayland PNGs with `grim`.

The helper alternates 20 left and 20 right drags from the Apps card region, waiting at least 250 ms after every drag. It captures an explicitly shown keyboard, explicitly hides it before overview/Back, counts current windows through a read-only command, opens the overview with an upward drag, and taps its Back control. It writes `acceptance.json`, native PNGs, copied metrics if supplied, and optional `/proc/<launcher-pid>` memory snapshots.

The persistent bar controls `wvkbd-mobintl` with:

```sh
pkill -RTMIN -x wvkbd-mobintl
```

That signal is a toggle. Inspect the current native screen before each keyboard command and pass explicit `--keyboard-show-command` and `--keyboard-hide-command` values that produce the intended state. The helper deliberately has no default show/hide command.

```sh
python3 tools/gesture-acceptance.py --execute \
  --device /dev/input/eventN \
  --inject-script /path/to/inject-tap.sh \
  --keyboard-show-command 'pkill -RTMIN -x wvkbd-mobintl' \
  --keyboard-hide-command 'pkill -RTMIN -x wvkbd-mobintl' \
  --window-catalog-command '/run/current-system/sw/bin/k230-window-catalog' \
  --launcher-pid "$(pidof k230-touch-launcher)" \
  --metrics-file /run/shell/launcher-metrics.txt \
  --output-dir docs/evidence/launcher-gestures/UTC-run
```

The execution mode refuses a catalog with fewer than two rows, so an empty or single-card overview is not accepted as a multi-card result. It retains only that row count: do not save or publish raw window titles or the catalog command output.

Start the native launcher with `K230_LAUNCHER_METRICS=/run/shell/launcher-metrics.txt` before the run. The copied fields are CPU-side **wall-clock** render and release-to-submit intervals plus transient client bytes. They do not measure process CPU accounting, display scanout, or physical presentation.

The default is plan-only: it writes a plan but makes no board, uinput, `grim`, or physical-touch claim. `--self-test` is a host-only mocked subprocess check of action order, the 42 injected drags, settle waits, and before/after resource snapshots.

This is injected-touch evidence only. A separate real-finger camera trial must show left/right paging, overview entry/exit, a card tap, and Back before the physical-glass task can close. Do not tick any hardware task from this procedure alone.
