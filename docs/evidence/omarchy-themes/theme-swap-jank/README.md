# Theme-swap jank: capture tool and the persistent-helper win

Addresses "theme switcher is VERY janky, capture jank and optimize", with a
hard target from the user: the new theme visible within about 100 ms of the
Apply tap, touch and animation never stalling. This is a **host +
headless-QEMU-under-`qemu-riscv64-static`** result: no board, glass, or
real-finger observation. Run 2026-09-24, worktree
`fix/wallpaper-visible-swap-jank`, base `master` `b9f81d47`.

## What exists already, and was checked before writing anything new

Per the task's own pointers: no `tools/shell-motion-trace.py` exists in this
repository. `tools/analyze-launcher-transitions.py` and
`tools/analyze-video-presentation.py` parse a different, unrelated
telemetry shape (launcher-transition CPU records and video presentation
frames). `tools/card-shell-benchmark.py` is the closest prior art -- a
`K230_CARD_BENCH`-prefixed telemetry parser with percentile/budget checks
and a `--board`-gated provenance manifest -- but it measures card drag/
tracking motion, not theme-swap events, and has no theme-swap schema.
`SWAY_K230_CPU_FRAME_TIMING`'s diagnostic Sway build
(`k230.shell.frameTiming`) is **mutually exclusive with `coherentShell`**
(`nix/shell.nix`'s own assertion), so it cannot instrument the board's real,
shipped shell session at all -- this capture tool deliberately does not
depend on it, and instead uses signals the production `coherentShell`
build already emits: the Rust shell's own `rust-shell <ms>ms <event>` log
(`fn log` in `nix/rust-shell-client/src/main.rs`) and `K230_CARD_SHELL`
`sway_log` lines from `nix/card-shell/adapter.c`, both readable from
`journalctl -u shell-ui -u shell` with no board reconfiguration.

## New tools

- `tools/theme-swap-jank.py` -- runs on the board as root (needs
  `/proc/<pid>/stat` for arbitrary pids and `journalctl`), triggers a swap
  as the shell user via `runuser`, samples per-process CPU every ~20 ms
  (sway, the Rust shell, and any live `theme_catalog.py`/`theme_helperd`
  helper process it finds by `cmdline`), and merges `journalctl -o json`
  lines from both units by wall-clock timestamp into one ordered event
  timeline. Writes one JSON report under `/run/`. `--self-test` exercises
  its `/proc/stat` parsing, CPU-percent math, and journal-line tagging
  against fixtures and touches no PID, journal, or `/run` file.
- `tools/analyze-theme-swap-jank.py` -- host-only. Reads that JSON and
  produces: a frame-interval histogram (bucketed <16.7/33.4/50/100/200/500
  ms), gaps over 33/50/100 ms with the two bounding events, the single
  longest stall plus every event (including the sway side) that happened
  during it, tap-to-visible latency against a configurable target (default
  100 ms, matching the user's stated target), and per-process CPU
  avg/max. `--self-test` proves a smooth-swap fixture passes and a
  janky-swap fixture (a synthetic ~1.85 s stall) fails on both the
  tap-to-visible and the gap-over-100ms checks, with the stall's context
  correctly including the sway-side event that happened during it.

```sh
python3 tools/theme-swap-jank.py --self-test
python3 tools/analyze-theme-swap-jank.py --self-test
```

Both currently pass (5 and 5 cases).

## The one jank source this change actually fixes: Python start-up

Board evidence already on `master`
(`docs/evidence/omarchy-themes/background-decode-cache-qemu/README.md`)
measured a bare `k230-theme --help` at 1259 ms against 71 ms for `runuser`
alone, and attributed most of that (via `PYTHONPROFILEIMPORTTIME`) to
importing `theme_activate` and its own dependents, not bare interpreter
start-up. A chooser Apply calls `k230-theme` twice (`preview` then
`activate`), so close to 2.4 s of the observed 2.8-3.5 s swap was paid
importing modules, not doing theme work.

`tools/theme_helperd.py` (a new persistent daemon) imports that chain once
and serves every later request over `/run/shell/theme-helper.sock` by
calling `tools/theme_catalog.py`'s own `build_parser()`/`handle()` --
extracted from its `main()` with no behavior change (see
`tests.test_theme_catalog`, all 10 pre-existing cases still pass).
`tools/theme_client.py` replaces `k230-theme`'s wrapped entry point: it
tries that socket first, using a second, deliberately minimal parser that
never imports `theme_catalog`, and falls back to the exact original
in-process path (never a second subprocess) when the daemon is not
reachable.

Full detail, rejected alternatives, and the requirement this adds are in
`openspec/changes/the-shell-swaps-themes-without-a-python-stall/`.

### Host + QEMU numbers (directional, not the board's own number)

Built `.#handheld-theme-command` fresh from this worktree:
`/nix/store/6i9i4am2f2nha0lj3yn4m7phd2bn2k9v-handheld-theme-command-0.1`
(a riscv64 package, run here under `qemu-riscv64-static` -- this is
cross-architecture emulation overhead dominating the absolute numbers, not
the K230's actual in-order core; only the *relative* before/after
comparison is meaningful from this host).

| | 5x `k230-theme list --json` | per call |
| --- | ---: | ---: |
| No daemon (fallback path, i.e. today's behaviour) | 5.740 s | 1.148 s |
| `theme-helper.service` running | 3.925 s | 0.785 s |

About a 32% reduction on this host under qemu-user emulation, despite qemu
overhead swamping the real per-call import-vs-runtime ratio the K230 itself
will show (its own evidence already isolates ~1.2 s as import cost
specifically, a much larger fraction of a ~1.15 s call there than of a
qemu-emulated call here). `python3 -X importtime` on a real subprocess
confirms the daemon path never imports `theme_catalog`/`theme_activate`/
`theme_transaction`/`theme_preferences`/`keyboard_appearance`
(`tests/test_theme_helper_daemon.py`'s
`test_client_subprocess_never_imports_theme_catalog_when_the_daemon_answers`).

## Board commands for the coordinator

Reserved-board evidence gate for tasks 2.3/3.4 in the OpenSpec change
above. Exact commands, once a system built from this change (or a later
`master` that includes it) is installed:

**1. Jank capture, before this change lands** (on the currently-installed
system, which has no `theme-helper.service`):

```sh
./tools/console.py /dev/ttyACM0 --wait=3 \
  "python3 /path/to/tools/theme-swap-jank.py --theme-id catppuccin-latte --duration-after-s 3"
# prints the /run/theme-swap-jank-<epoch>.json path it wrote; copy it off, e.g.:
./tools/console.py /dev/ttyACM0 --wait=3 "cat /run/theme-swap-jank-<epoch>.json" > /tmp/before.json
python3 tools/analyze-theme-swap-jank.py --input /tmp/before.json --output /tmp/before-report.json
```

(`tools/theme-swap-jank.py` needs to be present on the board -- either
`push-file.py` it over, or run it from an installed store path once this
change ships a package for it; it is a stdlib-only script with no build
step.)

**2. After landing this change** (installed system now has
`theme-helper.service` active -- confirm with
`systemctl is-active theme-helper`), repeat the exact same capture command
and compare `tap_to_visible_ms` and the gap histograms between the two
reports.

**3. Wallpaper visibility**, tying back to the sibling investigation in
this same branch: `docs/evidence/omarchy-themes/wallpaper-visibility-board-report/README.md`
has the exact `swaymsg card_shell enter` + `grim` + diagnostic commands.

Neither jank-capture run above has been executed on the board by this
change; `/dev/ttyACM0` was not opened. Task 2.3 in the OpenSpec change's
`tasks.md` remains open until the coordinator (or whoever holds the board)
runs it and commits both reports here.
