## Context

See proposal.md and `docs/research/mainline-kernel-inventory.md` (the full
inventory this design was decided from). Grounding, per
`.skills/k230-spec-change/SKILL.md`'s ordering:

- **File existence in `torvalds/linux`**, checked directly with
  `gh api repos/torvalds/linux/contents/<path>` (200/404) for every
  present/missing driver claim, not inferred from changelogs or Kconfig menu
  text alone.
- **Device-tree contents**, fetched directly from
  `raw.githubusercontent.com/torvalds/linux/master/...` and from the pinned
  tag's tree (`git show v7.2:...`), not summarized secondhand.
- **This project's own existing vendor board file**
  (`nix/dts/k230-tdisplay.dts`) and inventory
  (`docs/research/board-capability-inventory.md`), for every claim about
  what *our* board's console/memory/pinmux already is.

## Goals / Non-Goals

**Goals:** a second, clearly-separate kernel/DTB/boot-files build pinned to
the newest mainline revision with basic K230 support; an honest,
patch-by-patch accounting of which of our eleven vendor-kernel patches port
(answer: none, and why); a phased plan whose first hardware milestone is
named correctly ("reaches the serial console", not "SD rootfs", because SD
is not yet mainlined for this SoC) so a later change is not surprised by
that when it tries to prove it.

**Non-Goals:** booting anything on the board (host-only change, hardware
milestones are explicitly deferred and unclaimed); changing `.#kernel`,
`.#deviceTree`, any `nixosConfigurations` output, or `.#sdImage`; forward-
porting the SDHCI or USB-PHY-DT-node patches (named as the next change's
work, not this one's); attempting the display/audio/RTC/power-key/thermal
driver gap (no upstream starting point exists to port from, and writing one
from scratch is a project-sized effort of its own, explicitly out of scope
here); adding an initramfs/busybox rootfs (named as a cheap next step, not
built here, to keep this change's own build scope to "does it compile").

## Decisions

1. **Pin `v7.3-rc5`, not `v7.2.8` ("latest stable") or a moving `master`.**
   `v7.2.8` is what kernel.org calls "latest stable", but it has zero K230
   support — checked directly (`git show v7.2:arch/riscv/boot/dts/canaan/`
   lists only K210/Sipeed files). Basic K230 support merged for the v7.3
   window; `v7.3-rc5` is the newest tag that exists as of this research,
   pinned by its dereferenced commit hash so the build is reproducible
   rather than tracking whatever `master` happens to be on a later day.
   Rejected: pinning `master` directly (moves under us, defeats the purpose
   of a pin); waiting for a stable v7.3 (unknown timeline, and the
   inventory this change produces is valuable now).
2. **A fully parallel Nix surface, not an `.override` of the existing
   kernel.** `nix/kernel.nix`'s vendor tree and mainline are different
   source trees, different defconfigs (`k230_defconfig` doesn't exist
   upstream), and different Kconfig symbol sets entirely — there is no
   sensible "override" relationship the way `kernel-rvv-trial.nix` overrides
   `kernel.nix` (same tree, same defconfig, one Kconfig+patch delta).
   `nix/kernel-mainline-src.nix` and `nix/kernel-mainline.nix` mirror the
   *shape* of `nix/kernel-src.nix`/`nix/kernel.nix` (a split pin + builder,
   for the same device-tree-without-a-kernel-build reason) without sharing
   any code path with them.
3. **The board `.dts` reuses mainline's own `k230-evb.dts` as its template,
   not `k230-canmv.dts`.** `k230-canmv.dts` wires pinmux groups for buses
   (I2C, SPI, PWM, I2S, a second MMC) that have no matching controller node
   in this pin's `k230.dtsi` at all — copying it would mux pins for
   hardware nothing in this tree can drive, and would invite a false
   impression that this change wired up more than it did. `k230-evb.dts` is
   the minimal, honest template: console + memory + the one two-clock
   `sysclk` override, nothing this SoC/tree combination cannot actually
   back. Our board's memory size (1 GiB, `0x40000000`) is taken from our
   own existing `nix/dts/k230-tdisplay.dts`, not guessed.
4. **`defconfig = "defconfig"`, not a copied/trimmed vendor defconfig.**
   Mainline's own generic RISC-V defconfig is what every other mainline
   RISC-V board uses; inventing a K230-specific one here would be
   maintaining a defconfig fork for no benefit this early, when the actual
   open question is whether the three K230 driver symbols compile against
   this base at all. `autoModules = false` still applies (`nix/kernel.nix`'s
   own reasoning: build what is asked for, not everything nixpkgs' module
   auto-detection can find against a tree this unfamiliar).
5. **No initramfs, no rootfs, in this change.** Getting `.#kernelMainline`
   and `.#deviceTreeMainline` to compile is this change's actual, provable
   deliverable. Building a busybox-based initramfs is a legitimate cheap
   next step (does not wait on any upstream patch, unlike SD/USB) but is
   additional build surface this change does not need to claim its stated
   scope, and is better sized as the first task of the milestone-2 change
   once a board slot is scheduled — it can be built and inspected fully
   under host proof before that board slot is needed, but doing so here
   would blur this change's "does it compile" claim with a second claim
   ("does this rootfs work") that still cannot be checked without a board
   either way.
6. **Every one of the eleven vendor patches gets an individual disposition
   in the inventory, not a summary "none port".** `.skills/k230-spec-change/
   SKILL.md`'s evidence rule applies as much to a negative finding as a
   positive one — "cannot port" is a claim exactly like "ported", and needs
   the same file-existence citation per patch, not one blanket assertion
   covering all eleven. Rejected: writing only the aggregate conclusion,
   which would make a future re-check (once mainline gains, say, an RTC
   driver) have to redo this whole inventory instead of updating one row.

## Risks / Trade-offs

- **An `-rc` pin, not a stable release.** Accepted: the alternative is no
  K230 support at all until an unknown future stable tag. The pin is
  explicit about this (`nix/kernel-mainline-src.nix`'s own header) so a
  later reader does not mistake it for a release-quality target.
- **The board `.dts`'s console-pin assumption is unverified.** Both trees'
  device trees leave UART0 pinmux entirely to U-Boot's FPIOA table (neither
  programs a pinctrl consumer group for it), and our board's existing
  vendor `.dts` already asks for `serial0` as its console the same way —
  but "neither tree touches the mux" is not the same claim as "U-Boot
  configures the pins mainline's UART0 driver expects", and only a board
  boot settles that. Named explicitly as this change's first open hardware
  gate, not asserted as working.
