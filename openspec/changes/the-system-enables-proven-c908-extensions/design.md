## Context

See proposal.md. The pinned vendor `k230.dtsi` declares `rv64imafdcv_zba_zbb_zbc_zbs_zicbom_zicbop_zicboz_svpbmt` and separately names `zicntr`, `zicsr`, `zifencei`, and `zihpm`. This is firmware-supplied description, not execution proof for every extension. The physical trial kernel reported base `acdfimv`; its hwprobe V bit, signal/scheduling context test, and 192 Pixman byte comparisons passed. Six card runs in three matched pairs found small mixed CPU effects and failed independent card budgets. The normal system still uses the original kernel and Pixman.

## Goals / Non-Goals

**Goals:** Build one coherent default kernel/modules/initrd/renderer closure using the proven RVV path; retain runtime scalar dispatch and known-good rollback; produce a source- and runtime-grounded extension inventory with decisions by layer.

**Non-Goals:** Promise a card speedup, change existing performance budgets, force vector instructions globally, enable every vendor-specific opcode, alter stage 1 without evidence, or infer physical support from QEMU.

## Decisions

1. **Nix/kernel:** fold the tested vector compiler-probe correction and `RISCV_ISA_V`/`RISCV_ISA_V_DEFAULT_ENABLE` settings into the normal kernel derivation, then build matching external modules and initrd through the normal NixOS configuration. Keep the isolated trial output available for comparison and recovery provenance. The alternative of selecting a trial kernel in the ordinary image without rebuilding its dependent artifacts risks a mismatch.
2. **Nix/userspace:** build Pixman with the tested hwprobe syscall correction and `-Drvv=enabled` in the actual system package graph. Check the final closure has one Pixman provider and the actual compositor maps it. Pixman must select RVV only after the running kernel reports V; `PIXMAN_DISABLE=rvv` remains an operational scalar control. The prior `replaceDependencies` card package was suitable for a bounded experiment but not the fully rebuilt normal graph.
3. **ISA inventory:** compare the pinned DT declaration with physical hwprobe, boot log, kernel config, compiler/assembler support and relevant library dispatch. Record each named extension as enabled, already available, not meaningful at a given layer, or unverified. Standard application extensions (for example the bit-manipulation group) can be considered for targeted libraries after safe feature detection and representative physical tests. Cache-block operations and supervisor extensions have different privilege and kernel ownership. `zicbop` hints, counters and control/fence instructions are not generic reasons to rebuild all userspace with a wider `-march`. Xuantie custom instructions and vector-version compatibility need their own source/runtime proof before use. Reject global `-march` based only on DT strings because it could put unsupported instructions in startup paths before any runtime gate.
4. **Evidence/deployment:** build narrow derivations first, then a complete image with identities. Parameterize the existing pixel and card drivers with a validated candidate manifest; retain strict running-system and mapped-library guards and test that stale or mismatched manifests fail. One-time boot the candidate while retaining the persistent known-good selection. Check vector context, pixel equality and representative console, shell, Wi-Fi and card workloads; report card metrics without changing budgets. Return to the normal recovery selection and verify protected boot data, shell and network separately. Only then make the new normal selection persistent.

## Risks / Trade-offs

- **Kernel vector state regressions** → repeat the physical signal/scheduling probe and retain a one-time boot and known-good persistent entry.
- **Unexpected RVV dispatch or pixels** → check runtime library identity, scalar fallback and exact pixel comparisons; retain a disable switch.
- **Limited performance benefit** → report the earlier three mixed pairs (six runs) and new measurements as measured, without calling vector enablement card acceptance.
- **ISA description exceeds implemented support** → mark unproven extensions `UNVERIFIED` and defer their use pending per-extension source and physical evidence.
- **Larger rebuild closure** → build once through the normal package graph and inspect all Pixman dependencies before board selection.

## Migration Plan

Land the scope first. Build a complete candidate image and preserve its exact store paths. Stage it as a one-time selection with root watchdog/recovery; do not overwrite the known persistent entry or protected credentials. After physical checks and a separately recorded recovery boot, select the proved normal image. Revert by selecting the preserved prior closure if any check fails.
