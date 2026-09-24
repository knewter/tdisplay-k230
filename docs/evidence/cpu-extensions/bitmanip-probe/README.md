# C908 userspace bit-manipulation probe: source and host preparation

This is bounded preparation for OpenSpec task 2.2, not evidence that the board
executes any additional extension. Task 2.2 remains unchecked pending a
candidate host build and recorded physical execution. No system package or
global ISA flags change here.

The pinned vendor device tree at
`/nix/store/l6jdpbzp53y5n24ky6602f41gzs6f6ik-linux-xuantie-k230-rvv-src/arch/riscv/boot/dts/canaan/k230.dtsi:37-40`
declares Zba, Zbb, Zbc and Zbs. Existing physical CPU reports in
[`docs/evidence/cpu-readiness.txt`](../../cpu-readiness.txt) and
[`docs/evidence/second-core/live-handoff.txt`](../../second-core/live-handoff.txt)
list Zba, Zbb and Zbs but omit Zbc. Those strings describe firmware/kernel
advertisement; they do not establish safe userspace execution. The omission
makes Zbc especially uncertain. All four remain **UNVERIFIED for this
probe's physical execution**.

[`nix/c908-bitmanip-probe.c`](../../../../nix/c908-bitmanip-probe.c) tests one
representative opcode per extension: Zba `sh1add`, Zbb `andn`, Zbc `clmul`,
and Zbs `bset`. Each has four fixed edge/mixed vectors and an independent
baseline scalar reference. The recipe
[`nix/c908-bitmanip-probe.nix`](../../../../nix/c908-bitmanip-probe.nix)
sets `-march=rv64gc -mabi=lp64d -fno-lto`; inline assembly enables only the
named extension inside a never-inlined helper. Every opcode executes in a
separate child. A SIGILL is reported as unsupported, a wrong value as fail,
and a timeout or other fault as error. The parent kills a child after one
second. The four-character `cases` field preserves source-order results
(`P` exact, `I` SIGILL, `F` wrong, `E` error). Mixed success and SIGILL within
one family is an error. Host
`--self-test` covers scalar vectors and synthetic SIGILL, mismatch and timeout
paths; it does not run the extension instructions.

The recipe is intentionally not wired into `flake.nix` while the normal RVV
closure uses the build slot. After that build owner adds a separate
`pkgsCross.callPackage ./nix/c908-bitmanip-probe.nix { }` output, build that
output narrowly, inspect its ELF ISA attributes and helper disassembly, and
run `--probe` only under the board reservation. Capture exact executable,
running system, boot ID, board model, serial report and command in a new
physical evidence file. The probe's `runtime-probe-unclassified` label is
deliberate: its stdout alone does not authenticate a physical board. A
host/QEMU result cannot substitute for this gate or justify enabling a library
path. Zbc may correctly report `UNSUPPORTED`; do not add it to normal startup
or application flags based on the device-tree string.

Host check performed, using the already-present pinned cross tools directly
without a Nix derivation build:

```sh
C908_RISCV_CC=/nix/store/hjydl5cms9fq246i5ds51r4zc34f7gzd-riscv64-unknown-linux-gnu-gcc-15.2.0/bin/riscv64-unknown-linux-gnu-gcc \
C908_RISCV_OBJDUMP=/nix/store/w09zhchxszcai49si8mw3059xhhyxd20-riscv64-unknown-linux-gnu-binutils-2.46/bin/riscv64-unknown-linux-gnu-objdump \
python3 tests/test_c908_bitmanip_probe.py
```

Result: two host tests passed. The cross object advertised baseline `rv64gc`
without Zba/Zbb/Zbc/Zbs in `Tag_RISCV_arch`, while disassembly contained
the four intended instructions. This proves source/toolchain isolation, not
that the running C908 accepts any opcode. A direct ad hoc cross link outside
the Nix cross environment could not find `Scrt1.o` and `-lc`; the Nix recipe
still needs its named build check when the build slot is free. No board, QEMU
or Nix build was run.
