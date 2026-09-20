## Purpose

Defines how riscv64 artifacts for this board are produced on an x86_64 host,
and what is recorded when a package will not cross-compile.

## ADDED Requirements

### Requirement: The system is produced by cross-compilation, not emulation

*Grounding: `docs/evidence/cross-build.txt`. The full system closure was
cross-compiled on an x86_64 host with no riscv64 hardware — 353 derivations
built locally, ~970 substituted, producing 1.2 GiB across 474 store paths in
4413s. The resulting kernel booted under QEMU to a shell prompt
(`docs/evidence/qemu-boot.txt`).*

Building the system SHALL NOT require a riscv64 machine. The build SHALL
declare an `x86_64-linux` build platform and a `riscv64-linux` host platform,
so that derivations cross-compile by default.

Emulation SHALL remain available as a fallback for derivations that cannot
cross-compile, and any derivation built under emulation SHALL be named in the
repository rather than silently emulated. The distinction matters because
emulated builds are slow enough to change what is worth attempting.

#### Scenario: A closure is built on an x86_64 host

- **WHEN** someone with no riscv64 hardware builds the system
- **THEN** it completes, and produces riscv64 artifacts

#### Scenario: A package will not cross-compile

- **WHEN** a derivation fails to cross-compile and is built under emulation instead
- **THEN** it is listed in the repository as one that needs emulation, with what it cost

### Requirement: Cache coverage is partial, and the build says which part

Two things are easily conflated, and the difference decides whether a build
takes minutes or hours:

- **Native `riscv64-linux`** is community-tier in nixpkgs and is *not* built by
  the upstream cache.
- **Cross-compiled `pkgsCross.riscv64`** derivations are built *on* x86_64, so
  upstream does build many of them and they *are* substitutable.

Because this project cross-compiles, it benefits from that second case. The
project SHALL NOT assume full cache coverage, and documentation of the build
SHALL state the measured split between substituted and locally built paths, so
that a long compile is recognised as normal rather than as a fault.

*Grounding: measured on this host building the k230 closure — 636 paths
substituted from cache.nixos.org, of which 174 were riscv64 outputs, against
164 built locally. Recorded in `docs/evidence/cross-build.txt`.*

#### Scenario: A first build is attempted

- **WHEN** someone builds the system for the first time
- **THEN** they have been told which parts substitute and which compile, with a measured figure from a known machine

#### Scenario: Someone assumes riscv64 is entirely uncached

- **WHEN** the build's cost is estimated
- **THEN** the estimate distinguishes cross-compiled outputs, which largely substitute, from anything built natively on riscv64, which does not
