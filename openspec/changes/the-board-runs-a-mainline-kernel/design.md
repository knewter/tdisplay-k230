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

## Finite independent UART/IRQ progress diagnosis (group 5f)

Layer: optional kernel source/configuration and matching Nix system/bundle;
reserved operator/controller evidence. The physical Bash prompt followed by
zero receipt replies grounds this diagnostic boundary. The committed source/DT
receipt compares eight exact files and thirteen properties, not whole kernels
or runtime equivalence. Pinned source `26hzn5…` locates RX accounting/filtering
in `8250_port.c:1627–1690`, actual timer IRQ mapping in
`timer-riscv.c:167–183`, and thread-context aggregate IRQ accounting in
`irqdesc.c:1066–1073`. Linux IRQ numbers must come from those live bindings;
PLIC source 16 is not a guessed Linux IRQ number.

A separate runtime opt-in creates one normal-priority kernel thread from late
init, with at most six samples and finite sleeps over approximately thirty
seconds. No priority/affinity/tick-policy change or RT/busy loop. State, worker
and static aligned/page-contained output buffers must survive init cleanup.
Disabled mode starts no observer and has no output side effect.

A narrow internal 8250 snapshot validates line0, selected device/mapbase and
hardware interrupt binding; it does not misuse the runtime-PM-only
`serial8250_get_port()` interface. Protect registration/removal lifetime with
nonblocking acquisition, then make one port try-lock attempt and copy only
cached RX/TX/error/failed-flip counts, IER/read/ignore masks and uartclk. Mark
busy/unavailable/changed binding explicitly, without waiting or dereferencing
a stale device. Obtain UART/timer IRQ aggregate counters through safe live
identity and thread-context APIs. Release all locks before formatting or a
single SBI write; no printk/emergency fallback, retry, MMIO or register writes.
Buffer/format/frame count and page bounds require actual target object proof.

Records contain fixed version/sample/state and numeric public fields, no raw
addresses, proc text, UUIDs, private data or credentials. Reporter sequence
proves scheduling; jiffies/ktime are timekeeping observations. Actual timer IRQ
increments show accounted interrupts, which may be caused by the reporter's
own wakeups. RX increments count 8250-processed RX/break handling, including
synthesized break handling without a data byte; they do not prove a physical
FIFO read per increment or successful TTY/Bash delivery. Failed-flip counts
do not prove successful Bash reads. UART IRQ growth may
include shared/spurious activity. Absence, busy state or a missing final record
is unknown, not a timer/UART fault or proof that the last firmware call returned.
Finite sample count is not a guaranteed wall-clock bound if sleep/SBI stalls.

The matching controller retains shell PID1, async=0, marker suppression, sole
console and existing three controls. It sends at most one qualified fresh
builtin receipt stimulus, then captures bounded passive records, preserving
partial/duplicate/missing/unknown results. No command or reboot after unknown.
Require fresh protected normal preflight and independent postflight/operator
recovery; records and heartbeat never supply recovery or ordinary-root proof.

Rejected: another blind shell retry, a systemd-dependent observer before
systemd startup, IRQ/PID1-path output, guessed MMIO/mapping fixes, TTY poll
(`n_tty.c:2443` flushes work), and first-probe TIOCINQ (`2488–2494` takes a
semaphore). These change or depend on the boundary being investigated.
Diagnostic timing can perturb progress; a successful trial alone is not a
production fix. Existing default/console/diagnostic output identities remain
unchanged; only a new named kernel/system/bundle is eligible for this probe.


## Worker-entry and first-post-sleep breadcrumbs (group 5g)

Layer: separate optional kernel reporter source and matching Nix outputs,
followed by a separately reviewed typed host-controller selection. Physical
zero-report grounding is the finite packet in
`docs/evidence/mainline-uart-progress/physical-2026-10-03/README.md` and its fixed
result. It establishes exact candidate arguments, Bash prompt, one stimulus,
no receipt and no complete report, not an IRQ/timer fault. DBCN detection is
availability detection only. The actual selected source
`4av3w0kigacwah6w04zfpnky4gsh0k59` places the first sleep at
`drivers/soc/canaan/k230-uart-progress.c:37–43`, snapshot/time formatting at
43–65 and the single sample write at67. Worker creation follows the runtime
and DBCN gates at72–78. The initial visible output therefore conflates worker
scheduling, sleep/wakeup, snapshot and firmware progress.

### Frozen bounded comparison

