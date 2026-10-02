# Curated launcher cross-build

Recorded 2026-10-02T05:13Z. Evidence class: **host cross-build**, not a
device installation, rendered panel, or real-finger observation.

Source: `99f640c5950e2e7e096b7242e18918ac55c0cae6`, branch
`close/launcher-curation-build`. The coordinator reserved the build slot;
no other cross-build was running. The old twelve-derivation blocker no longer
applied: a fresh dry run required six derivations.

```sh
nix build .#touch-launcher --max-jobs 1 --cores 8 --no-link --print-out-paths
```

Result: exit 0. All six derivations completed, including the launcher, its
action helper, window catalog, Foot wrappers, and terminal launcher.

Output: `/nix/store/6z4m5s5qgvs5d4lfykw4qld4rffw2m8g-k230-touch-launcher`.
Derivation: `/nix/store/4k6m99yvyq643znbx3g5s4l1pg2mmfpl-k230-touch-launcher.drv`.
The public `bin/k230-touch-launcher` is a wrapper using the cross-built
RISC-V Bash; its SHA-256 is
`e3f63e9d371da5f75b0277ffe09a64c65cbd21b92eb7988405b25959b289ed6e`.
The wrapper executes
`/nix/store/j3jjk924r5h30808src712i8b0n1rkb8-k230-touch-launcher-riscv64-unknown-linux-gnu-0.1/bin/k230-touch-launcher`.
`file` identifies that binary as a 64-bit RISC-V ELF with the double-float
ABI; its SHA-256 is
`79353fa1baa812a483e4b60b8fe80de0819baa45783d15d8b57ced096157aaae`.

The task group's host commands were repeated against the same source:

```sh
python3 tests/test_desktop_catalog.py
python3 tests/test_launcher_navigation.py
```

Results: 6/6 and 4/4 tests passed, respectively.

This artifact is the C launcher used by the rollback/reference session.
Building it does not replace the installed Rust shell. Proposal task 2.1 is
complete; task 2.2 remains open for the named real-finger catalog and failed
launch recovery check. The earlier [host record](host.md) describes the
production curation source and its fixture limits; its old uncached-build
note is superseded by this result.
