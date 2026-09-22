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
- [ ] 3.3 With a cable from the host to J3, enter `ums` and confirm the host
      sees a block device of the right size. **Hardware proof.**
      board: `./tools/console.py /dev/ttyACM0 --wait=3 "ums 0 mmc 1"`;
      host: `lsblk -o NAME,SIZE,MODEL,TRAN` and `ls -l /dev/disk/by-id/`
      Done when a by-id path exists whose size matches 1.4, and both the
      console and the host output are in
      `docs/evidence/uboot-ums-hardware.txt`.
      - Not ticked, 2026-09-22: `docs/evidence/uboot-ums-enumerate.txt` — `ums 0 mmc 1` runs on the board (`UMS: LUN 0, dev mmc 1 ... count 0xee4c000`, the 119.1 GiB card) and was held for 300 s, but the host saw no new USB device. Sessions 3-4 (a second cable, then a register dump): `GOTGCTL` bit 19 `B_SESSION_VALID` = 1 — the PHY sees VBUS — and after `ums` the core shows D+ pulled up, a bus reset received and enumeration done at full speed; this host's kernel log shows no attach on any bus. A host is on the far end of that cable and it is not this machine. The `u-boot,force-*` properties are inert for `snps,dwc2` in this tree (`dwc2_udc_otg.c:1121`, gated on an STM32-only flag) and were not added. Next: confirm the cable's far end is in this host, same firmware.
- [ ] 3.4 Read the card back over `ums` and compare it against the image that
      was written in 3.1. **Hardware proof.**
      `sudo cmp -n $(stat -c %s "$IMG") "$IMG" /dev/disk/by-id/<ums path>`
      Done when `cmp` is silent. This proves the transport before anything is
      trusted to write through it.
- [ ] 3.5 Measure the write rate, so the claim in design.md is a number and
      not an estimate. **Hardware proof.**
      `sudo dd if="$IMG" of=/dev/disk/by-id/<ums path> bs=4M status=progress oflag=direct`
      Done when the observed MB/s is recorded in `docs/uboot-ums.md` §3.

## 4. Make it the default loop

- [x] 4.1 Teach `tools/flash-latest.sh` a `ums` target, keeping the card
      reader as the fallback and keeping `flash.sh`'s by-id refusal intact.
      Done when the reader path still works unchanged.
- [ ] 4.2 Flash a rebuilt image end to end with the card never leaving the
      board, and boot it. **Hardware proof.**
      `./tools/flash-latest.sh /dev/disk/by-id/<ums path>` then reset the
      board and capture the boot.
      Done when `docs/evidence/uboot-ums-hardware.txt` holds a boot log of an
      image that was written over USB.

## 5. Characterise the recovery paths

- [ ] 5.1 Test whether the BootROM falls through to USB boot with no bootable
      card. Power off, remove the TF card, power on via J3. **Hardware
      proof.**
      `lsusb | grep -i 29f1`
      Done when the evidence file records either `29f1:0230` appearing or
      that it does not.
- [ ] 5.2 Test whether holding `SW3` — the button wired to `BOOT0` — forces
      the same state with the card in. **Hardware proof.**
      Hold `SW3`, apply power, then `lsusb | grep -i 29f1`.
      Done when the result is recorded either way.
- [ ] 5.3 If 5.1 or 5.2 succeeded, write the card with Canaan's own tool and
      confirm the board boots the result. **Hardware proof.**
      `pip install k230-flash` then `k230-flash --help` and a write of the
      current image.
      Done when a board with a deliberately corrupted stage 1 is recovered
      without a card reader — or when it is recorded that this does not work
      here, which is equally useful.
- [ ] 5.4 Update `openspec/changes/.../specs/image/boot-chain/spec.md` to
      remove the two `<!-- UNVERIFIED -->` markers that 3.3 and 5.1 have
      grounded, and cite `docs/evidence/uboot-ums-hardware.txt`.
      `openspec validate --all`
      Done when validation passes and no requirement grounded by this change
      is still marked unverified.

## 6. Follow-up: keep USB host as well

Optional, and only after group 3 has settled whether it is needed.

- [ ] 6.1 Add a `.bind` to `drivers/usb/gadget/dwc2_udc_otg.c` returning
      `-ENODEV` unless `dr_mode` is `peripheral` or `otg`, set
      `dr_mode = "host"` on `&usbotg1`, and re-enable `CONFIG_USB_DWC2`.
      Done when the patch is a file in this repository, not a hand edit in
      `.build/`.
- [ ] 6.2 Confirm both work at once. **Hardware proof.**
      `./tools/console.py /dev/ttyACM0 --wait=3 "dm tree; usb start; usb tree"`
      then `ums 0 mmc 1` and check the host.
      Done when `usb tree` shows the RTL8152 and the host still sees the card
      as a block device.

## 7. Record what changed

- [x] 7.1 Record the built stage 1's hashes in the evidence and note in
      `docs/blob-inventory.md` that the configuration changed rather than the
      sources — nothing enters or leaves the inventory. (Rewritten 2026-09-22:
      there is no committed binary or PROVENANCE hash to refresh any more.)
      `nix build .#stage1 && cat result/SHA256SUMS && ./tools/blob-scan.py`
      Done when the hashes are in `docs/evidence/` and the scan exits 0.
- [ ] 7.2 Fold the measured numbers and the settled D3 answer back into
      `docs/uboot-ums.md`, so it reads as a record rather than a forecast.
      `./scripts/build_site.py`
      Done when the site build is green and every `docs/` path cited by a
      requirement is committed.
      - Not ticked, 2026-09-22: `docs/uboot-ums.md` §9 folds in everything observed so far and `./scripts/build_site.py` is green (108 s), but the measured write rate (3.5) and the settled D3 after-half (3.2) do not exist yet — both need the ums stage 1 on the card.
