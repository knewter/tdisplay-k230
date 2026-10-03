## Current evidence status (2026-10-02)

The original host milestones below are historical build records. Committed
physical trials in
`docs/evidence/mainline-display/physical-2026-10-01/README.md` observe Linux
7.3-rc5, DRM/fb0, Goodix input registration and photographed panel boot text,
but no usable mainline root or deliberate touch. Later PID1 shell probes
reached `/bin/true`; the minimal trial's systemd reboot refusal did not reach
the kernel. The protected normal system was independently restored by an
operator power cycle, recorded in
`docs/evidence/mainline-display/physical-2026-10-01/minimal-probe-recovery-2026-10-02/README.md`.
These are partial boot/probe/recovery observations, not product acceptance.
Task 5d.4 now has physical proof for the targeted five-clock candidate
without `clk_ignore_unused`: ordinary clock cleanup, kernel restart → SPL →
protected normal return with fresh identity and unchanged boot hashes,
recorded in `docs/evidence/mainline-sd1-clocks/physical-no-flag-2026-10-03/README.md`.
The earlier global-clock comparison remains historical evidence. Task 5b.5
stays open for ordinary NixOS root activation and deliberate touch.

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

**Original non-goals (superseded by the later bounded continuations):**
booting anything on the board (initially host-only, with hardware gates
deferred); changing `.#kernel`,
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
5. **No initramfs, no rootfs, in this change's ORIGINAL scope.** Getting
   `.#kernelMainline` and `.#deviceTreeMainline` to compile was that
   scope's actual, provable deliverable, and building a busybox initramfs
   was deliberately deferred as a separate, later task.

   **Superseded, task group 5**: the coordinator directed continuing this
   same change into the actual boot-critical porting ("do the actual
   porting ... so it can mount our SD rootfs", after merging `c5158fa8` to
   master) rather than opening a fresh change for it. Rather than a
   from-scratch busybox initramfs, task group 5 forward-ports real
   GPIO/SD-MMC/USB drivers so the system's OWN NixOS-generated initrd (the
   same mechanism `nix/sd-image.nix` already uses for the vendor image)
   can do the real work — switch-root onto the SD card's existing,
   already-populated ext4 root partition — rather than substituting a
   toy ramdisk rootfs that would prove less and still need replacing
   later. This is a strictly larger, more capable deliverable than the
   minimal initramfs originally sketched, not a smaller one.
6. **Every one of the eleven vendor patches gets an individual disposition
   in the inventory, not a summary "none port".** `.skills/k230-spec-change/
   SKILL.md`'s evidence rule applies as much to a negative finding as a
   positive one — "cannot port" is a claim exactly like "ported", and needs
   the same file-existence citation per patch, not one blanket assertion
   covering all eleven. Rejected: writing only the aggregate conclusion,
   which would make a future re-check (once mainline gains, say, an RTC
   driver) have to redo this whole inventory instead of updating one row.

7. **Forward-port the vendor's exact `ctl-reg`/`dwc2_set_k230_params()` USB
   mechanism, not mainline's own separately-accepted
   `phy-k230-usb.c`/`canaan,k230-usb-phy` generic-PHY-framework driver.**
   Both exist for the same HiSysConfig USB control registers at
   `0x91585000`+; they are not interoperable (different init sequences,
   different DT binding shape — `phys`/`#phy-cells` vs. a bare `ctl-reg`
   property). The vendor's mechanism is what this board's own working
   image already runs; the upstream PHY driver has never been exercised
   against this board by anyone, as far as this research found. Rejected:
   wiring the "more upstream-correct" phy-framework driver instead, which
   would mean debugging TWO unproven things at once (a new PHY driver AND
   a new DT binding) on the very first hardware attempt, rather than one.
8. **`k230-mainline-console`, not the coordinator's suggested
   `k230-coherent-shell-mainline`.** The coordinator's own instruction
   named this as an example ("e.g."), not a requirement. Extending
   `k230-coherent-shell` would pull in Sway/wlroots wanting a DRM/KMS
   device (`/dev/dri/card0`) that does not exist under mainline at all
   (no `canaan-drm` — see the inventory), so the build would either fail
   outright on a missing dependency or succeed into a system whose shell
   service cannot ever start, silently misrepresenting what this milestone
   reaches. `k230-console` (shell off, already the deliberately minimal
   variant `system/nixos-config` requires) is the honest base. Flagged
   explicitly rather than silently substituted.
