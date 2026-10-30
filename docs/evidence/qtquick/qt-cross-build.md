# Qt Quick probe: riscv64 cross-build record (task 1.1, 1.2, 2.3)

Evidence class: **host build/test**. Nothing here is a board observation.
Source: pinned nixpkgs Qt 6.11.2 (`pkgsCross.riscv64`), worktree branch of
`master` at the commits that add `nix/qtquick-software-probe` and
`nix/qtquick-shm-baseline`. Builds ran with `--max-jobs 1 --cores 4` under
`flock /tmp/k230-nix-build.lock`, in chunks so other agents could interleave.

## What happened, in order

| Local time (2026-10-30) | Step | Result |
|---|---|---|
| 08:22:48 to 08:49:55 | `qtbase` (cross, 1961 steps) | built, 27 min |
| 08:51:55 to 09:23:59 | `qtdeclarative` as pinned | built, 32 min, but **"Qt Quick support: no"** |
| 09:32:49 to 09:35:17 | `qtwayland` | built, 2.5 min |
| 09:38 to 09:40 | probe, first form (`pkg-config`) | **failed**: Qt 6 ships no `.pc` files; `Qt6Quick` not found |
| 09:49 | probe via CMake | **failed**: `Qt6QmlTools` (host tools) not found |
| later attempts | host Qt tools passed as paths | **failed**: `Qt6Quick_DIR` missing, because the pinned cross `qtdeclarative` did not build Qt Quick |
| 09:49:38 to 10:55:04 | `qtdeclarative` with the bounded correction (below) | built, 66 min, Qt Quick present |
| 10:59:15 to 11:00:20 | probe against it | **built** |

### The pinned cross build has no Qt Quick

`qtdeclarative`'s configure log (the pinned derivation) says:

```text
Qt Quick:
  Qt Quick support ....................... no
Note: Qt Quick modules not built due to not finding the qtshadertools 'qsb' tool.
-- Could NOT find Qt6ShaderToolsTools (missing: Qt6ShaderToolsTools_DIR)
```

The host qtshadertools output does contain `lib/cmake/Qt6ShaderToolsTools`
and `bin/qsb`; the cross configure just is not pointed at it. This is a
nixpkgs cross-build gap, not a device limit.

### Bounded correction (only one)

`nix/qtquick-software-probe/default.nix` overrides `qtdeclarative` with two
extra CMake flags that point at the build platform's tool packages:
`-DQt6ShaderToolsTools_DIR=` and `-DQt6QuickTools_DIR=` (the latter because
the next configure error was `Failed to find the host tool "Qt6::svgtoqml"`).
The probe passes `QT_HOST_PATH`, `Qt6QmlTools_DIR`, `Qt6QuickTools_DIR`,
`Qt6ShaderTools_DIR`, `Qt6ShaderToolsTools_DIR` as store paths rather than
inputs, because the qtbase hook aborts when two Qt ABIs are inputs
("detected mismatched Qt dependencies"). Nothing else in the closure is
changed; the default image and `qtwayland` are untouched.

## Configure summary of the final `qtdeclarative`

```text
QML just-in-time compiler .............. no     (QV4 runs the interpreter; no RISC-V JIT, as predicted from src/qml/configure.cmake)
QML network support / debugging ........ yes
Qt Quick: AnimatedImage, Canvas, Flipable, GridView, ListView, TableView,
          Repeater, ShaderEffect item, Sprite, VectorImage ... yes
Qt Quick Controls 2 styles ............. Basic Fusion FluentWinUI3 Imagine Material Universal
```

`ShaderEffect item: yes` only means the item type is compiled in; the
software scene graph cannot render it, which is what the probe's negative
control (`--negative-effect`) checks on the board. The probe loads
`Probe.qml` from disk at run time (no ahead-of-time or cache precompile), so
every start parses it with the interpreter.

## Identities

```text
probe     /nix/store/j2dd2anwbp2hpfmvm4w6kpsa0qn37zq8-qtquick-software-probe-riscv64-unknown-linux-gnu-0.1
baseline  /nix/store/y4qh2n92b7ailf2bw7129b9xynxzbz3h-qtquick-shm-baseline-riscv64-unknown-linux-gnu-0.1
qt        6.11.2 (qtbase, qtdeclarative, qtwayland); wrapper sets QT_QPA_PLATFORM=wayland QT_QUICK_BACKEND=software QSG_INFO=1, unsets QSG_RHI_BACKEND
```

`nix path-info -rs`: the probe's closure is 326 store paths, 1,681,872,192
bytes (the Qt libraries; it also references build-platform
`qtbase`, `gtk+3` paths through baked CMake files). Relative to the board's
current system (`49mnsl2s...`, 1215 paths) only **2 paths, 354,192,960 bytes**
are new: the probe itself and the Qt Quick-enabled `qtdeclarative`. The
baseline closure is 5 paths, 34,327,840 bytes, of which **1 path, 92,376
bytes** is new.

## Commands and results

```text
nix build .#qtquick-software-probe --max-jobs 1 --cores 4 --no-link --print-out-paths
  /nix/store/j2dd2anwbp2hpfmvm4w6kpsa0qn37zq8-qtquick-software-probe-riscv64-unknown-linux-gnu-0.1
nix build .#qtquick-shm-baseline --max-jobs 1 --cores 4 --no-link --print-out-paths
  /nix/store/y4qh2n92b7ailf2bw7129b9xynxzbz3h-qtquick-shm-baseline-riscv64-unknown-linux-gnu-0.1
python3 tests/test_qtquick_probe_scene.py     OK (14 tests; host scene/output fixtures)
python3 tools/qtquick-trial.py --self-test    OK
python3 tests/test_qtquick_trial_recovery.py  OK (host simulation)
python3 tools/qtquick-trial.py prepare --qt PROBE --baseline BASELINE --output docs/evidence/qtquick/qt/manifest.json
  manifest hash 3820d48b32bf5381 (system and compositor read from the board, read-only)
prepare with a missing --qt path        -> error: qt: .../bin/qtquick-software-probe is missing (exit 2, no manifest written)
prepare with --qt equal to --baseline   -> error: qt: ...: bin/qtquick-software-probe is missing (exit 2, no manifest written)
```

The host also compiled `nix/qtquick-software-probe/main.cpp` natively against
the host's Qt 6.11.1 and ran it with `QT_QPA_PLATFORM=offscreen
QT_QUICK_BACKEND=software`: it printed `start`, `commit`, `first_frame`,
`exit` events (host, not board).
