## 1. Research and proposal

- [x] 1.1 Record upstream U-Boot/OpenSBI K230 support, the vendor overlay pieces to port with sizes, and prior art in `design.md`; verify with `openspec validate --strict the-board-boots-a-modern-u-boot`. Done 2026-10-30 (source reading only: upstream tags v2026.10 and OpenSBI v1.9, vendor SDK `1104236`).
- [ ] 1.2 Land the proposal on `master`; verify with `python3 scripts/render_work_board.py` and a green CI run for the pushed commit.

## 2. Stage a: modern U-Boot proper, host build

- [ ] 2.1 Pin U-Boot v2026.10 and build upstream's own `k230_canmv_defconfig` unchanged under `nix/`; verify with `nix build .#uboot-k230-modern-upstream` (host build only; shows the toolchain and upstream baseline compile).
- [ ] 2.2 Add the T-Display board: defconfig, dts (1 GiB, uart0, mmc1, usb0 peripheral, usb1 host, pinctrl table), `early_init` port of `harts_early_init`, cache enable port; verify with `nix build .#uboot-k230-modern` and `fdtget` over the built dtb (host build only).
- [ ] 2.3 Port the K230 SDHCI PHY setup as a variant of upstream `snps_sdhci.c`, with `ENV_IS_IN_MMC` at `0x300000`/`0x320000` and `mmc_boot_dev_num=1`; verify with the same `nix build` plus a check that `CONFIG_MMC_SDHCI_SNPS=y` and `CONFIG_ENV_OFFSET=0x300000` are in the built `.config` (host build only).
- [ ] 2.4 Port USB gadget `ums` on usb0 with the PHY pull-down handling; verify `CONFIG_CMD_USB_MASS_STORAGE=y` and the vendor/product IDs `29f1:0230` in the built `.config` (host build only; gadget enumeration is task 5.2).
- [ ] 2.5 Port the RM69A10 logo path (vendor `logo/*` from the SDK pin plus patches 0004/0005 rebased), the `canaan,stage1-splash` fdt fixup and the `k230_set_dtb` command; verify `nix build .#uboot-k230-modern` and that `nix/boot-splash.nix` is the single source of the framebuffer address (host build only).
- [ ] 2.6 Carry the Game of Life boot-frame hook forward on native `cyclic` without editing the other worktree's files: record the call-site mapping in `design.md` and verify by building the modern tree with `CONFIG_CYCLIC=y` (host build only; do not duplicate that change's tasks).
- [ ] 2.7 Package the result as the five stage-1 files in the layout `nix/stage1.nix` already expects (new attribute `.#stage1-modern`), asserting the U-Boot slot fits in 1 MiB, the K230 magic, CM byte `0x09`; verify with `nix build .#stage1-modern` and compare `SHA256SUMS` field list with `.#stage1` (host build only).

## 3. Stage a0: RAM trial (board, no boot-firmware write)

- [ ] 3.1 Read-only board check from the running 2022.10 console: `bdinfo`, `md` of `0x0`, caches state; record under `docs/evidence/modern-uboot/`; verify with the board console transcript (real board, read-only).
- [ ] 3.2 Stage the modern binary on `/boot` and run it from the 2022.10 prompt; verify with a console transcript showing the modern banner, `mmc info`, `ext4ls mmc 1:1`, two `crc32` runs of a large `ext4load` agreeing, and a full `blinux` to login (real board, console).
- [ ] 3.3 Run `ums 0 mmc 1` from the RAM-trial U-Boot and enumerate it on the host (J3 to the host directly); verify with `lsusb`/by-id listing and a read of the 2 MiB slot compared with the saved image (real board, console + host).

## 4. Install and recovery procedure (review gate)

- [ ] 4.1 Save the 2022.10 slot (2 MiB, 1 MiB long), both SPL copies and both env copies from the card with hashes under `docs/evidence/modern-uboot/preinstall.txt`, and copy `fn_ug_u-boot.2022.10.bin` to `/boot`; verify with `sha256sum` equalities (real board or card reader).
- [ ] 4.2 Write the exact write/rollback procedure (offsets, commands, preserved regions, console evidence per step) into `docs/modern-uboot-install.md`; verify by review by the coordinator. **Stop here until the coordinator approves.**

## 5. Stage a: install on the board (after 4.2 approval)

- [ ] 5.1 Write only the U-Boot slot at `0x200000`; verify raw read-back hash equals `.#stage1-modern` `SHA256SUMS` and SPL/env regions are byte-identical to 4.1 (real board, ums or reader).
- [ ] 5.2 Cold boot: verify console banner, splash lit, `ums` enumerates `29f1:0230` on J3, `blinux` reaches the shell, kernel log reports the panel left as found (real board: console + `grim` capture).

## 6. Stage b: modern SPL

- [ ] 6.1 Prove the BootROM recovery route on a disposable card (owned by `characterise-bootrom-usb-recovery` group 2); verify with that change's evidence files. Stage b write tasks stay blocked until this is done.
- [ ] 6.2 Measure whether the BootROM falls back to the second SPL copy at `0x180000` when the first is invalid (disposable card only).
- [ ] 6.3 Port SPL, DDR init (1 GiB LPDDR4 2667), SPL SD load and the U-Boot decompress path; verify with `nix build .#uboot-k230-modern-spl` and an SPL size check below `CONFIG_SPL_SIZE_LIMIT` (host build only).
- [ ] 6.4 Install and boot (after a reviewed procedure): console shows SPL banner, PMU training lines, 1 GiB, `mtest` pass, shell (real board, console).

## 7. Stage c: modern OpenSBI

- [ ] 7.1 Build OpenSBI v1.9 with the MAEE-clear forward-port and the unchanged `FW_JUMP_FDT_ADDR` departure; verify with `nix build .#opensbi-k230-modern` and a disassembly check that `FW_JUMP_ADDR=0x200000` (host build only).
- [ ] 7.2 Replace `/fw_jump_add_uboot_head.bin` on `/boot` and boot; verify banner `OpenSBI v1.9`, `Domain0 Next Arg1` equal to `bootm`'s DTB address, `mxstatus.MAEE=0`, shell up (real board, console).

## 8. Close-out

- [ ] 8.1 Rename `nix/uboot-k230.nix`/`opensbi-k230.nix` users to the modern ones only after 5.2/6.4/7.2, update `openspec/config.yaml` stage 1 term, `docs/blob-inventory.md`, and run `openspec validate --all`; then archive per AGENTS.md.