9. **`boot.extraModulePackages`/`boot.kernelModules` force-cleared, not
   left alone.** `nix/hardware.nix`'s `k230WifiDriver` builds the
   out-of-tree RTL8189FTV module against `config.boot.kernelPackages.kernel`
   dynamically and unconditionally (not gated by `k230.shell.enable`), so
   swapping the kernel without addressing this would have tried to compile
   a driver written against 6.6-era vendor headers against a v7.3-rc5
   kernel seven major versions newer, most likely failing the entire
   system build. There is also no SDIO DT node enabled for it to bind to
   in this milestone regardless (`&mmc_sd0` stays disabled — see the
   inventory table's Wi-Fi row). `lib.mkForce [ ]` on both options, plus
   forcing the always-instantiated `k230-wifi` systemd service off, is the
   narrowest fix that keeps the toplevel buildable; the module itself is
   simply never evaluated as a build target once `mkForce` wins the
   option merge (`k230WifiDriver`'s `let`-bound derivation is never
   forced).
10. **Boot files carry no hardcoded `root=` device path.** The system's
    `fileSystems."/"` (inherited unchanged from `nix/hardware.nix`) is
    `{ device = "/dev/disk/by-label/NIXOS_SD"; fsType = "ext4"; }`, and
    `nix/sd-image.nix`'s own `rootfsImage` is built with exactly that
    volume label — so the vendor image's own proven boot flow already
    resolves root by ext4 label through the initrd's generated fstab, not
    a raw device node, and its own `bootargs` construction carries no
    `root=` override either. `nix/kernel-mainline-boot-files.nix` copies
    that same construction. Rejected (and actually shipped once, then
    corrected before this change's evidence was recorded): hardcoding
    `root=/dev/mmcblk0p2` — a guess about MMC enumeration order that the
    label mechanism makes entirely unnecessary, and that would have
    silently fought the `root=fstab` token NixOS's own `kernelParams`
    already contributes.

11. **RTC ported as a small, real proof the methodology generalizes; the
    full DRM display stack scoped but NOT ported, and NOT left half-done
    in the committed tree.** After milestone 1, the same "copy the vendor
    file, build, fix what the compiler names" methodology was applied to
    the smallest, most self-contained item in the coordinator's milestone
    3 (RTC) as a genuine additional deliverable, and to the coordinator's
    milestone 2 (display) as scoping only. RTC built cleanly after one
    trivial fix; the display stack's very first file hit a structural DRM
    allocation-model change (`drm_panel_init()` → `devm_drm_panel_alloc()`)
    after two Kconfig fixes, and porting all ~3,900 lines plus re-applying
    this project's own ~10 existing panel/DSI/VO patches on top is a
    materially larger, multi-file, actively-churned-subsystem task than
    anything attempted so far. Rejected: continuing to force a
    build-error-driven port of the whole display stack within this same
    pass, which risked either running out of budget mid-port (leaving
    `.#kernelMainline` broken, violating this change's own spec
    requirement that it stays buildable) or producing a large amount of
    code no one could verify compiles cleanly, let alone runs correctly,
    within this session. The scratch trial was reverted
    (`git checkout -- nix/kernel-mainline.nix`, the trial's
    `nix/patches/mainline/drm/` directory deleted) rather than committed
    as WIP, matching the project's own convention that a task group ends
    with the command that proves it — an unbuildable derivation proves
    nothing.

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
- **Two real vendor-tree-to-mainline API migrations were needed for
  GPIO/SD-MMC, found only by a failed build, not by inspection.**
  `struct gpio_chip`'s generic-chip fields (`bgpio_init()`/`.read_reg`/
  `.write_reg`/`.bgpio_lock`) were replaced by `struct gpio_generic_chip`
  sometime after this file's 6.6-era vendor origin, and
  `sdhci_pltfm_free()` was removed outright. Both were fixed against
  mainline's own already-migrated reference drivers
  (`gpio-dwapb.c`/`sdhci-of-dwcmshc.c`), not guessed — but this is a real
  signal that forward-porting a 6.6-era file onto a v7.3 tree is not a
  mechanical copy in general, only in the specific cases checked here.
  USB's `dwc2/{params.c,core.h,core.c}` hunks happened to need no such
  migration (confirmed by a clean build), but that is a fact about this
  one function/struct pair, not a general property of the USB subsystem;
  a future forward-port (touch's I2C plumbing, say) should expect to hit
  the same class of problem and budget for it.
- **The clock-gate and reset IDs chosen for GPIO/SD-MMC/USB in
  `nix/dts/k230-tdisplay-mainline.dts` are a best-effort mapping from ID
  names alone** (e.g. `K230_HS_SD0_BASE_GATE` for the SDHCI functional
  clock, `K230_HS_SD0_AHB_GATE` for the register-bus clock), not confirmed
  against any vendor clock-tree documentation or working configuration.
  They are syntactically valid and let each driver's mandatory `clk_get`
  calls succeed at probe time, which is as far as a host build can check.
  Wrong gate/reset selection would surface as a probe failure or a
  hung/misbehaving peripheral on the board, not a build failure — squarely
  the first hardware milestone's job to find, not this one's.

## Follow-up: isolated DRM display continuation

The original task 5a.2 records why the first milestone-3 display trial was
reverted. The coordinator later authorized continuing that port as a
separate, opt-in `kernelMainlineDrm` derivation. Its DRM, DSI, universal
panel, and LT9611 sources live under `nix/patches/mainline/drm/`, copied
from the vendor-derived working port and kept out of `kernelMainline` and
all default outputs. The pin is still Linux v7.3-rc5; this does not change
the kernel source pin or claim that pin is the latest kernel.org release.

The first source/API increment replaces removed generic fbdev setup with
the pinned tree's DMA fbdev/client API, updates the changed atomic helper
and platform remove signatures, and removes `drm_driver.date`. The exact
prepared-header external-module result is in
`docs/evidence/mainline-display-api-compile.md`. This is useful compiler
feedback, but the unresolved modpost symbols mean it is not a complete
in-tree kernel build. The opt-in `deviceTreeMainlineDrm` source and matching
`kernelMainlineDrmBootFiles` collector now exist. Host cpp/dtc/round-trip
proof is recorded in `docs/evidence/mainline-display-dtb.md`. The full kernel,
DTB, and boot-files derivations now build successfully; their paths and the
first link failure/correction are recorded in
`docs/evidence/mainline-display-nix-build.md`. The initial host candidate omitted the vendor display power domain because
the pin has no upstream `sysctl_power` provider; the locally forward-ported
continuation below addresses that source gap. Physical probe, panel, and
touch behavior remain open tasks.


## Matching DRM trial boot path

`k230-mainline-drm-trial` extends the mainline console profile with the
separate DRM kernel, retaining its disabled out-of-tree Wi-Fi module and
label-based root configuration. It supplies the candidate's own NixOS
initrd and exact system `init=` path through
`kernelMainlineDrmTrialBootFiles`. The recipe writes both DTB bootargs and a
volatile U-Boot environment import file because the vendor stage 1 can
overwrite DTB bootargs (`nix/sd-image.nix` and
`docs/evidence/hardware-boot.txt`). The root-stage procedure copies the exact
closure beside the normal system and leaves its selected profile and normal
boot files untouched. The Image+DTB-only collector remains available.

Rejected: pairing the DRM Image with an arbitrary existing initrd/system or
changing the normal card's boot selectors. These hide the kernel/system
boundary or undermine the recoverable trial. Host build and artifact matching
are recorded in `docs/evidence/mainline-display-boot-preparation.md`.
The committed October 1/2 records now establish card staging, partial
boot/probe/photographed boot text, and distinct protected normal recovery;
usable mainline root and deliberate touch remain unperformed.


## Optional DRM power-domain continuation

Layer: kernel genpd provider, candidate DRM runtime PM, and candidate device
tree. Forward-port `drivers/soc/canaan/k230-power-domains.c` and
`include/dt-bindings/soc/canaan,k230_pm_domains.h` from the pinned vendor
revision `7d4e1f444f461dbe3833bd99a4640e7b6c2cd529`. Preserve the full five-domain
one-cell ABI, register offsets, enable/write-enable bits and AI repair logic.
Use per-device state, checked genpd registration with partial-failure cleanup,
and omit unused hardlock variables/property reads: the vendor reads them but
never uses them. Keep the vendor controller compatible string on both sides.
Only the DRM candidate selects the provider and adds its DT binding header.

The existing DRM master already pins DISP at probe, before modesetting. Use a
checked runtime-PM acquisition, keep that reference throughout successful
binding, and release it on probe failure/removal. The logical display master
receives the vendor DISP domain; VO/DSI clock/reset wiring stays as before.
The prior board observation in `docs/evidence/dsi-phy-hang.md` establishes why
this boundary matters. It does not prove the new provider executes correctly
under the mainline pin. Host proofs and the exact source changes belong in
`docs/evidence/mainline-display-power-domain.md`.

Rejected: relying on U-Boot to leave DISP powered (not a maintained runtime
reference), claiming an initrd change fixes power (it does not), changing the
console/default kernels, or guessing new clock/reset mappings. The complete
candidate kernel, DTB and matching trial bundle must build before handoff;
the physical serial/panel/touch/normal-restoration gate remains unchecked.


## Optional DRM restart continuation (group 5d)

Layer: optional kernel reset driver and Nix patch application. Grounding is
the committed restart source audit and the read vendor
`drivers/reset/reset-k230.c` at
`7d4e1f444f461dbe3833bd99a4640e7b6c2cd529`. Its restart callback writes
bits 0 and 16 to `SYSCTL_BOOT_BASE_ADDR + CPU0_RST_CTL`
(`0x91102000 + 0x60`), then waits indefinitely; its probe registers a
priority-128 restart notifier. The normal vendor boot transcript records
restart reaching U-Boot SPL. Mainline's `canaan,k230-rst` controller instead
implements peripheral reset operations only. The boot-control register is
outside its reset-controller resource; do not reinterpret the peripheral
CPU0 reset ID as the system restart operation.

Forward-port only that restart sequence alongside mainline's existing reset
implementation in the separate DRM derivation. Map the vendor-defined four
bytes at probe time with managed lifetime; check mapping and restart
registration failures. Use `devm_register_sys_off_handler()` with
`SYS_OFF_MODE_RESTART` and vendor priority 128, preserving the ordering while
adapting the callback to `struct sys_off_data`. The pinned
`include/linux/reboot.h` declares this API; the convenience
`devm_register_restart_handler()` fixes the priority to zero, so it would
change the vendor ordering. Keep the vendor write mask and terminal wait,
with `cpu_relax()` in the wait. Do no allocation or mapping inside the
atomic restart callback. Managed actions unregister the handler before its
mapping and per-device state are released on failed probe or removal.
Register only after the peripheral reset controller has registered, checking
all results. No DT change is needed if this vendor-defined mapping is
available independently of the existing peripheral resource.

Rejected: an initrd script writing registers (bypasses the kernel recovery
boundary), direct SBI SRST calls without advertised support, changing loaded
OpenSBI/stage 1 in the same increment, borrowing a different platform's reset
handler, or inferring restart success from a built object or the systemd
refusal. This write's physical behavior under the mainline kernel remains
UNVERIFIED. Preserve the existing usable-root/display/touch gate 5b.5.

First compile the changed reset object against the exact pinned prepared
headers and evaluate/apply the optional Nix source patch. Then, under the
single shared build slot, build `.#kernelMainlineDrm`, build and inspect its
matching `.#kernelMainlineDrmTrialBootFiles`, and compare default and
console-only derivation identities to the base revision. Only the operator
may perform the recoverable physical trial: preserve a serial log showing a
kernel reboot request reaching stage 1 and a fresh normal boot identity,
protected normal hashes and shell postflight. A systemd refusal is a failed
prerequisite; an operator power cycle records recovery but does not prove
mainline automatic restart. The actual controller invocation and artifact
identity must accompany that physical evidence.


## Finite opt-in kernel boot-boundary diagnosis (2026-10-03)

Following the bounded serial-only and retained-SBI trials, add a separate
`kernelMainlineBootTrace` derivation and matching ordinary-init system/bundle.
The current DRM/restart/five-clock source remains its base; existing kernel,
console, observer and default outputs stay unchanged. The optional system
removes exactly tty0 from the base console arguments and adds
`k230.boot_trace=1`, with no retained boot console or clock bypass. Keep the
ordinary controller's qualified controls and identity/protected recovery gates.

Use fixed paired markers around basic setup/initcalls, initramfs readiness,
root-console opening, init accessibility/namespace, integrity keys, async
completion, initmem/readonly cleanup and init exec. Enable only the exact
runtime value 1; disabled calls have no output/emergency side effect. Keep the
helper/state outside freed init sections and cap output at 32 public records.
Briefly enter nbcon emergency state for each individual printk, then leave it
before the bracketed work. This can perturb flushing and a marker can itself
block; an enter-only marker is a last visible boundary, not a stack or cause.
Namespace and fallback-exec markers preserve the original conditional paths.

Host proof is in
`docs/evidence/mainline-system-trial/boot-boundary-host-2026-10-03.md`.
Full matching kernel/artifact proof and operator-controlled physical output,
ordinary root/login, automatic recovery and real touch remain UNVERIFIED.
This diagnostic increment preserves task 5b.5 and all existing acceptance
requirements; it adds no shipped capability.
