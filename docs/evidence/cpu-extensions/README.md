# K230D C908 extension inventory

This is a source and **previous physical-report** audit for the proposed
ordinary vector image, not a new physical execution result. The board's
captured [CPU report](../hardware-userspace.md) says
`rv64imafdcv_zicbom_zicboz_zicntr_zicsr_zifencei_zihpm_zba_zbb_zbs_svpbmt`.
The pinned vendor
[`k230.dtsi`](../../../nix/dts/k230-tdisplay.dts) includes the pinned
`arch/riscv/boot/dts/canaan/k230.dtsi`, which additionally declares `zbc`
and `zicbop`. This DT is a software declaration, and Linux's `/proc/cpuinfo`
is still based on detected/parsed platform information. Neither is an
instruction-by-instruction physical conformance test. The vector trial's
[physical boot report](../card-shell/kernel-rvv/board-trial/boot1-selected.log)
prints base `acdfimv`; its
[context report](../card-shell/kernel-rvv/board-trial/vector-state1.json)
records hwprobe V and signal/scheduling preservation. Other hwprobe keys
were not collected there.

| Extension(s) | Layer and present evidence | Ordinary-image decision / remaining proof |
| --- | --- | --- |
| RV64I, M, A, F, D, C | User and kernel baseline; `/proc/cpuinfo` and successful physical Linux userspace boot. | Already available through the ordinary riscv64 ABI/toolchain baseline. Keep it; no new global ISA change. |
| V | Kernel state management plus gated userspace Pixman. DT, physical hwprobe V, 2-process signal/scheduling probe and [192 exact pixel cases](../card-shell/pixman-rvv/pixel-trial/README.md) pass on the trial kernel. | Enable the same kernel state support and Pixman runtime gate in the ordinary graph. Candidate normal-image boot, actual library mapping and recovery remain **UNVERIFIED**. Pixman's scalar fallback remains mandatory. |
| Zba, Zbb, Zbs | Standard userspace bit manipulation; physical CPU report lists all three. The candidate config has dynamic `RISCV_ISA_ZBB=y`; Zba and Zbs have no corresponding kernel switch in this tree. Pinned GCC 15.3 accepts the target ISA and emits `cpop` for an isolated function (command below). | A targeted library path still needs runtime dispatch and physical execution/benefit proof. That proof is **UNVERIFIED**. No global `-march` widening; existing binaries continue to boot without these instructions. |
| Zbc | Standard carry-less multiplication; vendor DT names it but the physical CPU report omits it. | **UNVERIFIED** and excluded from default codegen pending a safe physical probe. |
| Zicbom | Kernel cache-block management for noncoherent DMA; DT and physical CPU report name it. The candidate config has dynamic `RISCV_ISA_ZICBOM=y`. | Keep kernel-managed detection and existing DMA behavior. Actual candidate operation remains **UNVERIFIED**; no blanket userspace use. |
| Zicboz | Kernel cache-block zeroing; DT and physical CPU report name it. The candidate config has dynamic `RISCV_ISA_ZICBOZ=y`. | Retain the kernel's dynamic path; a userspace or library zeroing path needs separate measurement and fault-safe detection. Actual candidate operation is **UNVERIFIED**. |
| Zicbop | Prefetch hint; named in vendor DT but omitted from physical CPU report. | Exclude from required codegen. The hint's utility and actual availability are **UNVERIFIED**. |
| Zicntr, Zihpm | Counter/performance-monitor interfaces, named in DT and physical CPU report. | No generic renderer build switch. Access policy and meaningful workload use remain **UNVERIFIED**. |
| Zicsr, Zifencei | Control-register and instruction-fence base instructions, named in DT and physical CPU report. The [stage-1 ELF inventory](../../blob-inventory.md) also records them for SPL. | Existing firmware/toolchain baseline already accounts for them; no added performance flag. User-mode CSR access is separately controlled by privilege. |
| Svpbmt | Supervisor page-based memory-type extension, named in DT and physical CPU report. The candidate config has `RISCV_ISA_SVPBMT=y` with dynamic detection. | Kernel/firmware boundary only; do not emit supervisor opcodes in userspace. Candidate page-attribute behavior remains **UNVERIFIED**. |
| Xuantie-specific extensions and vector-version variants | C908 compatible and vendor errata paths exist, but no exhaustive custom-opcode list or version conformance report has been collected. OpenSBI's Canaan overlay handles the MAEE page-attribute quirk. | Do not select `xthead*` or alternate vector codegen globally. Each proposed custom instruction needs exact vendor source, toolchain support, kernel/firmware contract and physical execution proof. **UNVERIFIED** otherwise. |