Add only a new layered source/kernel family, tentatively
`kernelMainlineUartProgressBreadcrumbs`, optional configuration
`k230-mainline-uart-progress-breadcrumbs`, toplevel/trial bundle and
`kernelMainlineUartProgressBreadcrumbsExactObjects`. Layer over the existing
reporter source rather than changing its recipe or C file. Keep all existing
package derivations, kernel source/config identities, ordinary trial families
and default system/image identical to the landed baseline. Inherit the original
serial-only ordinary-init artifact parameters with both trace tokens; add no
runtime reporter/breadcrumb flag to the artifact. Matching selected kernel.dev
headers, actual config, source layering and complete hardware DT identity after
only chosen bootargs removal require distinct host proof.

The new setup flag is exact `k230.uart_progress_breadcrumbs=1`; absent, bare or
invalid values retain the original six-sample behavior without breadcrumbs.
The existing exact `k230.uart_progress=1` remains required to start the worker,
and existing CONFIG_RISCV_SBI/DBCN availability gates still apply. Setup code
alone is init-lifetime; helper/flag and two aligned static const byte strings
use ordinary lifetime. Each string is at most64 bytes, aligned64 and contained
within an actual configured 4KiB page, never a stack/VMAP_STACK or freed init
buffer. Call exactly once per point, passing literal length excluding NUL.
No formatting, printk/emergency, retry, fallback or counter query is added.

Fixed wire bytes (leading and trailing newline; the backslashes below denote
those literal LF bytes):

```text
\nK230_UPB1 point=worker-entry\n
\nK230_UPB1 point=first-post-sleep\n
```

Worker-entry occurs only on sample0 after the existing first stop check and
immediately before its `msleep(5000)`. First-post-sleep occurs only on sample0
after that sleep and the existing second stop check, immediately before the
cached snapshot. Both execute solely in the normal-priority worker and outside
all snapshot locks. No IRQ, TTY, PID1/init, priority/affinity/tick change is
permitted. Six existing samples, format/state semantics, stop checks and delay
sequence remain unchanged. The whole worker attempts at most eight SBI writes:
two breadcrumbs plus six samples. Firmware results are deliberately discarded.
One invocation is not a wall-clock firmware bound; sleep/scheduling may stall.
The write API in the same source's `arch/riscv/kernel/sbi.c:591–617` performs an
availability check, static-buffer physical conversion, page clamp and one ECALL;
full/partial/zero/error returns do not trigger a second attempt.

### Strict controller and interpretation boundary

A separate explicit `--uart-progress-breadcrumbs` selector requires minimal
mode plus `--same-image-shell-pid1 --uart-progress`. It qualifies the new exact
manifest/kernel/dev/source/ordinary artifact policy before UART, preserves the
same async=0, marker suppression, rdinit/Bash and three qualified controls, and
adds only the exact new volatile gate alongside the existing reporter gate.
Existing modes and numeric sample parsing remain unchanged. Protected normal
pre/postflight and registration-absence checks remain mandatory.

Accept each of the two exact complete breadcrumb lines at most once; reject
unknown versions/points, extra fields, duplicates, reordered observed points,
truncation, echo/stale lines and inserted kernel text. Preserve raw private
bytes; do not strip printk or repair a split marker. Retain the whole bounded
fresh boot phase so early direct output is not lost merely because printed
kernel banners lag. Associate records only after fresh selected Linux/received
argument qualification for that boot attempt; old buffers or an unqualified
prompt do not establish freshness. Breadcrumbs never authorize input. The one
receipt stimulus still requires the existing fresh init-entry/primary-prompt
and exact received arguments; afterward input remains stopped, including when
receipt or any record is unknown. No candidate reboot is added.

Report breadcrumb presence/completeness separately from receipt and the six
numeric samples. Host arrival before/after stimulus is not per-byte RX timing.
Entry alone proves worker reach to the entry output call, not return from it,
sleep completion or failure location. First-post-sleep proves the first sleep
and both stop checks passed and the earlier entry call returned, not that its
output was complete. A later sample proves progress past the post-sleep call
and snapshot/formatting, not firmware count, healthy RX or Bash delivery.
Missing entry/wake/sample may reflect scheduling, blocked/failed/partial output
or later work; none alone identifies a cause. Missing/malformed breadcrumbs
remain incomplete/unknown even if numeric samples or protected recovery appear.
Automatic return and independent protected operator recovery remain separate.

Rejected: another identical sleeping-worker retry; dropping its first sleep;
IRQ/PID1/TTY instrumentation; a printk/earlycon fallback; polling/retry; and
loosening existing parsers to remove arbitrary console text. These introduce
additional dependencies or change the boundary being compared. Source/object,
full build, typed protocol and physical proof tasks stay distinct. Diagnostic
calls can perturb timing and successful output is not a production fix.


## After-n1-write and third-post-sleep discriminator (group 5h)

