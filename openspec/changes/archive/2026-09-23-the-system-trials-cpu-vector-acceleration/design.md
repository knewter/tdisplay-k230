## Context

See `proposal.md` for the performance gap and separate scope. Existing source work already fixes the pinned Xuantie compiler probe (`rv64iv` needs M with GCC 15) and Pixman's missing `sys_riscv_hwprobe` wrapper. Normal hardware still reports no usable standard V. The context diagnostic passes full Linux QEMU cases and safely skips on the normal board. These are reusable checkpoints, not trial-kernel or speedup acceptance.

## Goals / Non-Goals

**Goals:** make the existing experiment reproducible, recoverable and measurable; close each diagnostic/build/board stage with its own evidence; feed a concrete result to the card cost decision.

**Non-goals:** see the proposal. In particular, do not change the normal kernel/renderer, relax card budgets, claim a second core, or require RVV to finish the independent Pixman card path.

## Decisions

- **Kernel and Nix own one coherent trial system.** Keep the compiler-detection correction opt-in. Derive external Wi-Fi modules and initrd from the selected kernel. A standalone kernel swap beneath old modules is rejected. Record ordinary and trial identities separately and retain the storage-growth service.
- **Stage 1 is only the existing loader.** Reuse the proven memory map, verify loaded sizes/checksums and import trial arguments only into volatile environment state. Keep normal boot files/profile available and avoid `saveenv`. Reflashing for every experiment is rejected because it needlessly replaces the known return path. A physical reset remains a possible recovery action after a kernel hang; do not relabel that limitation as automatic recovery.
- **Userspace asks the kernel before executing vectors.** Keep scalar hwprobe entry code and fallback. ISA strings and forced-dispatch environment overrides cannot establish usable state handling. Require the positive context probe on physical hardware; retain full-system QEMU positive and corruption controls as diagnostic validation. QEMU user emulation is rejected as context proof because the existing signal test fails there.
- **Correctness precedes cost.** Add a narrow physical Pixman comparison for declared RGB565/ARGB pixel cases before an opt-in vector compositor package. Compare repeated identical card workloads with normal runtime vector selection and with vectors disabled. Keep kernel, scene, panel format, input sequence and measurement producer fixed within each pair. Do not compare unrelated workloads or promote synthetic throughput as interaction latency.
- **Reconcile existing evidence rather than repeat everything.** Review and cite the exact existing successful host/guest artifacts. Rerun only when source/artifacts changed or a remaining physical condition requires it. Failed load/parser/context runs remain visible. Full-image readback remains opt-in under the repository flashing policy.

## Risks / Trade-offs

- [A trial hangs before userspace] → preserve normal persistent boot files and the known recovery image; record whether serial reset is possible or a physical reset is needed.
- [Vector state corrupts another task or a signal frame] → use the guarded two-process signal/preemption diagnostic before renderer trials, preserve its failure controls, and do not bypass a missing capability.
- [Build support is mistaken for acceleration] → distinguish host, full guest, board instruction, pixel and full card workload evidence.
- [Correct vector code loses at real workloads] → retain paired results and the ordinary renderer; a negative performance decision is useful evidence, not a reason to weaken the budget.
- [Injected input overstates touch validation] → label native capture and injected control checks explicitly; real-finger/default compatibility remains a separate acceptance gate.

## Migration Plan

Publish this scope, then reconcile the existing source/build/guest checkpoints. Finish the physical load-and-return path and record normal recovery. Boot the matching system once, capture capability/configuration/context results and normal shell/network observations, then return and reverify normal boot. Only after a physical context PASS should pixel and paired card trials proceed. Keep every unmet gate open. A default promotion, if justified, is proposed separately with its remaining image and real-glass checks.
