## Context

The Qt Quick evaluation (`the-handheld-evaluates-qtquick-and-quickshell`, owned elsewhere) already provides the matched-pair harness: `nix/qtquick-shm-baseline` (a plain `wl_shm` client with the scene, gestures and JSONL event log), `tools/qtquick_analysis.py` (manifest, per-run metrics, percentiles, CPU, memory, comparison, restoration) and `tools/qtquick-trial.py`. This change imports those files and never edits them.

Layers: **Nix and userspace** only. Both toolkits run as transient clients of the normal Sway session.

## Goals / Non-Goals

**Goals:** Say plainly whether an egui app and a Sidestep app run well here, with the same metrics as the shell and Qt (frame/commit interval and render-time percentiles, process and combined CPU, RSS, startup, input-to-commit proxy). Separate "builds", "runs", "renders correctly" and "is fast enough".

**Non-goals:** see the proposal.

## Decisions

1. **egui renders on the CPU, not through wgpu or glow.** The board has no OpenGL or Vulkan (the VG-Lite GPU is a 2D vendor API, see `docs/research/gpui-handheld-feasibility.md`). The probe uses `egui` 0.34 with `egui_software_backend` 0.0.3 (its own rasteriser; `softbuffer`, `winit` and `rayon` stay disabled) and draws into a `wl_shm` buffer by `wayland-client`, the pinned crate set `nix/rust-shell-client` already cross-builds. `eframe` is excluded because it drags in winit and a GL/wgpu surface. Alternative considered: a tiny-skia painter for `epaint` meshes; rejected as new, unproven rasteriser code when a maintained backend exists.
2. **Same scene, same log.** Geometry, content, gestures and the JSONL events (`start`, `first_frame`, `input`, `commit`, with `r` = render microseconds added) match the baseline so `tools/qtquick_analysis.py` consumes them unchanged. The egui render time is reported alone because the baseline does not log it; comparisons use commit interval, input-to-commit, CPU, memory and startup.
3. **Renderer identity is observable.** The probe logs the egui version, backend crate version, buffer format and that no GL/Vulkan library is mapped (`/proc/PID/maps` check). A GL/Vulkan mapping fails the software-route gate.
4. **Comparable trial design.** Three alternating matched pairs per candidate against the same baseline client, 30 s idle and 30 s active phases, at least 24 scripted interactions per active arm, the Qt trial's workload id and ceilings (startup 5 s, incremental memory 128 MiB, idle client CPU 2%), and the unchanged card budgets as a separate production check. A new manifest schema names the candidate slot (`egui` or `sidestep`); the Qt manifest schema is untouched.
5. **Sidestep is judged from source before anything is built.** Its dispatch (`objc_msg_lookup`), class and object model are portable Rust. The architecture-specific pieces are the `saving_entry!` assembly frame (`trampoline.rs`), `objc_msgSend` (`msgsend.rs`), the forwarding trampoline (`forward.rs`), the register-file and calling-convention layout used by `NSInvocation` and forwarding (`call.rs`), block-implementation thunks (`block_imp.rs`), the ARC return-value handoff (`arc.rs`), and the `dispatch` queue's stack-switch code. Several of these already have `not(any(aarch64, x86_64))` fallbacks. The assessment counts lines per piece and classifies each as "fallback exists", "mechanical LP64D port" or "new design". A port is attempted only if the unfallbacked, non-mechanical share is small; the result is recorded either way.
6. **Evidence classes stay separate.** Host builds, QEMU user-mode runs (riscv64 instructions on an x86_64 host; they prove neither speed nor board behaviour), injected-input board runs and any camera or glass observation are labelled individually. The operator's glass waiver (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`) permits injected events plus native `grim` captures; it is recorded as a waiver, never as glass evidence.
7. **Transient board runs.** Deploy test clients by `nix copy` and a plain process start under the board lock with a fixed deadline; no `switch-to-configuration`, no boot-default change, no edits to user settings. Kill only owned PIDs, confirm the compositor identity and boot ID are unchanged, and remove copied paths.

## Risks / Trade-offs

- egui at 568x1232 on one in-order C908 core may be slow because every egui frame retessellates; that is the finding, not a defect of the trial.
- `egui_software_backend` is 0.0.x; its speed may understate a tuned egui renderer. The result is stated for this backend and version.
- The Sidestep port may compile yet fail at run time in assembly. Mitigation: QEMU user-mode conformance first; any failure is retained.
- QEMU user numbers are never performance evidence.
- The board is currently unreachable; board tasks stay open until it is back.

## Migration Plan

Land the proposal first. Then host assessment and builds, then QEMU user runs, then board trials when the board is available. No default image change; adoption would be a separate proposal.
