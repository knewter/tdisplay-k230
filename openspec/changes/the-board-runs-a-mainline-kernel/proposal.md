## Why

Today's kernel is a pinned vendor fork, `ruyisdk/linux-xuantie-kernel` @
`7d4e1f444f461dbe3833bd99a4640e7b6c2cd529` (Linux 6.6.36, `nix/kernel-src.nix`),
carrying eleven local patches (`nix/kernel.nix`) that exist only because that
tree is old, undermaintained upstream, and missing fixes this board's bring-up
needed: a bounded DSI PHY wait, a bounded thermal loop, an RTC day-of-month
mask bug, a DCS-read backport, a touch driver backport, and more. Nobody
outside this project reviews that tree, security fixes land on it only if
someone backports them by hand, and every future Linux feature (newer
schedulers, newer DRM, newer RISC-V vector support) requires either a manual
backport or staying frozen at 6.6 forever.

Mainline Linux has been gaining real Canaan K230 support since late 2025:
`arch/riscv/Kconfig.socs`' `ARCH_CANAAN`, a pinctrl driver
(`drivers/pinctrl/canaan/pinctrl-k230-iomux.c`, `PINCTRL_K230`), a reset
driver (`drivers/reset/reset-k230.c`, `RESET_K230`), a clock driver
(`COMMON_CLK_K230`), and a basic `arch/riscv/boot/dts/canaan/k230.dtsi` +
`k230-canmv.dts`/`k230-evb.dts` all merged for the v7.3 window (too late for
v7.2, confirmed: `git show v7.2:arch/riscv/boot/dts/canaan/` lists only K210
files). A USB-PHY driver and its device-tree binding for K230 were also
accepted upstream (Vinod Koul, `lkml.org/lkml/2026/2/27/1255`) but the DT node
wiring it into `k230.dtsi` has not landed as of this writing. An SDHCI series
(`sdhci-of-dwcmshc.c` reuse, v5 as of March 2026, "tested successfully on
CanMV-K230-V1.1 with AP6212 SDIO on MMC0 and MicroSD on MMC1") is still under
review on `linux-riscv`, not yet merged into any tagged or `master` tree
checked here. There is still no mainline display (`canaan-drm`/VO/DSI),
touch, audio, RTC, PMU/power-key, thermal, ADC, PWM, GPIO, or crypto driver
for this SoC — `panel-canaan-universal.c`, `canaan_drv.c`, `rtc-k230.c`,
`canaan_thermal.c`, `k230-adc.c`, `k230-pmu-pwrkey.c`, `canaan_k230_inno.c`
all return HTTP 404 from `torvalds/linux` today (checked directly via
`gh api repos/torvalds/linux/contents/<path>`, 2026-09-29); the GT9895 touch
driver this project backported (`goodix_berlin`) is, unusually, already
upstream on its own merits, since it was itself a v6.12 mainline driver we
backported onto the older vendor tree.

So mainline cannot run this handheld's shell today, and won't be able to for
some time — the display stack alone is a from-scratch driver effort with no
public work in progress found. But mainline *can* now be built for this SoC,
and getting there — a real cross-build, a real device tree, a real forward
port of what applies — is work worth doing in parallel with the vendor-kernel
image, so that: (1) the day mainline gains a usable display driver, this
project is not starting from zero; (2) our patches that fix generic-Linux
bugs (not Canaan-driver bugs) have a known home; and (3) the board has a
path to a maintained, security-patched kernel for its console/network/storage
functions even before the display works.

## What Changes

- Publish a researched hardware/mainline-support inventory (this document +
  `docs/research/mainline-kernel-inventory.md`) covering every function
  `docs/research/board-capability-inventory.md` already names, with a fourth
  column this project has not written before: mainline driver status,
  cited by file existence (`gh api .../contents/<path>` returning 200 vs.
  404) and, where a driver is genuinely missing, the exact in-review patch
  series if one exists.
- Add a **second, parallel** kernel/device-tree/boot-files build
  (`.#kernelMainline`, `.#deviceTreeMainline`, and a boot-files output) pinned
  to a specific mainline commit that carries basic K230 support
  (`v7.3-rc5`, the newest tag with `arch/riscv/boot/dts/canaan/k230.dtsi`
  present; there is no stable release with K230 support yet — `v7.2` does not
  have it). This does **not** touch `.#kernel`, `.#deviceTree`,
  `nixosConfigurations.k230`, or `.#sdImage` — the shipped image keeps
  booting the vendor Xuantie kernel unchanged.
- Forward-port whatever of our eleven vendor-kernel patches target hardware
  or bugs mainline already covers (expected: none of the display/audio/RTC/
  power-key ones, since mainline has no driver for any of them to patch;
  the vector-toolchain-probe fix turns out to be already fixed upstream,
  see inventory). Record exactly which patches port, which do not, and why,
  rather than silently dropping any.
- Define a phased plan whose first milestone is host-provable
  (`nix build .#kernelMainline`, `.#deviceTreeMainline`) and names the actual
  first hardware milestone as "boots to a serial console" — not "SD rootfs" —
  because mainline has no merged storage driver for this SoC yet; SD rootfs
  and USB networking are later milestones explicitly gated on upstream
  patches this project does not control the timeline of.
- Add `system/kernel` requirements recording that a parallel mainline build
  exists, that the default system is unaffected by it, and what its current
  hardware ceiling is — the same pattern already used for the optional RVV
  trial kernel in this same capability.
- **Milestone 1, coordinator-directed continuation of this same change**:
  forward-port GPIO (`gpio-k230.c`), SD/MMC (`sdhci-of-kendryte.c`) and USB
  (`dwc2` parameter/register hunks) from the pinned vendor tree onto the
  mainline pin, with matching device-tree nodes; add a full NixOS system
  variant (`nixosConfigurations.k230-mainline-console`) that boots this
  kernel, with the out-of-tree Wi-Fi kernel module excluded (no expectation
  it compiles against a kernel seven major versions newer than its origin);
  and produce matching boot files (Image, a DTB with this system's real
  bootargs baked in, and its initrd wrapped for U-Boot) so a future
  one-shot boot attempt has everything staged. Two real vendor-to-mainline
  API migrations were found (by a failed build, not by inspection) and
  fixed against mainline's own already-migrated reference drivers — see
  `docs/research/mainline-kernel-inventory.md` and design.md decisions 7–10
  for the full account. Still entirely host-only; no board action taken.

## Capabilities

### Modified Capabilities

- `system/kernel`: adds requirements for the parallel mainline build
  (existence, non-default status, and its recorded hardware ceiling).
  Existing requirements (the vendor kernel is pinned and its patches
  recorded; the RVV trial retains normal recovery; vector execution is
  gated by kernel/context support) are unchanged.

### New Capabilities

None. This is infrastructure inside the existing `system/kernel` capability,
not a new user-observable capability — nothing about what the shipped
handheld does changes.

## Impact

`nix/kernel-mainline-src.nix`, `nix/kernel-mainline.nix`,
`nix/dts/k230-tdisplay-mainline.dts`, `nix/device-tree-mainline.nix`,
`nix/kernel-mainline-boot-files.nix`, `nix/patches/mainline/{gpio-k230.c,
sdhci-of-kendryte.c}`, `flake.nix` (new package/nixosConfigurations outputs
only, no changes to existing ones), `docs/research/mainline-kernel-inventory.md`,
`openspec/specs/system/kernel/spec.md`. No change to `nix/kernel.nix`,
`nix/kernel-src.nix`, `nix/device-tree.nix`, `nix/k230.nix`,
`nix/hardware.nix`, `nix/sd-image.nix`, `nix/shell.nix`, or any existing
`nixosConfigurations` output — confirmed by `git diff --stat` against each
after every task group, including the milestone-1 continuation. This whole
change's functional proof is host-only (cross-builds, including a full
NixOS system-closure build); the first hardware milestone (does U-Boot
actually load and run an Image+DTB(+now, optionally, initrd) and print
anything on the CH342 console, and separately, does the milestone-1
candidate reach a login prompt over SD) is explicitly **not** performed by
this change and is left as two named, unclaimed evidence gates — see
tasks.md's "Remaining evidence gate" section — for the coordinator to
schedule a board boot.


The isolated DRM continuation also provides `k230-mainline-drm-trial` and
`kernelMainlineDrmTrialBootFiles`: a console system built against the DRM
candidate, its matching initrd/bootargs and closure inventory, and an offline
root-stage/manual U-Boot procedure. `nix/mainline-drm-trial.nix`,
`tools/mainline-drm-trial-inspect.py`, and
`docs/evidence/mainline-display-boot-preparation.md` own this host-only
preparation. The normal system profile and boot files remain selected; actual
card staging and task 5b.5's physical evidence are unperformed.
