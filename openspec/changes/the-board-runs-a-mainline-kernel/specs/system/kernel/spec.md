## ADDED Requirements

### Requirement: A parallel mainline kernel build exists and does not affect the default system

The project SHALL provide a mainline-Linux kernel, device-tree, and
boot-files build (`.#kernelMainline`, `.#deviceTreeMainline`,
`.#kernelMainlineBootFiles`) pinned to the newest mainline revision carrying
basic Canaan K230 support, built entirely separately from the pinned vendor
Xuantie kernel `.#kernel` uses. No existing package, `nixosConfigurations`
output, or `.#sdImage` SHALL depend on or be changed by this build existing.

*Grounding: `nix/kernel-mainline-src.nix` pins `torvalds/linux` at the
dereferenced `v7.3-rc5` commit — the newest tag with
`arch/riscv/boot/dts/canaan/k230.dtsi` present, confirmed absent at `v7.2`
by direct tag diff. `nix/kernel-mainline.nix` and
`nix/device-tree-mainline.nix` share no code path with `nix/kernel.nix` or
`nix/device-tree.nix`; `flake.nix`'s new `kernelMainline`/
`deviceTreeMainline`/`kernelMainlineBootFiles` outputs are additive only.*

#### Scenario: Someone builds the mainline kernel

- **WHEN** someone runs `nix build .#kernelMainline`
- **THEN** it exits 0 and produces a riscv64 kernel Image, independent of
  whether `.#kernel` has ever been built

#### Scenario: Someone builds the default system

- **WHEN** someone builds `.#nixosConfigurations.k230.config.system.build.toplevel`
  or `.#sdImage`
- **THEN** the result is byte-identical to what it would be if
  `nix/kernel-mainline.nix`, `nix/kernel-mainline-src.nix`,
  `nix/device-tree-mainline.nix`, and this change's other new files did not
  exist

### Requirement: A parallel full system variant boots the mainline kernel without changing the default system

The project SHALL provide a full NixOS system variant
(`nixosConfigurations.k230-mainline-console`) that substitutes the
mainline kernel for the vendor kernel via the same `k230Kernel` specialArg
substitution mechanism the existing `k230-rvv-trial` variant already uses,
built from the shell-off `k230-console` base rather than the graphical
`k230-coherent-shell` base, and SHALL exclude any out-of-tree kernel module
that is not expected to compile against the mainline pin. No existing
`nixosConfigurations` output SHALL be changed by this variant existing.

*Grounding: `flake.nix`'s `k230-mainline-console` extends `k230-console`
with `specialArgs.k230Kernel = self.k230MainlineKernel` and force-clears
`boot.extraModulePackages`/`boot.kernelModules` (the out-of-tree RTL8189FTV
module `nix/hardware.nix` builds against `config.boot.kernelPackages.kernel`
dynamically, with no reason to expect it compiles against a v7.3-rc5 API
seven major versions newer than its 6.6-era vendor origin, and no SDIO DT
node enabled for it to bind to regardless). Proven:
`nix build .#toplevel-mainline-console` exits 0, producing
`/nix/store/d488a1cibw8r7ip7hbbb9j52hy0kzb0h-nixos-system-nixos-26.11.20260919.20b1ddd`.
Deviates from the coordinator's suggested "-shell-" name for the reason
above; flagged rather than silently decided.*

#### Scenario: Someone builds the mainline system variant

- **WHEN** someone runs `nix build .#toplevel-mainline-console`
- **THEN** it exits 0 and produces a NixOS system closure built against
  `kernelMainline`, independent of whether any other `nixosConfigurations`
  output has ever been built

### Requirement: The mainline build's hardware ceiling is recorded, not assumed

The project SHALL record, per hardware function, whether mainline Linux at
the pinned revision can drive it, citing direct file-existence or
device-tree-content checks rather than changelog summaries. Hardware
functions with no mainline driver SHALL be recorded as blocked rather than
silently omitted, and any of this project's own vendor-kernel patches that
cannot be forward-ported to mainline SHALL be recorded individually with the
reason, not summarized as a single negative finding.

*Grounding: `docs/research/mainline-kernel-inventory.md`'s Inventory table
(each row cites `gh api repos/torvalds/linux/contents/<path>` returning 200
or 404) and its per-patch disposition list (all eleven vendor-kernel patches
checked individually; ten target files absent upstream, one already fixed
upstream independently, none require porting as a patch today).*

#### Scenario: Someone asks whether mainline can drive the display

- **WHEN** someone reads `docs/research/mainline-kernel-inventory.md`'s
  panel row
- **THEN** it states that the pinned upstream tree had no DSI/VO/Canaan
  DRM drivers at the time of the inventory, cites the exact file-existence
  checks, and points to the separately tracked `kernelMainlineDrm`
  continuation without claiming that continuation is complete

#### Scenario: A vendor-kernel patch is checked against mainline

- **WHEN** someone asks whether a specific patch in `nix/kernel.nix` applies
  to the mainline build