The [stage-1 U-Boot recipe](../../../nix/uboot-k230.nix) documents the
vendor SPL ELF as `rv64imac_zicsr_zifencei` and hand-encoded T-Head cache
operations. The [OpenSBI recipe](../../../nix/opensbi-k230.nix) uses Canaan's
nine-file overlay to clear MXSTATUS.MAEE; that stage-1 behavior is not a
reason to ask the Nix userspace toolchain for custom instructions. The
[vendor kernel Kconfig](../../../nix/kernel.nix) offers dynamic Zbb,
Zicbom, Zicboz and Svpbmt paths. The evaluated candidate config at
`/nix/store/gqrjmbw5k0k6i9m66sp5fyhza6202dbh-linux-config-riscv64-unknown-linux-gnu-6.6.36-xuantie`
contains all four, `RISCV_ISA_V=y`, `RISCV_ISA_V_DEFAULT_ENABLE=y`,
`DYNAMIC_SIGFRAME=y` and `ERRATA_THEAD_VECTOR=y`. This is host
configuration evidence; physical candidate operation is still unverified.

The separate [six-run card comparison](../card-shell/kernel-rvv/card-cost/README.md)
showed small mixed CPU changes and failed card frame/tracking budgets. This
inventory does not recast that experiment as a speedup or card acceptance.

Source audit command (host, no board):

```sh
rg -n 'riscv,isa|riscv,isa-extensions' \
  /nix/store/l6jdpbzp53y5n24ky6602f41gzs6f6ik-linux-xuantie-k230-rvv-src/arch/riscv/boot/dts/canaan/k230.dtsi
```

Toolchain-only check (host, no board; assembly generation does not show that
the CPU can execute the instruction):

```sh
/nix/store/4j2mwxqjvnyr6da0925sp0bm4jaj5r5i-riscv64-unknown-linux-gnu-gcc-wrapper-15.3.0/bin/riscv64-unknown-linux-gnu-gcc \
  -march=rv64gc_zba_zbb_zbs -mabi=lp64d -S -x c \
  -o /tmp/k230-zb-toolchain.s - <<<'unsigned long f(unsigned long x) { return __builtin_popcountl(x); }'
rg -n 'cpop|\\.attribute arch' /tmp/k230-zb-toolchain.s
```

The same pinned GCC 15.3 also accepted the entire vendor DT extension string
in an isolated assembly-only check:

```sh
/nix/store/4j2mwxqjvnyr6da0925sp0bm4jaj5r5i-riscv64-unknown-linux-gnu-gcc-wrapper-15.3.0/bin/riscv64-unknown-linux-gnu-gcc \
  -march=rv64gc_zba_zbb_zbc_zbs_zicbom_zicbop_zicboz_svpbmt \
  -mabi=lp64d -S -x c -o /tmp/k230-declared-isa-toolchain.s - \
  <<<'unsigned long f(unsigned long x) { return __builtin_popcountl(x); }'
rg -n 'attribute arch|cpop' /tmp/k230-declared-isa-toolchain.s
```

The emitted attribute listed Zba/Zbb/Zbc/Zbs, Zicbom/Zicbop/Zicboz and
Svpbmt, and the sample emitted `cpop`. This establishes assembler/compiler
syntax only. In particular it does **not** resolve the physical report's
omission of Zbc and Zicbop, privilege policy, or the absence of an actual
targeted library path for most of these extensions.