Layer: a new optional reporter-source/Nix family and separately reviewed typed
controller selection. The committed [breadcrumb packet](../../../docs/evidence/mainline-uart-progress-breadcrumbs/physical-2026-10-03/README.md)
and [result](../../../docs/evidence/mainline-uart-progress-breadcrumbs/physical-2026-10-03/result.json)
at revision 278769d0 record both worker points, a matched fresh receipt and
complete n0/n1, then no n2–n5 in 180s. CI 37171186624 and exact publication passed;
the subsequent operator reset passed guarded fresh protected normal recovery
and Home observation, recorded in the packet’s distinct recovery receipt.
Automatic return remains unverified. No guessed counter/IRQ diagnosis
is used. The immutable
selected source `k5a5zrhqy9ypr3mja1r50mdlcgi74i1f` has worker sleep/stop at
`drivers/soc/canaan/k230-uart-progress.c:67–70`, snapshot at 74 and numeric SBI
write at 98. A complete n1 frame leaves that call's return and the following
iteration/sleep/snapshot/output unproved.

### Additive source and finite placement

Layer only a new reporter patch over the current Breadcrumbs source. Name the
new family `kernelMainlineUartProgressPostSample`, configuration
`k230-mainline-uart-progress-post-sample`, matching toplevel/trial bundle and
`kernelMainlineUartProgressPostSampleExactObjects`. Preserve every old package,
source/config, object and trial derivation identity, including original reporter
and Breadcrumbs outputs. Inherit original serial-only ordinary-init artifact
parameters; bake in no reporter/breadcrumb/post-sample runtime flag. Exact
selected-dev config/headers, applied source, compiled Image and complete hardware
DT comparison remain separate host gates.

Only exact `k230.uart_progress_post_sample=1`, alongside exact existing
`k230.uart_progress=1` and `k230.uart_progress_breadcrumbs=1`, CONFIG_RISCV_SBI
and actual DBCN availability enables the new records. Absent/bare/invalid new
values preserve the current selected variant's behavior. Setup alone has init
lifetime; helper/flag and two static const arrays have ordinary lifetime. Each
array is aligned 64, sizeof<=64 including NUL and page-contained under actual
4KiB configuration; pass literal length excluding NUL, not a stack/VMAP_STACK
or freed init buffer. Each point attempts the existing SBI write API once.

Fixed new bytes, with literal leading/trailing LF:

```text
\nK230_UPP1 point=after-n1-write\n
\nK230_UPP1 point=third-post-sleep\n
```

After-n1-write is only sample index1, immediately after the existing numeric
SBI call returns, before loop advancement. Third-post-sleep is only index2,
after the unchanged third sleep and second stop check, immediately before
snapshot. No added stop check, delay, counter query, formatting, retry,
printk/emergency/fallback, priority/affinity/tick change or IRQ/TTY/PID1 output.
Existing six samples and two breadcrumbs remain unchanged. At most ten attempts
occur if calls return: six numeric, two old breadcrumbs, two new records.
Full/partial/zero/error counts remain discarded. One attempt is not a deadline;
firmware and sleep/scheduling can block, and the added calls can perturb timing.

### Typed capture and interpretation

Explicit `--uart-progress-post-sample` requires minimal mode and all existing
`--same-image-shell-pid1 --uart-progress --uart-progress-breadcrumbs` selectors.
Qualify the new exact manifest/kernel/dev/source and unique linked marker/gate
bytes before UART. Preserve exact original artifact qualification, marker-free
async=0/Bash/sole console/three controls, protected normal/registration-absence
checks and the single fresh receipt stimulus. Add only the new volatile gate.
No further candidate input or reboot follows that stimulus, irrespective of
receipt/record completeness. Existing selectors/parsers retain their behavior.

Accept only the two exact complete fresh lines, at most once and in source
order when both appear. Unknown/extra/stale/echo/duplicate/reordered/truncated/
interleaved records remain incomplete/unknown; retain private raw bytes, never
repair or strip arbitrary console text. Capture the whole qualified fresh boot
phase. Preserve independent facts for receipt, old breadcrumbs, new points,
six samples and protected recovery; a new point never authorizes input.

A visible after-n1-write proves the numeric n1 call returned, not its full
write count or this new call's return. A visible third-post-sleep proves the
prior point's call returned and the third sleep/stop checks passed, not
snapshot or n2 output. A later n2 record proves progress past that second
point and snapshot/formatting, not firmware count or physical RX delivery.
Missing points cannot distinguish blocked/failed/partial output, scheduling or
later work; do not name a fault from the last line. Independent protected normal
recovery remains a separate gate; no automatic-return or root/touch claim.

Rejected: another identical eight-call trial, shortened/removed sleeps,
IRQ/TTY/PID1 output, changed console/SBI fallback, polling/retry, and parser
loosening. These change other dependencies or repeat the same unresolved
boundary. Group 5h separates planning, source/native identity, full build,
exact objects, typed protocol and physical/recovery evidence.


