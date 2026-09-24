# Normal-image vector build, host evidence

This records cross-build results for the proposed ordinary RVV board graph.
It is **host build evidence only**: no candidate boot, installed system,
physical vector result or recovery is claimed here. The relevant source
changes are `86aca3a2` (normal kernel/Pixman graph), `baebf364`
(normal-graph card package), and `55de932c` (target-only overlay guard).
The combined build branch includes the independently reviewed charged-input
instrumentation cherry-pick `a34e900e`; its landed master equivalent is
`c292ebcb`.

## Normal kernel: PASS

```sh
nix build .#kernel --max-jobs 1 --cores 4 --no-link --print-out-paths
```

The host cross-build completed successfully on 2026-09-23/24 UTC and printed
`/nix/store/nyka2ipsrg8i5w5grrc4y18pspyv9gxj-linux-riscv64-unknown-linux-gnu-6.6.36-xuantie`.
Its matching module output is
`/nix/store/4b9ijyimxs95dmd7pafc5pjm8yrk9c1f-linux-riscv64-unknown-linux-gnu-6.6.36-xuantie-modules`.
The exact kernel derivation is
`/nix/store/rai03djhpx5hf4jpk3x10wf0rb43vdx2-linux-riscv64-unknown-linux-gnu-6.6.36-xuantie.drv`.
The evaluated config is
`/nix/store/gqrjmbw5k0k6i9m66sp5fyhza6202dbh-linux-config-riscv64-unknown-linux-gnu-6.6.36-xuantie`;
it contains `RISCV_ISA_V=y`, `RISCV_ISA_V_DEFAULT_ENABLE=y`,
`DYNAMIC_SIGFRAME=y`, `ERRATA_THEAD_VECTOR=y`, and dynamic
`RISCV_ISA_ZBB=y`, `RISCV_ISA_ZICBOM=y`, `RISCV_ISA_ZICBOZ=y`,
`RISCV_ISA_SVPBMT=y`. The ordinary kernel and diagnostic trial aliases
evaluate to this same derivation, avoiding a second application of the
toolchain-probe source patch. This does not prove a physical boot.

## Initial compositor attempt: FAIL, corrected

The first `nix build .#shell-compositor --max-jobs 1 --cores 4 --no-link
--print-out-paths` failed in native x86 Pixman derivation
`/nix/store/5mspjxgk0i24acz5ibx9xvsayigb49sc-pixman-0.46.4.drv`.
Meson reported `RISC-V Vector Support unavailable, but required` while
identifying its host machine as x86_64. The board overlay had also applied
to native `buildPackages`, so the host tool dependency was incorrectly
asked to build RVV. This failure is retained; it was not a target Pixman
failure or a board result.

Commit `55de932c` restricts the RVV override to
`prev.stdenv.hostPlatform.system == "riscv64-linux"`. Evaluation after
that correction yields the unchanged, tested target RVV Pixman derivation
`/nix/store/3vhbn7qrav9g876s4kd6snp3rx6hhyvv-pixman-riscv64-unknown-linux-gnu-0.46.4.drv`
and native scalar Pixman derivation
`/nix/store/c69ckksfgkwwdp84gxi33m9m1zc2cjlh-pixman-0.46.4.drv`.
The corrected compositor build is a separate run; its result is recorded
below when complete.
