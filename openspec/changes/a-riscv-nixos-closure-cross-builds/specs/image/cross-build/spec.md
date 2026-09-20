## Purpose

Defines how riscv64 artifacts for this board are produced on an x86_64 host,
and what is recorded when a package will not cross-compile.

## ADDED Requirements

### Requirement: The system is produced by cross-compilation, not emulation

<!-- UNVERIFIED: nothing has been cross-built yet. Grounded once
docs/evidence/cross-build.txt records a completed closure. -->

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

### Requirement: There is no binary cache, and the build says so

<!-- UNVERIFIED: asserted from nixpkgs' stated support tier for
riscv64-linux, not yet observed on this host. -->

`riscv64-linux` is community-tier in nixpkgs and is not built by the upstream
cache. The project SHALL NOT assume cached substitutes for riscv64 artifacts,
and documentation of the build SHALL state the expected first-build cost so
that a long compile is recognised as normal rather than as a fault.

#### Scenario: A first build is attempted

- **WHEN** someone builds the system for the first time
- **THEN** they have been told beforehand that it compiles from source, and roughly how long that takes on a known machine