Group5h's matching source/objects/full artifacts and positive controller gates
passed. Its independently reviewed physical capture reached worker-entry/Bash,
but no receipt, numeric samples or new points in180.0975s; the committed
[physical packet](../../../docs/evidence/mainline-uart-progress-post-sample/physical-2026-10-03/README.md)
and deployment receipt preserve that incomplete result. The subsequent NEW
operator reset passed guarded fresh normal postflight and reviewed Home evidence.
No return from entry's output, first sleep completion or later point is proved.
This leaves the ordinary mainline acceptance requirement and task5b.5 open.

## Memory-progress intervention after group5h (UNVERIFIED)

Group5h's independently reviewed actual capture reached only entry/Bash, with
no matching receipt, samples or new points. Group5g reached n1. Missing serial
output cannot identify execution or firmware return. The source audit in
[the memory comparison note](../../../docs/research/mainline-memory-progress-comparison-2026-10-03.md)
grounds a distinct intervention rather than another per-boundary ECALL chain.

Add separately named Memory reporter/kernel/system/bundle/exact-object outputs;
keep all existing package/source/config/trial identities. Explicit
`k230.uart_progress_memory=1` requires exact existing progress opt-in and actual
SBI/DBCN support. In that variant and gate only, suppress ALL worker output,
including numeric, Breadcrumbs and PostSample calls, retaining six5000ms sleeps,
cached snapshots, existing stop checks, normal priority/affinity and termination.
Absent/bare/invalid gate retains inherited worker behavior. Do not combine
runtime Breadcrumbs/PostSample selectors with this comparison.

Publish a finite consistent ordinary-memory state: stage before/after each
sleep, completion bitmap and last completed index. Publication/read ordering
must be explicit, bounded, and free of locks across sleep or firmware calls.
No snapshot/getter gains MMIO. An independently created normal-priority observer
waits once with finite kernel timeout (45 seconds), copies a consistent bounded
state, then attempts ONE final <=256-byte aligned page-contained ordinary-buffer
DBCN summary. No retry/printk/fallback/IRQ output; observer creation failure must
be explicit and bounded. Timeout depends on kernel execution; it is not a
firmware wall-clock guarantee. Existing modes must not create this observer.

Freeze the exact public grammar/stage encoding during source/controller review,
validate completion bitmap/index/stage consistency and fixture exact/absent/
invalid gates, sleep/stop/publication ordering, observer completion/timeout,
allocation failure and full/partial/zero/error one-call behavior. Independently
inspect actual selected headers/objects/linked strings/lifetime/config, original
artifact policy and complete hardware DT before physical use.

Typed `--uart-progress-memory` requires minimal/same-image-shell-PID1/progress
and rejects Breadcrumbs/PostSample or conflicting flags. Its actual preparation
qualifies reviewed source/dev/Image/manifest/archive, adds only the new volatile
gate, preserves fresh exact args/Bash readiness and protected normal guards,
and sends at most one fresh receipt followed by passive180-second capture.
The summary never authorizes another command or candidate reboot. Strict parser
accepts one complete exact fresh summary, keeping receipt/recovery distinct.
Unknown/duplicate/echo/stale/truncated/inconsistent output stays unknown.

A received summary proves its recorded progress BEFORE the final firmware call;
completion supports progress under removed repeated output, not an IRQ/firmware
fault or this call's return. Missing summary cannot distinguish worker, observer,
timeout, M-mode or serial failure. An M-mode stall on the only executing hart
can prevent S-mode observer progress. Protect normal profile/boot selection and
require separate fresh normal recovery. Ordinary root/glass and5b.5 stay open.

Rejected for this bounded comparison: direct UART polling without LSR/nbcon
ownership proof, firmware replacement, and repeated ECALL point chains.


## Same-image no-stimulus comparison (group 5j, UNVERIFIED)

Memory's completed 180.1021-second capture has one stimulus but no receipt/summary.
Preserve its exact selected lznjjfx1 bundle/307d7c source/dev/config/Image/DT,
all manifests/archive/load guards and identical volatile Memory bootargs. Add
`--uart-progress-memory-no-stimulus` requiring Memory, minimal, same-image-shell
PID1 and progress; reject conflicting comparison selectors before UART access.
This is only a controller input policy, never an appended kernel argument.

After the candidate boot command, use only read/pump/passive bounded 180-second
capture: no receipt, CR, Ctrl-U/Ctrl-C, retries, guards/uploads/proc commands,
reboot or finally/error-path input. Retain strict exact fresh summary parsing,
early-record argument qualification, banner/binsh/primary-prompt observations.
Record stimulus_attempts=0, receipt_observed false, receipt_status NOT_REQUESTED
and RX NOT_TESTED. Keep summary validity, worker completion and recovery separate.
A valid completed summary may qualify diagnostic observation without a receipt
in this explicit mode, never ordinary-root or receive acceptance. Default Memory
mode still sends exactly one stimulus and uses its existing receipt requirement.

