## Context

See proposal.md — Why. The technical findings this design rests on are in
`docs/uboot-ums.md`; this document records the choices, not the evidence.

Three constraints shape everything below.

1. **The work lands in stage 1**, specifically in the Canaan U-Boot 2022.10
   tree: a Kconfig delta and a device-tree override. Not the kernel, not Nix
   beyond plumbing, not userspace.
2. **`tools/gen-stage1.sh` does not compile U-Boot.** It packages an
   already-built tree under `.build/k230_linux_sdk/output/`. A configuration
   change has nowhere to land until the compile step is inside this
   repository, which is what `every-blob-is-built-from-source-or-named` is
   doing.
3. **The card is the only boot medium**, so the blast radius of a wrong
   stage 1 is one trip to the card reader — the loop we are already in.

## Goals / Non-Goals

**Goals**

- One U-Boot binary that boots normally *and* can be dropped into `ums`.
- The change expressed as configuration, not as a fork: a defconfig fragment
  and a device-tree override that read as intent.
- The recovery story written down and tested, not assumed.

**Non-Goals**

- Automatic entry into `ums`. A `bootcmd` that stops and waits for a host is
  a boot-time hazard on a board whose only recovery is a card reader. Typing
  `ums 0 mmc 1` at a prompt we already interrupt is enough.
- Signing, authentication, or protecting the card from a host that mounts it.
- Making the write itself faster. That is the partial-write follow-up.

## Decisions

### D1: Use `ums`, not `dfu`, not `rockusb`, not `fastboot`

`ums` gives the host a block device, so `dd`, `sfdisk`, `mount` and
`rsync` all work unchanged and `tools/flash.sh` keeps its
`/dev/disk/by-id` guardrails.

*Rejected: `dfu`.* Canaan's path, and cheaper in one way — `CONFIG_CMD_DFU=y`
alone also flips `usbotg0` to `okay`, because `k230.dtsi` guards its
`status = "disabled"` with `#ifndef CONFIG_CMD_DFU`. But DFU writes named raw
regions from `dfu_alt_info`; it cannot mount a filesystem, so the
partial-write follow-up that is the real prize is not available. It also
drags in `select DFU` and, per `arch/riscv/cpu/k230/cpu.c`, removes the PMP
entries locking the `0x91213000`/`0x91214000` window.

*Rejected: `rockusb`, `fastboot`.* `f_rockusb.c` is in the tree but is
Rockchip protocol; `fastboot` needs a host tool and gives less than a block
device. Neither is used by anything on this board.

### D2: Enable `usbotg0` with an explicit device-tree override

```dts
&usbotg0 {
        status = "okay";
        dr_mode = "peripheral";
};
```

in `arch/riscv/dts/k230_canmv_v3.dts`, rather than getting the same effect
for free by setting `CONFIG_CMD_DFU=y`. The override says what it means, does
not change the PMP configuration, and matches what
`k230_canmv_mrt.dts`, `k230_canmv_lckfb.dts` and `k230_canmv_gt6700.dts`
already do in the vendor tree.

### D3: Turn the dwc2 *host* driver off in the first variant

In U-Boot 2022.10, `U_BOOT_DRIVER(usb_dwc2)` (`UCLASS_USB`) and
`U_BOOT_DRIVER(dwc2_udc_otg)` (`UCLASS_USB_GADGET_GENERIC`) both match
`snps,dwc2`. `lists_bind_fdt()` binds the first matching driver in the linker
list and stops; it only continues on `-ENODEV` from a driver's `.bind`, and
neither driver has one. The gadget's `dr_mode` refusal lives in
`dwc2_udc_otg_of_to_plat()`, which runs at probe — too late. Linker-list
entries sort by name, and `dwc2_udc_otg` sorts before `usb_dwc2`.

So with both enabled the gadget claims every `snps,dwc2` node, including
`usbotg1` and the onboard RTL8152 behind it, and U-Boot's USB host goes dark
without saying so. Canaan reached the same conclusion: their
`k230_canmv_burntool_defconfig` enables the gadget and drops
`CONFIG_USB_DWC2`.

The first variant therefore sets `# CONFIG_USB_DWC2 is not set`. A silent
loss is worse than a declared one, and nothing in `bootcmd` — `run blinux`,
which touches only `mmc` — uses USB host.

