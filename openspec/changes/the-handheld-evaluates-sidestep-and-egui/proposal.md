## Why

Two people-visible questions are open as of 2026-10-30. The user asked whether the new Linux UI toolkit Sidestep (an Objective-C runtime plus Foundation/AppKit for Linux, so objc2 apps run unchanged) can run on this handheld, and how fast egui is on it. Neither is known. The shell, the Qt Quick trial and the card budgets give the yardsticks, but nobody has run an egui or Sidestep client on the board, and the board has no OpenGL, so egui's normal renderers are unavailable.

## What Changes

- Add an opt-in egui software-rendered Wayland client (egui plus `egui_software_backend`, presenting through `wl_shm`) that runs the same list, scroll, text-edit and animated-tile scene as the Qt Quick trial, and record how fast it is next to the Qt probe and the `wl_shm` baseline on the same Sway session.
- Reuse the Qt trial's harness rather than inventing one: the SHM baseline client, the event/JSONL schema, and the percentile, CPU, memory and startup analysis in `tools/qtquick_analysis.py`. The new tool imports it and adds only a candidate slot.
- Assess the Sidestep riscv64 port from source (which runtime pieces are architecture specific, how many lines, which have portable fallbacks). If the port is bounded, implement it as a patch overlay, cross-build its benches and examples, run its conformance tests under QEMU user mode, and then measure on the board. If it is large or uncertain, record the estimate and stop that part; that is a valid result.
- Publish a plain-language verdict per toolkit with numbers beside the shell and Qt results.

**Non-goals:** Replacing Sway or the live-card compositor; software OpenGL; a VG-Lite renderer for egui; upstreaming Sidestep changes; running macOS applications; changing the default image or session. This is an evaluation, not an adoption decision.

## Capabilities

### New Capabilities

- `runtime/egui-sidestep-validation`: opt-in egui and Sidestep trials with verified renderer identity, matched cost measurements, a bounded riscv64 port assessment and explicit evidence classes.

### Modified Capabilities

None. The normal shell contract is retained.

## Impact

Nix probe packages (`nix/egui-software-probe`, `nix/sidestep-riscv64`), a trial tool that extends the Qt analyzer, and evidence under `docs/evidence/egui-sidestep/`. Host work (source assessment, builds, QEMU user-mode conformance) can proceed with the board offline. Board measurement needs the board lock and a transient run (no system change, no boot-default change). No stage-1, kernel, device-tree or flash change.

Needs the physical board: only the measurement tasks (groups 3 and 5). Source assessment, builds and QEMU user runs do not.