Only existing ordered fresh SPL→6.6.36→login→normal-prompt qualification can
authorize protected NORMAL postflight writes; exact identities/eight hashes/
services/registration absence and distinct boot checks remain mandatory.
No summary is inconclusive; no normal return requires separate operator recovery.
An observed difference supports changed behavior under removed input attempt,
not a UART/IRQ/firmware fault or timing-independent causal conclusion.

Fixtures use transport write spies across prompt/summary/no prompt/no summary,
malformed/duplicate/truncated/stale/echo, timeout/read error/overflow and wrong
args, with zero candidate bytes throughout. Candidate normal-looking text cannot
authorize helper writes. Test same args, pre-open selector rejection, default
one-stimulus regression and separate actual protected recovery. Requalify actual
existing artifacts before physical use; no new kernel or full build is required.


## Same-image idle-polling comparison (group 5k, UNVERIFIED)

Add typed `--uart-progress-memory-poll-idle`, requiring minimal/same-image/
progress/Memory AND no-stimulus selectors. Reject conflicts/types/modes before
UART. Reuse the exact lznjjfx1 bundle, 1pvqbm4 dev, 307d7c source, Image/config/DT,
archive/manifest/load checks. Qualify `CONFIG_GENERIC_IDLE_POLL_SETUP=y` and the
linked NUL-terminated `nohlt` setup. The sole bootarg difference is one trailing
bare `nohlt`; reconstruct the exact literal argument transform and reject
`hlt`, duplicate/value-form tokens or arbitrary additions. Both previous Memory
policies and all other default transports remain unchanged. No kernel rebuild.

After boot, preserve strict zero-write behavior on success/timeout/error/finally,
180-second passive capture, fresh argument/summary parsing, NOT_REQUESTED receipt,
zero attempts and RX NOT_TESTED. Normal postflight writes require the existing
ordered fresh SPL→6.6.36→login→normal-prompt gate and independent protected
identities/eight hashes/three services/registration absence/distinct boot checks.
No candidate reboot or persistent environment/card/profile change.

The [source audit](../../../docs/research/mainline-memory-idle-polling-comparison-2026-10-04.md)
shows nohlt forces IRQ-enabled polling and restarts the tick. A summary supports
an idle/tick-policy-dependent difference only; absent output retains all worker,
observer, timer, scheduler and final-firmware-output limits. This is neither a
production power policy nor ordinary `/init`/root/panel/glass acceptance.
Rejected: cpuidle.off alone (default WFI remains), extra firmware-output markers,
new MMIO/IRQ/firmware/scheduler modifications and an unnecessary full build.

Fixtures must test typed pre-open dependencies/conflicts, exact sole argument
change, unchanged default/no-stimulus transports, unsupported/mismatched actual
config/Image gates, stale/wrong received args, strict valid/malformed/duplicate/
truncated summaries and zero candidate writes on read error/overflow/timeout.
Run actual existing-artifact preparation before the one physical comparison;
preserve fresh recovery or explicit pending operator reset separately.


## Memory summary through Linux printk (group 5l, UNVERIFIED)

Layer a separately named MemoryPrintk source/kernel/trial/exact-object variant
above unchanged Memory. New exact runtime gate
`k230.uart_progress_memory_printk=1` requires existing progress and Memory gates.
Preserve existing invalid/absent behavior and every prior derivation/source/
config/trial identity. New controller selector `--uart-progress-memory-printk`
requires minimal/same-image/progress/Memory/no-stimulus; reject nohlt/point/trace
selectors and type/mode conflicts before UART. Configuration/autoconf and hardware
DT match baseline Memory; only the reviewed source/Image and matching artifacts
change. Never select this code through an old artifact/namespace.

Keep worker sleeps, cached getters, stop checks, publication and observer
allocation/failure/completion/one acquire unchanged. Suppress all worker output.
With the new gate, observer performs ONE ordinary KERN_INFO/pr_info call instead
of final explicit DBCN, with fixed format
`\nK230_UMK1 s=%u n=%u m=%02x l=%u w=%u\n` and the existing bounded state rules.
The single call includes a leading newline: printk prefixes an empty line first,
separating any existing Bash prompt from the following timestamped summary.
The parser accepts only that following complete line; never strip a shell prompt.
No emergency priority, force flush, raw register access, firmware fallback,
second channel or retry. The normal registered Linux console owns its IER/
locking/nbcon behavior; one attempt is not a firmware or console wall-clock bound.

