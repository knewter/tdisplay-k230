# Injected gesture acceptance procedure

Run this only with the board operator holding the serial and graphical-session reservation. It is a board-local helper: it uses the existing `tools/inject-tap.sh` virtual touchscreen and captures native Wayland PNGs with `grim`.

The helper alternates 20 left and 20 right drags from the Apps card region. It then captures a keyboard-visible state supplied by the operator, records a read-only window-catalogue count, opens the overview with an upward drag, and taps the overview Back control. It writes `acceptance.json`, PNGs, optional `window-catalog.tsv`, and optional `/proc/<launcher-pid>` memory snapshots under the selected evidence directory.

```sh
python3 tools/gesture-acceptance.py --execute \
  --device /dev/input/eventN \
  --inject-script /path/to/inject-tap.sh \
  --keyboard-command 'kill -USR2 "$(pidof wvkbd)"' \
  --window-catalog-command '"$K230_WINDOW_CATALOG"' \
  --launcher-pid "$(pidof k230-touch-launcher)" \
  --output-dir docs/evidence/launcher-gestures/UTC-run
```

Start the native launcher with `K230_LAUNCHER_METRICS=/run/shell/launcher-metrics.txt` before the run, then copy that metrics file beside `acceptance.json`. The fields are CPU-side **wall-clock** render and release-to-submit intervals plus transient client bytes. They do not measure process CPU accounting, display scanout, or physical presentation.

Use `--dry-run` behavior (the default) first. It writes a plan but makes no board, uinput, `grim`, or physical-touch claim.

This is injected-pointer evidence only. A separate real-finger camera trial must show left/right paging, overview entry/exit, a card tap, and Back before the physical-glass task can close. Do not tick any hardware task from this procedure alone.
