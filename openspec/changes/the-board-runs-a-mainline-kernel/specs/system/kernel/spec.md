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
- **THEN** it states plainly that no mainline DSI/VO/canaan-drm driver
  exists, cites the exact file-existence checks that established this, and
  does not claim a porting effort in progress

#### Scenario: A vendor-kernel patch is checked against mainline

- **WHEN** someone asks whether a specific patch in `nix/kernel.nix` applies
  to the mainline build
- **THEN** the inventory names that exact patch, the file it targets, and
  whether that file exists upstream today

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