Qualify actual PRINTK/PRINTK_TIME/8250 console/DW support, disabled PRINTK_CALLER,
reviewed new source and
unique linked format/setup; target object must show ordinary printk API use plus
unchanged atomic/completion behavior. Exact config and DT/archive/load/CRC guards
remain. Literal args add only the new gate to base zero-input Memory; no nohlt,
earlycon, keep_bootcon, quiet or logger-format override. Received exact args and
fresh Linux ttyS0 registration/console-enable markers must ground the backend.

Accept only fresh K230_UMK1 with the observed timestamp-only six-decimal kernel
console prefix/CRLF convention and bounded fields; do not repair embedded CR or
invent execution-context prefixes. Reject old UMP/wrong-channel, duplicates,
malformed/truncated/stale/echoed records and wrong received args. Keep one coherent
summary, validity and worker-completion facts separate. Retain zero candidate
writes on all capture/error/finally paths, NOT_REQUESTED receipt/RX NOT_TESTED,
180-second passive capture and independently gated protected normal recovery.

A record establishes observer snapshot/formatting reached changed Linux output;
not printk return, prior DBCN failure or ordinary root. Absence retains observer,
timeout/scheduling/console/UART limits. Rejected: unsupported timer-DT switches,
extra SBI markers, simultaneous nohlt, MMIO polling and force-console bypasses.
Source/backend grounding and limits are in the linked research note. First land
native/source identity proof, then freeze matching full build, target object and
actual artifact/controller gates before one reserved physical boot.


## Same-image tickless-policy comparison (group 5m, UNVERIFIED)

Layer a typed controller-only `--uart-progress-memory-printk-nohz-off` selector
on the existing MemoryPrintk policy. Require minimal/same-image/progress/Memory/
no-stimulus/MemoryPrintk and reject invalid types, modes and competing polling,
point, clock, trace or timer selectors before opening UART. Reuse the actual
p2kdar89 bundle, xna7x12 kernel, 24hbalyl dev and 0l4mgw9 source. No kernel,
initrd, DT build or new transfer is necessary. The board operator still verifies
existing staged artifacts and fresh protected normal state before use.

Keep matching source/config/Image/archive/manifest/load/CRC/DT guards and all
previous package identities/default transports. Require actual NO_HZ_COMMON and
NO_HZ_FULL, HIGH_RES_TIMERS, HZ=250, RISCV_TIMER and RISCV_SBI configuration,
matching config/Image hashes and one linked NUL-terminated `nohz=` setup. Do not
require the unset legacy CONFIG_NO_HZ symbol. Reconstruct the exact qualified
MemoryPrintk baseline and append ONLY trailing `nohz=off`: literal U-Boot
transport changes 416 to 425 bytes within the existing 512-byte bound. Reject
original nohz/nohz_full tokens, bare/empty/alternate/duplicate nohz forms and
arbitrary bootarg syntax or changes; do not expose a general option editor.

Retain worker/observer/source/format, fresh exact received args and Linux ttyS0
backend proof, strict complete-line UMK namespace and bounded state parsing,
and the qualified optional Readline prompt prefix. Capture remains 180 seconds
with zero candidate writes on success/error/finally, NOT_REQUESTED receipt,
zero attempts and RX NOT_TESTED. Only independently ordered fresh normal boot
markers and protected normal postflight authorize recovery writes. No candidate
reboot, flash or persistent environment/profile/card change.

The [read source and actual config/Image](../../../docs/research/mainline-memory-printk-periodic-tick-comparison-2026-10-04.md)
show this inhibits global tickless activation, without disabling high-resolution
timers or guaranteeing hardware timer interrupts. nohlt already restarts ticks
in its poll arm; do not relabel that previous test as a tickless-off test. Exact
received token and compiled parser support do not separately observe runtime
activation. A valid record supports progress under changed tick policy, not an
IRQ cause or printk return. Silence retains scheduling, sleep/wakeup and output
unknowns. Ordinary /init/root/panel/glass acceptance remains separate.

Fixtures cover pre-open dependency/type/conflict rejection; sole exact transform
and unchanged defaults; unsupported/mismatched actual config/Image; stale/wrong
args, valid/malformed/duplicate/truncated/wrong-channel records; zero writes on
all timeout/error paths and independently guarded recovery. Commit an executed
actual-artifact qualifier and safe receipts before physical use. Rejected: combined
nohlt/highres/clock options, new markers, raw IRQ/MMIO intervention and unnecessary
full builds. A fixed Bash-PID1 autonomous probe is a separately planned fallback,
not authorization to pass arbitrary scripts through this selector.


## Fixed autonomous Bash-PID1 comparison (group 5n, UNVERIFIED)

This controller/userspace comparison uses existing p2/xna/24h/0l4 artifacts. Add
only typed `--autonomous-bash-pid1`, requiring minimal and same-image-shell-PID1.
Reject every progress/breadcrumb/post-sample/Memory/no-stimulus/polling/Printk/
nohz/clock/trace/shutdown selector and invalid types/modes before preparation,
output creation or UART. Retain all defaults and generic transport restrictions.
The new helper reconstructs one exact fixed script from a controller-generated
32-character lowercase hex nonce; it is not a script/args editor. Retain original
sole init token, rdinit=/bin/sh, async0, fsck skip and the two service masks.

