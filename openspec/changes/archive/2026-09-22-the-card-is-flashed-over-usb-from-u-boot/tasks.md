# Tasks

Task groups 1 and 5 need only the board as it stands today. Group 2 needs no
board at all. Groups 3, 4 and 6 need the board and a cable to **J3**, the data
USB-C — not the charging one that carries the console.

Group 2 onwards depends on `every-blob-is-built-from-source-or-named` having
landed, because until then nothing in this repository compiles U-Boot. It
landed on 2026-09-22: U-Boot is compiled by `nix/uboot-k230.nix`, so "the
configuration this repository builds" below means a Kconfig fragment and a
patch file that derivation applies, and "build stage 1" means `nix build
.#stage1`. Wherever a task below still says `firmware/stage1/*.bin` or
`PROVENANCE.txt`, read the built `SHA256SUMS` instead; there is no committed
binary any more.

## 1. Establish the baseline on the board

- [x] 1.1 Confirm `ums` is absent and `k230_dfu` is present, which also
      confirms that the source under `.build/` is what is on the card.
      **Hardware proof.**
      `./tools/console.py /dev/ttyACM0 --wait=3 "help ums" && ./tools/console.py /dev/ttyACM0 --wait=3 "help k230_dfu"`
      Done when the first says the command is unknown and the second prints
      "k230 burntool enter dfu".
- [x] 1.2 Record which driver is bound to each `snps,dwc2` node today, as the
      before half of the D3 question. **Hardware proof.**
      `./tools/console.py /dev/ttyACM0 --wait=3 "dm tree"`
      Done when the output is appended to
      `docs/evidence/uboot-ums-hardware.txt` and shows `usb-otg@91540000`
      bound and `usb-otg@91500000` absent.
- [x] 1.3 Record whether U-Boot enumerates the onboard RTL8152 today — this
      is exactly what variant A1 gives up. **Hardware proof.**
      `./tools/console.py /dev/ttyACM0 --wait=3 "usb start; usb tree"`
      Done when the result is in `docs/evidence/uboot-ums-hardware.txt`,
      either way.
- [x] 1.4 Record how U-Boot sees the card, so the `ums` arguments are not a
      guess. **Hardware proof.**
      `./tools/console.py /dev/ttyACM0 --wait=3 "mmc list; mmc dev 1; mmc info"`
      Done when the device number and capacity are in the evidence file.

## 2. Configure stage 1 for USB device mode

- [x] 2.1 Add the gadget symbols to the U-Boot configuration this repository
      builds: `CONFIG_USB_GADGET`, `CONFIG_DM_USB_GADGET`,
      `CONFIG_USB_GADGET_DWC2_OTG`, `CONFIG_USB_GADGET_DOWNLOAD`,
      `CONFIG_CMD_USB_MASS_STORAGE`, and a vendor/product pair. Done when
      `CONFIG_CMD_USB_MASS_STORAGE=y` appears in the generated `.config`.
- [x] 2.2 Turn the dwc2 host driver off (`# CONFIG_USB_DWC2 is not set`) and
      write the reason — design.md D3 — next to it, so the next reader does
      not "fix" it. Done when the comment names the binding conflict, not
      just the symbol.
- [x] 2.3 Override `&usbotg0` in `arch/riscv/dts/k230_canmv_v3.dts` to
      `status = "okay"; dr_mode = "peripheral";`. Done when the built
      device tree has `usb-otg@91500000` enabled.
- [x] 2.4 Build stage 1 and confirm `ums` is linked in. **No board needed.**
      `nix build .#stage1 && strings result/fn_ug_u-boot.bin | grep -c ums`
      — or, if the compressed image defeats `strings`, grep the U-Boot map
      or `.config` in the build output instead. Done when the `ums` command
      is demonstrably in the binary.
- [x] 2.5 Confirm the image still assembles at the sizes `nix/sd-image.nix`
      enforces — `fn_ug_u-boot.bin` has a 1 MiB slot and the gadget code
      grows it. **No board needed.**
      `nix build .#sdImage`
      Done when the build succeeds rather than failing the slot check.

## 3. Prove it on the board

- [x] 3.1 Write the new stage 1 to the card in a reader. This is the last
      mandatory card-reader cycle. **Hardware.**
      `./tools/flash-latest.sh`
      Done when the board still boots Linux exactly as before — the gadget
      must not have broken the normal path.
- [x] 3.2 Record what is bound now, as the after half of 1.2. **Hardware
      proof.**
      `./tools/console.py /dev/ttyACM0 --wait=3 "dm tree"`
      Done when the gadget driver is bound to `usb-otg@91500000` and the
      evidence file says whether it also took `usb-otg@91540000`, settling
      design.md D3.
- [x] 3.3 With a cable from the host to J3, enter `ums` and confirm the host
      sees a block device of the right size. **Hardware proof.**
      board: `./tools/console.py /dev/ttyACM0 --wait=3 "ums 0 mmc 1"`;
      host: `lsblk -o NAME,SIZE,MODEL,TRAN` and `ls -l /dev/disk/by-id/`
      Done when a by-id path exists whose size matches 1.4, and both the
      console and the host output are in
      `docs/evidence/uboot-ums-hardware.txt`.
      - Ticked 2026-09-22 on session 5 of `docs/evidence/uboot-ums-enumerate.txt`: `29f1:0230` on `usb 3-4` at 480 Mb/s, `/dev/disk/by-id/usb-Linux_UMS_disk_0-0:0`, 249 872 384 sectors = the card. Sessions 1-4 failed because the cable's far end was not this host; the registers said so before the phone test proved it.
