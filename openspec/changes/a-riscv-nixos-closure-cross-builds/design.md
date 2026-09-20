## Context

See proposal.md — Why. The constraints that shape the approach:

- The build host is `x86_64-linux` with 32 cores and 125 GiB of RAM, Nix 2.35
  with flakes, and `binfmt` `qemu-riscv64` already registered.
- `riscv64-linux` has no upstream binary cache, so wall-clock cost is dominated
  by compilation, and anything that lands in the closure is paid for repeatedly.
- QEMU 11.1.0 provides `-machine k230`, described as "RISC-V Board compatible
  with Kendryte K230 SDK". It models the SoC well enough to boot; it does not
  model this board's panel, touch controller, SDIO radio, or SD layout.
- The real boot chain is vendored and unavailable under QEMU, so the QEMU path
  and the hardware path load the kernel differently. That difference is the
  main thing this design has to keep honest.

## Goals / Non-Goals

**Goals:**

- Settle whether a riscv64 NixOS closure cross-builds on this host, cheaply.
- Establish the stage-1 seam as a structural boundary from the first commit.
- Produce a boot transcript that later changes can diff against.

**Non-Goals:**

- Matching the hardware boot path. QEMU loads a kernel directly; the board goes
  through vendored U-Boot. Pretending these are the same is how the next change
  gets a nasty surprise, so they are kept visibly distinct.
- Closure size or boot speed.
- Any device this board has and QEMU does not model.

## Decisions

**Cross-compile by default; emulate only named exceptions.**
`nixpkgs.buildPlatform = "x86_64-linux"` with
`nixpkgs.hostPlatform = "riscv64-linux"`. The alternative — run the whole build
under `binfmt` emulation — was rejected because a full NixOS closure emulated
through QEMU user-mode on this host would take long enough to stop the
feedback loop this change exists to create. Emulation stays registered as a
per-derivation escape hatch, and each use gets written down.

**Vendor stage 1 as an opaque input rather than packaging it.**
Canaan's SPL carries a DDR PHY training blob and a custom image header with
compression. Reimplementing that packaging in Nix was considered and rejected
for now: it is a project in itself, it is not on the path to answering this
change's question, and it can be revisited once anything boots at all. The
seam is declared now so the later work has somewhere to land.

**QEMU is a boot check, not a hardware simulator.**
The runner is a script under `tools/`, not a Nix app, so it stays obviously a
development convenience rather than something later changes might mistake for
a test of the board. Its output is committed under `docs/evidence/`.

**The console is serial at 115200 8N1 in both worlds.**
The board's CH342 gives two CDC-ACM ports at that rate. Matching it under QEMU
means one transcript format, and means the first hardware boot differs from a
known-good QEMU boot in the fewest possible ways.

## Risks / Trade-offs

- **A core package fails to cross-compile and blocks the closure.** → The
  emulation fallback exists precisely for this. If something central fails both
  ways, that is the answer this change was built to surface, and it is reported
  rather than worked around.
- **First build takes long enough to look hung.** → Record the measured
  duration on this host in the repository, so the next person knows the shape
  of normal.
- **QEMU's `k230` diverges from the real SoC.** → Accepted and bounded by
  scope: this change claims only that the closure builds and boots under
  emulation. Nothing here is evidence about the board, and the spec says so.
- **The QEMU and hardware boot paths drift apart.** → Mitigated by keeping the
  stage-1 seam explicit, so the difference is a named boundary rather than an
  accident discovered later.

## Open Questions

- Which nixpkgs revision to pin. Deferrable: it changes what fails to
  cross-compile but not the approach, the specs, or the task breakdown.
- Whether the kernel this change boots under QEMU is a stock nixpkgs riscv64
  kernel or already the Xuantie one. The stock kernel is the cheaper way to
  answer this change's question; the Xuantie kernel is required for hardware
  and belongs to `the-board-boots-what-we-built`. Starting stock and switching
  later costs nothing here.