Use the exact 154-byte script and old-Hush transport in the
[scout](../../../docs/research/mainline-autonomous-bash-pid1-comparison-2026-10-04.md).
The only new argv after -- are -c and that script. Remove all reporter and trace
gates so the read source returns before creating either reporter thread. Native
execution of the exact selected Hush lexer/variable/quote/command handling must
show one volatile setenv bootargs call, the exact 477-byte result, zero expansion
or extra/persistent command execution. Use the pinned parser source/hash and
qualify configuration/version facts with their installed-identity limits. Native
selected Linux next_arg plus repair/set_init_arg handling must show exactly -c
and the complete script after init/rdinit clearing and post-- parsing. A Python
model or POSIX/shlex surrogate alone is insufficient.

The old Hush syntax requires a single-quoted complete data argument with no
embedded single quote, raw dollars protected and every script backslash doubled.
Linux strips its outer script doublequotes but cannot escape inner doublequotes;
the fixed body has none. With the actual system path this yields one 503-byte
command, 504 with CR, within the unchanged strict 512-byte transport bound. Reject
nonce changes in shape, script/quote/backslash damage, extra args/gates/options
and all arbitrary syntax before UART. Actual printenv equality must pass before
boot; fresh exact kernel arguments, new 7.3 phase, registered Linux ttyS0 and
/bin/sh entry qualify records. Commandline/echoed script text is never a record.

Requalify same source/config/Image/DT/archive/manifest/load/CRC identities and
actual archived executable /bin/sh and /bin/sleep, their RISC-V ABI/loader hashes
and Bash printf/test/exec builtins. Commit executed actual-artifact qualifier,
native parser proof and safe receipts. No implicit build/transfer or hardware
claim follows from host execution.

The fixed script checks $$=1 and EUID=0, emits newline-delimited
K230_BP1:<nonce>:B, runs exactly one absolute /bin/sleep 5 and emits E only after
prior successful returns. Outside that conditional chain it execs /bin/sh -i,
including after a failed test/sleep; it deliberately does not exit PID1 or issue
a reboot. Runtime exec failure/EOF/output blockage remain possible. Capture is
60 seconds, zero candidate bytes on success/error/finally, no receipt/RX test,
no shell commands/retries/recovery attempts based on marker presence. Existing
ordered fresh normal-return markers and protected identities/eight hashes/three
services/distinct boot/registration checks alone permit normal postflight.

Accept only complete fresh raw B then E lines with the exact nonce, strict CRLF
handling and no prompt/ANSI/kernel-text repair. Reject malformed record-prefixed
lines, stale/wrong/duplicate/reversed/truncated/interleaved records. Preserve
begin/end/prompt separately and keep absence unknown. Begin supports limited
PID1/UID0 tests and output reached; end supports earlier printf/sleep success,
not its own printf return. A later interactive prompt adds progress through
that return/exec. This is not a proc/kernel/initrd full identity guard, RX,
ordinary /init/root/panel/glass acceptance or a single-fault isolation. Host
wall time does not prove kernel-clock progress. Recovery remains independent.

Rejected: generic script flags, POSIX-only quoting models, kernel observer
markers in this comparison, unconditional exit/reboot, another kernel build
and multiple timer/IRQ interventions. Preserve the zero-input result even on
incomplete capture and record separate operator recovery or explicit NEW reset.


## Fixed initrd manager debug logging (group 5o)

Userspace controller only: begin-only `--initrd-debug-logging` requires the
existing synchronous-initramfs and marker-free selectors. Append exactly
`rd.systemd.log_level=debug rd.systemd.log_target=console`; reject inherited
plain/initrd log settings and underscore/hyphen aliases, duplicate/conflicting
values, wrong types and other phases before UART. Save the typed selection;
old state defaults false. Pure policy gives 356 argument / 374 command bytes.

Retain p2 Image/initrd/DT/source/config/manifest, all five load/CRC checks, sole
console, exact init/root/masks and 180-second passive readiness. Preserve the
complete private log even past rolling-buffer capacity, split fresh milestones
and unknown-no-input behavior. Debug output may change timing/console pressure.
Reject global tracing, journal forwarding, udev verbosity, extra masks/targets,
alternate PID1 or a new build for this first comparison. Manager state/ExecStart
logs cannot pinpoint silent shell subcommands; narrower helper instrumentation
would need separate scope. Physical results and recovery remain unverified.
See [read archive/source and current physical boundary](../../../docs/research/mainline-initrd-debug-logging-2026-10-05.md).


