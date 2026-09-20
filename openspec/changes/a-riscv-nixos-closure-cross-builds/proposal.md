## Why

Nothing this project wants to run — AtomVM, the Dozer core, anything with a
screen — can be built until something can build riscv64 at all. `riscv64-linux`
is community-tier in nixpkgs with **no binary cache**, so a NixOS closure for it
is compiled rather than downloaded, and whether that succeeds on the machine we
have is unknown.

It is worth answering that first and separately, because it needs no hardware.
QEMU 11.1 ships a `k230` machine, so an image can be built and booted in a loop
on a laptop while the board sits in a drawer. If a riscv64 closure turns out not
to cross-build cleanly, every later plan changes, and we would rather learn that
now than after a soldering iron is involved.

## What Changes

- **A flake that cross-compiles a minimal riscv64 NixOS system from x86_64.**
  Cross-compilation is the default path, not emulation: `binfmt` with
  `qemu-riscv64` is registered on the build host and stays as the fallback for
  derivations that refuse to cross.
- **That system boots under `qemu-system-riscv64 -machine k230` to a console
  prompt**, with the boot recorded as committed evidence.
- **The stage-1 seam is drawn now, before it is needed.** BootROM, U-Boot SPL
  with its DDR training blob, U-Boot and OpenSBI are declared vendored from the
  outset, so the flake never grows an accidental dependency on building them.
  Under QEMU nothing occupies that seam; the point is that the shape is right
  when `the-board-boots-what-we-built` fills it.
- **What refuses to cross-compile is written down.** A list of packages that
  fail, and which needed emulation, is the useful output of this change even if
  everything else goes smoothly.

**Non-goals.** The physical board. The panel, touch, or either radio — QEMU's
`k230` models none of them, so claiming any would be unfounded. AtomVM, the
Dozer core, or any choice of shell. A pleasant or minimal closure size; this
one only has to boot.

## Capabilities

### New Capabilities

- `image/cross-build`: producing riscv64 artifacts on an x86_64 host, and what
  is done when something will not cross.
- `system/nixos-config`: what the NixOS system for this board contains and what
  it guarantees on boot.

### Modified Capabilities

None. This is the first change in the repository.

## Impact

Adds `flake.nix` and a `nix/` tree at the repository root. Adds a QEMU runner
under `tools/`. No existing code is touched; `tools/` currently holds only
serial and USB helpers, which this does not disturb.

Build host requirements: an `x86_64-linux` Nix with flakes, and `binfmt`
`qemu-riscv64` registered for the emulation fallback. Both are present on the
development machine.