- **THEN** the inventory names that exact patch, the file it targets, and
  whether that file exists upstream today

### Requirement: Forward-ported drivers are grounded in the vendor tree and checked against the pinned mainline API

Where this project forward-ports a vendor-tree driver onto the mainline
pin so a boot-critical function (GPIO, SD/MMC, USB) is available, the
ported file or hunk SHALL be traceable to its exact vendor-tree origin by
path, and any API difference between the vendor tree's kernel version and
the pinned mainline revision that required a code change (not just a
Kconfig/Makefile wiring change) SHALL be recorded with what changed and
how it was confirmed, rather than silently patched around.

*Grounding: `nix/patches/mainline/gpio-k230.c` and
`nix/patches/mainline/sdhci-of-kendryte.c` are forward-ported from
`ruyisdk/linux-xuantie-kernel` @ `7d4e1f444f461dbe3833bd99a4640e7b6c2cd529`;
`nix/kernel-mainline.nix`'s postPatch carries the `drivers/usb/dwc2/
{params.c,core.h,core.c}` hunks from the same tree. Two real API
migrations were found and fixed this way, each only after a failed build
named the exact missing symbol: `struct gpio_chip`'s `.read_reg`/
`.write_reg`/`.bgpio_lock` and `bgpio_init()` were replaced upstream by
`struct gpio_generic_chip`/`gpio_generic_chip_init()`
(`include/linux/gpio/generic.h`), confirmed against mainline's own
already-migrated `gpio-dwapb.c`; `sdhci_pltfm_free()` was removed upstream
entirely, confirmed against mainline's own `sdhci-of-dwcmshc.c`, whose
probe error paths and `.remove` call no equivalent function.*

#### Scenario: A forward-ported driver fails to compile against the pinned mainline API

- **WHEN** `nix build .#kernelMainline` fails with an unknown-symbol or
  missing-member compiler error in a forward-ported file
- **THEN** the fix is recorded against the exact API change found, citing a
  mainline reference file that already uses the new API, not a guess

### Requirement: A mainline hardware boot is a named, unclaimed evidence gate

Reaching a mainline-booted serial console, rootfs, or any further hardware
milestone on the physical board SHALL be treated as hardware evidence, never
inferred from a successful cross-build. A change that only cross-builds the
mainline kernel/device-tree SHALL say so explicitly and SHALL NOT claim any
hardware milestone until a board console transcript exists.

*Grounding: this change's own `tasks.md` "Remaining evidence gate" section
names the exact operator command
(`flock /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0
--wait=10`) and the manual U-Boot `ext4load` steps it depends on, without
performing them.*

#### Scenario: Someone asks if the mainline kernel boots on the board

- **WHEN** someone asks whether `.#kernelMainline` has booted on the T-Display-K230
- **THEN** the answer cites a committed board console transcript under
  `docs/evidence/`, or states plainly that none exists yet

### Requirement: A mainline display port remains isolated and evidence-bounded

The project MAY provide an opt-in mainline DRM candidate, but it SHALL
remain a separate derivation from the console-only `kernelMainline` and
SHALL NOT change the vendor kernel, default device tree, system
configuration, or image outputs. Source/API checks, complete kernel builds,
DTB checks, and physical display/touch observations SHALL be recorded as
distinct evidence; one class SHALL NOT be described as proof of another.

*Grounding: `nix/kernel-mainline-drm.nix` builds the copied Canaan DRM/DSI,
RM69A10 panel, and LT9611 code as a separate override of
`kernelMainline`. `nix/device-tree-mainline-drm.nix` and the separate
`kernelMainlineDrmBootFiles` output pair the candidate DTB/Image without
changing default outputs. `docs/evidence/mainline-display-api-compile.md`,
`docs/evidence/mainline-display-dtb.md`, and
`docs/evidence/mainline-display-nix-build.md` record the prepared-header
external-module, host DTS, and complete Nix kernel/DTB/boot-files checks,
with their limits and the absent hardware results.
`docs/evidence/mainline-display-boot-preparation.md` records the matching
opt-in trial system/initrd/bootargs and closure inventory, and the unperformed
root staging and recoverable U-Boot procedure. The DRM driver sources in the pinned
upstream source output are absent; this candidate forward-ports them from
the vendor-derived implementation. The initial candidate omitted display power-domain wiring because the
pinned source has no provider; the DRM-only local provider continuation
remains gated by separate source/build and physical runtime evidence.*

#### Scenario: Someone builds the console-only mainline kernel

- **WHEN** someone runs `nix build .#kernelMainline`
- **THEN** the optional DRM candidate does not modify that kernel or its
  existing console boot-files/DTB outputs

#### Scenario: Someone asks whether the DRM candidate drives the panel

- **WHEN** the complete derivation builds, prepared-header object check, and
  DTB round-trip are available, but no physical observation exists
- **THEN** the answer reports those host results and leaves board probe,
  display power, panel illumination, and touch behavior unverified