## Fixed info/console comparison (group 5p)

Userspace controller: typed begin-only `--initrd-info-logging` requires both
existing synchronous-initramfs/marker-free selectors and excludes the debug
selector. Select exactly `rd.systemd.log_level=info rd.systemd.log_target=console`.
This changes only one previous value: 355 argument / 373 literal command bytes.
Persist/restore the typed choice; old states default false. Reuse alias/type/
pre-UART guards while keeping old defaults and debug mode unchanged. Retain
same source/config/Image/initrd/DT, normal/artifact/load/CRC/argument gates and
180-second passive readiness/full private logging/unknown-no-input policy.

Reject compensating kernel verbosity, debug+kmsg, extra masks/targets, global
tracing and rebuilds for this comparison: each changes additional boundaries.
Changed observed progress is sensitivity to one value, not a proven call/cause.
A silent run cannot distinguish earlier PID1 setup from console open/write.
[Source/physical scope](../../../docs/research/mainline-initrd-info-console-comparison-2026-10-05.md);
NEW recovery and actual qualification remain required.


## Fixed info/kmsg comparison (group 5q)

Userspace controller: begin-only `--initrd-info-kmsg-logging` requires synchronous
initramfs and marker-free ordinary init, excluding both debug and info-console.
Append exactly `rd.systemd.log_level=info rd.systemd.log_target=kmsg`: the sole
changed value is console→kmsg,352 raw argument/370 literal command bytes.
Preserve old defaults/profiles, typed saved continuation with old missing=false,
pre-UART alias/type/conflict guards and the unchanged transport bound. Retain
same p2/24h source/config/Image/DT/archive/system init, masks/root/console,
five loads/CRCs, normal and live argument guards,180-second passive capture,
full private logging and unknown-no-input policy.

Kmsg selection may fall back to console or drop/filter records. Eligible INFO
severity is not proof of delivery or absence of console calls. Changed progress
means backend-selection sensitivity; silence does not localize a failing call.
Reject debug+kmsg, verbosity compensation, arbitrary logging controls, tracing,
new masks/targets/PID1 or builds: each adds another intervention. Require
reviewed source/actual host gates and NEW protected recovery before one board
capture, then independent recovery or explicit NEW reset. [Pinned source audit](../../../docs/research/mainline-initrd-info-kmsg-comparison-2026-10-05.md).


## Unchanged ordinary-baseline repeat (group 5r)

Userspace orchestration/evidence only. Existing begin selectors
`--wait-initramfs-in-initcall --without-boot-markers` select the quiet policy;
all three logging selectors remain false. Preserve exactly299 raw argument/
317 literal bytes, p2/24h source/config/Image/DT/archive/init/root/three controls,
five loads/CRCs, normal helper and printed/live arguments. Actual preparation
must show equality with the earlier quiet command, not merely removing an
arbitrary suffix from a captured string. No new selector or source change.

Require NEW verified recovery after5q, actual artifact qualification and
independent review before one180-second passive capture. Keep full private
coverage and no candidate input on unknown readiness; commit independent
recovery or explicit pending NEW reset. A repeat tests reproducibility before
new interventions; either outcome does not establish a single logging cause.
Retain ordinary5b.5 and all runtime/glass/cause limits. Reject multiple repeats,
compensating verbosity, tracing, targets/masks/PID1/IRQ/MMIO and builds in this
group. Helper instrumentation is a separately scoped possible follow-up only
if the original closure boundary reproduces. [Read archive/source roadmap](../../../docs/research/mainline-ordinary-baseline-repeat-2026-10-05.md).


## Selected init exec-return record (group 5s)

Use a separately gated, default-disabled child of p2. Emit at most one fixed
versioned INFO record with the signed return value immediately after the selected
ramdisk run_init_process call, before its unchanged success/error conditional.
Existing boot markers stay disabled; do not add generic fallback records, force
console delivery, change printk mechanics, argv/env, init or existing branches.
A typed begin-only controller selection must reject conflicts/aliases/types
before UART, validate exact expected new arguments and manifests, and preserve
all protected preflight/load/CRC/normal/unknown-no-input guards and180s bound.

Old Nix outputs retain their identities. New kernel/dev/source/system/bundle
identities and every necessary archive dependency delta require actual proof;
retain exact config, DT hardware and archived systemd/init/Bash/loader/helper
bytes. Require source/control-semantic fixtures, selected RISC-V object review,
actual artifact qualification and independent review before physical capture.
A record with return value zero shows exec setup success, not user-mode
transition/loader/main.
Missing/partial records and output-call return remain unknown; never label them
a located instruction or hardware cause. Recovery is independently guarded or
explicitly pending NEW reset. [Pinned source and alternative analysis](../../../docs/research/mainline-init-exec-return-probe-2026-10-05.md).
