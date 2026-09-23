# Opt-in renderer cost profile

`K230_VGLITE_PROFILE=1` records wall and process CPU durations for each render
pass. The ordinary image remains unchanged; other values disable profiling.
The root diagnostic harness accepts `--profile` and passes that setting only
to its compositor. It retains its unprivileged client and recovery watchdog.

Phases cover immutable snapshot creation, imported-target cache maintenance,
VG-Lite initialization, target import, source allocation/conversion, GPU API
commands (including SDK source cache cleaning), synchronous finish, GPU resource
cleanup, and full Pixman replay. Total spans pass creation through source
release. It includes other pass bookkeeping and diagnostic logging; phase sums
need not equal total. Setup/clock/log overhead and capture disturbance remain.
Process CPU includes user/system time charged to the process; it excludes other
processes, separately accounted interrupts and whole-device cost. No optical
latency or scanout cadence is measured by these timers.

The production renderer sanitizer suite passes with profiling both disabled
and enabled, retaining exact pinned Pixman comparisons and failure quarantine.
Eight root-harness tests pass, including compositor-only opt-in, as do four
parser tests rejecting absent, malformed, failed, insufficient or mixed runs.
The narrow `nix build .#shell-compositor-vglite --max-jobs 1 --cores 8
--no-link --print-out-paths` passes and yields
`/nix/store/kb31nr0jgpz8bcpzy26s7l50r99vzxib-sway-1.12`.

```sh
TMPDIR=/mnt/MediaVolume/home/jadams \
WLROOTS_SOURCE=/nix/store/r2zcb3d3dgmz09qjaqsy945inal2h41r-source \
VGLITE_SOURCE=/nix/store/pvpqrg3diyi9mcgmqjc0f80hpdmk699p-source/buildroot-overlay/package/vg_lite \
  tools/test-vglite-renderer.sh
python3 tests/vglite/test_root_trial.py
python3 tests/vglite/test_cost.py
python3 tools/vglite-cost.py COST_LOG --minimum-frames 100 --discard-frames 20
```

Board profiling remains pending at this source checkpoint. This is a diagnostic
for the next optimization decision, not completion of the matched performance,
normal-service, cache or physical-control acceptance gates.