*Alternative kept for the follow-up:* add a ten-line `.bind` to
`dwc2_udc_otg.c` returning `-ENODEV` unless `dr_mode` is `peripheral` or
`otg`, then set `dr_mode = "host"` on `usbotg1`. `lists_bind_fdt()` falls
through to the host driver and both work. Worth doing, because a TFTP loop
over the onboard Ethernet is a *faster* iteration path than `ums` for
kernel-only changes — but it is a source patch to a driver, so it comes after
the configuration-only version is proven.

### D4: No board C code

`CONFIG_DM_USB_GADGET=y` takes the DM half of `dwc2_udc_otg.c`, which fills
`struct dwc2_plat_otg_data` from the device tree. The legacy path, where a
board calls `dwc2_udc_probe()` by hand as Rockchip and Meson do, is the
`#if !CONFIG_IS_ENABLED(DM_USB_GADGET)` branch and we do not take it. The USB
PHY is already set up unconditionally in `harts_early_init()`
(`arch/riscv/cpu/k230/cpu.c` writes `USB_IDPULLUP0`, `USB0_CTL0`,
`USB0_CTL1`), so there is nothing left for a board file to do.

### D5: Sequence behind `every-blob-is-built-from-source-or-named`

This change cannot land first. It needs a U-Boot that this repository
configures and compiles, and under the requirement that change is replacing
— "Stage 1 … SHALL NOT be built from source by this project" — it is not
merely awkward but forbidden.

### Why this is an ADDED delta and not a MODIFIED one

The obvious move is a MODIFIED delta against "Stage 1 is a pinned vendored
artifact". Two reasons not to:

- That requirement is not in `openspec/specs/` yet. `image/boot-chain` exists
  only as an ADDED delta in `the-board-boots-what-we-built`, which is still
  in flight.
- It is already being overturned. `every-blob-is-built-from-source-or-named`
  carries a RENAMED + MODIFIED delta turning it into "Stage 1 is built from
  source this project can read". A second MODIFIED delta against the same
  requirement, from a change that depends on the first, would be two changes
  editing the same sentence in opposite directions.

So this change adds requirements about what stage 1 *offers*, and states its
dependency instead of re-litigating how stage 1 is produced.

## Risks / Trade-offs

- **The dwc2 gadget does not enumerate on first try.** → The usual cause is
  B-session / VBUS detection. `dwc2_udc_otg_of_to_plat()` in this tree reads
  `u-boot,force-b-session-valid` and `u-boot,force-vbus-detection`; adding
  either is a device-tree line. J3 has real `USB0_ID` and `USB0_VBUS` wiring
  and `cpu.c` already sets `IDPULLUP0`, so there is a decent chance neither is
  needed. Budget one extra iteration.
- **The driver-binding reasoning in D3 is read from source, not observed.** →
  `dm tree` at the U-Boot prompt settles it in one command, before and after.
  Both variants are safe under either answer; only the explanation changes.
- **`ums` is not obviously faster.** The image is 2.21 GB and U-Boot's dwc2
  gadget realistically moves 5–20 MB/s. → The win claimed here is removing
  the human, not raw throughput. If the follow-up partial write never
  happens, this change buys unattended flashing and little else, and that
  should be said out loud rather than discovered later.
- **A host that automounts the card mid-write.** → `flash.sh`'s existing
  unmount step and by-id discipline already cover this; the `ums` device is
  just another by-id path.
- **We write our own bootloader through the thing our bootloader is running.**
  A full-image write over `ums` overwrites the raw region at 1 MiB / 1.5 MiB /
  2 MiB that the running U-Boot came from. → Harmless, because the running
  copy is already in DRAM and the next boot reads the new one; and if the new
  one is bad, §6 of `docs/uboot-ums.md` applies.

## Migration Plan

1. `every-blob-is-built-from-source-or-named` lands; stage 1 is compiled from
   this repository.
2. Add the defconfig fragment and the device-tree override. Build. The old
   stage 1 still exists in git history and in the store.
3. One card-reader cycle installs the new stage 1. This is the last mandatory
   one.
4. Prove `ums` on hardware, capture the console into
   `docs/evidence/uboot-ums-hardware.txt`.
5. Add the `ums` target to `tools/flash-latest.sh`, keeping the reader path.

Rollback is writing the previous image in a reader. There is no state on the
board that survives it.

## Open Questions

- Which sequence number the gadget controller gets, i.e. whether the command
  is `ums 0 mmc 1`. Answered by `dm tree` on the first boot of the new
  stage 1; it does not change the specs, the approach or the tasks.
- Whether Route C — the BootROM USB path via `k230_flash` — actually engages
  on this board. Deliberately a task rather than an open question, because
  the answer is written into a requirement either way.
