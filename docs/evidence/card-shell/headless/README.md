# Product card adapter: host implementation proof

Recorded 2026-09-23T07:09Z–07:12Z. Branch `impl/card-shell-adapter`, worktree
`k230-card-shell-adapter`, implementation base `f655a2804208` (probe merge
`aaff330`, accepted contract `af5f2e8`, policy `237be7b` + `c2ece6a` cherry-picked).
The root coordinator owns the board; this work used no board or UART.

Evidence class: **actual cross-built Sway 1.12 / wlroots 0.20.2, headless Pixman
under QEMU user emulation, real native XDG/SHM clients, explicitly injected
input and virtual keyboard protocol events**. This is not panel, real finger,
OSK, normal service restoration, or board performance acceptance.

## Build and closure

```
nix build .#card-shell --max-jobs 1 --cores 8 --no-link --print-out-paths
```

PASS, final output `/nix/store/vv68a0gg1wv63dnvx58q1a0x9pihh402-k230-card-shell`.
The wrapper supplies D-Bus/coreutils/bash PATH entries for transient sessions.
Unwrapped compositor:
`/nix/store/cr22m8r2rq2h89mjxk1pv4sya1p1ha3s-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`.

`closure.json` records `nix path-info --recursive --json` for this package and
the unchanged normal system
`/nix/store/nz82q373yj1hp2k4qm85xa3c328jli8j-nixos-system-nixos-26.11.20260919.20b1ddd`.
Only five store paths are additional; all shared libraries already belong to
the normal system. These are NAR closure bytes, not runtime RAM or compressed
transfer size. No system-image dependency or default shell changed.

## Actual runtime and named gates

```
export CARD_SHELL_SWAY=/nix/store/cr22m8r2rq2h89mjxk1pv4sya1p1ha3s-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway
export CARD_SHELL_CLIENT=/nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client
python3 tests/test_card_shell_composition.py
python3 tests/test_card_shell_gestures.py
python3 tests/test_card_shell_recovery.py
python3 tests/test_card_shell_state.py
python3 tests/test_touch_menu.py
```

All PASS: three named actual-compositor suites, exact-disabled opt-in check,
21 compiled ASan/UBSan policy cases, and seven existing touch-menu tests.
`TMPDIR=/mnt/MediaVolume/card-tests` was used after the host `/tmp` user quota
filled; this only changes temporary test artifact placement.

The longer producer/parser run used:

```
python3 tests/card_shell_runtime.py --sway "$CARD_SHELL_SWAY" \
  --client "$CARD_SHELL_CLIENT" --benchmark \
  --output /mnt/MediaVolume/card-tests/final
```

`result.json` lists sixteen verified behaviors. Assertions include both live
parent and independently committing child frame counts advancing while both
cards are actually visible, pixel changes during direct drag, tap expansion
and virtual-key delivery, upward throw generating an actual XDG close request,
refusal retaining the client until separately labeled timeout, accepted close
exiting another client, private/unavailable uniform placeholder pixels, privacy
changes during active composition, three mapped stable view IDs, top-bar
restoration, no-up stream cancellation, two-contact draining, edge/button entry,
output-loss restoration, and a clean compositor exit. Fully offscreen mirrors
correctly receive no presentation/frame feedback.

A teardown regression found during development was fixed before this record:
output disable now restores routing synchronously before Sway evacuates its
workspaces. Render/timer checks cannot substitute for this hook because a
zero-output state stops rendering. The tests assert restoration before output
re-enable and a zero exit status after clients, keyboard, and compositor close.

`two-live.png`, `during-drag.png`, `private.png`, and `unavailable.png` are actual
headless captures of synthetic fixtures. No physical panel is shown. Exported
compositor lines contain only the patch's fixed-schema IDs, counters and states;
client logs contain synthetic fixture data and key counts, never key contents.
The normal Sway debug journal is not committed.

## Benchmark integration result: acceptance remains open

```
python3 tools/card-shell-benchmark.py \
  --input docs/evidence/card-shell/headless/benchmark.txt \
  --output docs/evidence/card-shell/headless/benchmark.json
```

Parser implementation `d3ffbd7` consumed the actual telemetry without schema or
correlation errors: 107 inputs map to 104 successful commits, including three
coalesced inputs; no unresolved input/commit/presentation IDs. Same two mapped
apps span baseline, active deck, and restored resource phases. Entry header
follows earlier baseline samples. Submission is timestamped before commit
dispatch and logged only on success; actual presentation uses backend feedback.
Nested CPU scopes include input, render, prepare and timer reconciliation once.

**Exit 1 / diagnostic FAIL is preserved, not waived:** headless tracking frame
interval p95 was 52.16033 ms against the provisional 33.334 ms limit. Isolated
session memory is INCOMPLETE because this host run did not claim a dedicated
cgroup. The report explicitly says `NOT_BOARD_EVIDENCE`; passing individual
host timing metrics does not establish K230 performance. Root must run the
separately declared board benchmark, including total isolated-session memory,
actual RGB565 output and physical/injected provenance, before cost acceptance.

## Remaining work

Product image integration/QEMU boot, every physical control/keyboard route,
board injected acceptance, optical/real-finger trial, and measured Pixman cost
remain UNVERIFIED. The architecture probe has its own independent board gate.
This product package is opt-in and has no product board-session harness yet;
operator session/rollback integration must be reviewed before deployment.
After an isolated session is installed, arm `card_shell benchmark physical` or
`injected`, retain the same apps for >=3-second baseline/active/restored phases,
then collect normalized telemetry and run the committed benchmark command with
`--board` and its required provenance manifest. Do not reuse the architecture
probe's package identity as product deployment evidence.