- [x] 3.4 Read the card back over `ums` and compare it against the image that
      was written in 3.1. **Hardware proof.**
      Reworded 2026-09-22: the original check — `cmp` of the whole image
      against the device, silent — cannot pass on a card that has booted
      even once. U-Boot's `k230_set_dtb_env()` calls `env_save()` on every
      boot (`board/canaan/common/k230_board_common.c:511`), rewriting the
      environment slot at 3 MiB, and Linux mounts both ext4 partitions
      read-write. The check that replaces it, all read-only over `ums`:
      the BootROM region `[0, 3 MiB)` byte-identical to the image; the five
      partition-1 files (`Image`, `fw_jump_add_uboot_head.bin`, the DTB,
      `bootargs.txt`, `initrd.uimg`) byte-identical via `debugfs` with no
      mount; and every remaining byte read to the end with all differing
      4 KiB blocks confined to mounted ext4 metadata and data, zero in the
      gaps.
      `tools/ums-session.py --cmp <image>`
      Done when region A is identical, the five files are identical, and the
      block statistics show `gap=0` — `docs/evidence/uboot-ums-enumerate.txt`,
      session 8: A identical, 5/5 identical, 5 506 differing blocks all in
      `p1(boot)`/`p2(root)`, `gap=0`, read at 12.0 MB/s.
- [x] 3.5 Measure the write rate, so the claim in design.md is a number and
      not an estimate. **Hardware proof.**
      `sudo dd if="$IMG" of=/dev/disk/by-id/<ums path> bs=4M status=progress oflag=direct`
      Done when the observed MB/s is recorded in `docs/uboot-ums.md` §3.

## 4. Make it the default loop

- [x] 4.1 Teach `tools/flash-latest.sh` a `ums` target, keeping the card
      reader as the fallback and keeping `flash.sh`'s by-id refusal intact.
      Done when the reader path still works unchanged.
- [x] 4.2 Flash a rebuilt image end to end with the card never leaving the
      board, and boot it. **Hardware proof.**
      `./tools/flash-latest.sh /dev/disk/by-id/<ums path>` then reset the
      board and capture the boot.
      Done when `docs/evidence/uboot-ums-hardware.txt` holds a boot log of an
      image that was written over USB.
      - Ticked 2026-09-22: written by `tools/ums-session.py --flash` through `tools/flash.sh` on the by-id path, 175 s, then `reset`; the boot log — SPL banner and PMU training included, for the first time — is in `docs/evidence/uboot-ums-write.txt`, summarised at the end of `uboot-ums-hardware.txt`. Board hashed its own slots to the image's bytes afterwards.

## 5. BootROM recovery (successor change)

BootROM recovery was not tested and is not part of this completed UMS change.
The four unperformed tests are preserved verbatim in the separate,
implementation-ready OpenSpec change `characterise-bootrom-usb-recovery`:
no-card fall-through, SW3/BOOT0 entry, conditional `k230_flash` recovery, and
spec/evidence reconciliation. Nothing here claims that path works.

## 6. Follow-up: keep USB host as well

Optional, and only after group 3 has settled whether it is needed.

- [x] 6.1 Add a `.bind` to `drivers/usb/gadget/dwc2_udc_otg.c` returning
      `-ENODEV` unless `dr_mode` is `peripheral` or `otg`, set
      `dr_mode = "host"` on `&usbotg1`, and re-enable `CONFIG_USB_DWC2`.
      Done when the patch is a file in this repository, not a hand edit in
      `.build/`.
- [x] 6.2 Confirm both work at once. **Hardware proof.**
      `./tools/console.py /dev/ttyACM0 --wait=3 "dm tree; usb start; usb tree"`
      then `ums 0 mmc 1` and check the host.
      Done: `docs/evidence/uboot-usb-host-coexist-v2.txt` and
      `docs/evidence/usb-host-second-candidate-linux.txt` record
      RTL8152 in the U-Boot host tree, UMS enumeration/readback, and return
      to Linux with the shell active. This does not claim packet traffic.

## 7. Record what changed

- [x] 7.1 Record the built stage 1's hashes in the evidence and note in
      `docs/blob-inventory.md` that the configuration changed rather than the
      sources — nothing enters or leaves the inventory. (Rewritten 2026-09-22:
      there is no committed binary or PROVENANCE hash to refresh any more.)
      `nix build .#stage1 && cat result/SHA256SUMS && ./tools/blob-scan.py`
      Done when the hashes are in `docs/evidence/` and the scan exits 0.
- [x] 7.2 Fold the measured numbers and the settled D3 answer back into
      `docs/uboot-ums.md`, so it reads as a record rather than a forecast.
      `./scripts/build_site.py`
      Done when the site build is green and every `docs/` path cited by a
      requirement is committed.
      - Completed 2026-09-22: measured A1 transfer rates and repaired A2
        binding/enumeration are documented, both raw hardware transcripts are
        committed, and the full site build passes (55 pages, 1,100,344 bytes,
        12.63 seconds). See `docs/evidence/usb-host-validation.md`.
