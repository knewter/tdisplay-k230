# Tasks

**Not startable until `every-blob-is-built-from-source-or-named` has landed.**
Every stage 1 task below edits U-Boot source, Kconfig or the generated
environment through `nix/uboot-k230.nix` and `nix/stage1.nix`; against the
vendored binaries on `master` there is nothing to edit.

Groups 1, 3 (build half), 4 (build half), 5.1 and 6.1 are **laptop claims**.
Everything that says *hardware* takes the board — say when you take
`/dev/ttyACM0` and when you release it — and is proven by a photograph or a
console capture under `docs/evidence/`. **QEMU proves nothing anywhere in
this change**: its `k230` machine models neither stage 1 nor a display.

## 1. Ground the vendor sources before touching anything

- [x] 1.1 Record LILYGO's U-Boot logo port as evidence: the unified diff of their four `board/canaan/common/logo/` files against the SDK copies on disk, their `k230_canmv_t_display_defconfig` display lines, and their Linux patches `0027`, `0038`, `0051`, with the `Xinyuan-LilyGO/T-Display-K230` commit hash they were read at. Verify by committing `docs/evidence/lilygo-uboot-logo.md` and confirming every path the change's specs cite appears in it — laptop claim
- [x] 1.2 Write the static half of the stage 1 memory map from sources already on disk: every address in `firmware/stage1/tdisplay.env`, the kernel `Image` size and its extent from `0x200000`, OpenSBI's `FW_JUMP_FDT_ADDR`, the initrd size, `CONFIG_SYS_LOAD_ADDR`, `CONFIG_SYS_BOOTM_LEN`, and the vendor logo path's `0x1000000` staging address, each with the file and line it came from. Verify by committing `docs/evidence/stage1-memory-map.md` with a "read from the board" section left explicitly empty for task 2 — laptop claim
- [x] 1.3 Derive the PLL `m`, `n` and `voc` the Linux driver uses for 49.5 MHz / 594 Mbps by working `canaan_dsi_clk_cfg()` (`canaan_dsi.c:316-383`) by hand, and put them beside LILYGO's `{4, 97, 0x19, 0x96}` and the SDK's ST7701 `{9, 196, 0x17, 0xa3}` in one table. Verify by adding the table to `docs/evidence/dsi-hsfreqrange-hardcoded.md` and checking the derived lane rate reproduces the `DSI PHY: lane 594000 kbps` line already in the boot log — laptop claim

**Proves group 1 — laptop claim.** `git diff --stat` showing only `docs/evidence/`, and `./scripts/build_site.py` exiting 0 with the new evidence reachable.

## 2. Read the addresses nobody has written down — **hardware**

- [ ] 2.1 Take the board, interrupt the 5-second countdown and capture `bdinfo` at the U-Boot prompt: `relocaddr`, `reloc off`, `ram_top`, `fdt_blob`, and the malloc base if printed. Verify by committing the transcript into the "read from the board" section of `docs/evidence/stage1-memory-map.md` — hardware claim
- [x] 2.2 Boot normally and capture `bootm`'s own load messages — `Loading Ramdisk to …`, `Loading Device Tree to …` — with `./tools/capture-boot.py`. Verify by committing them to the same document and marking each address in the map as loaded, relocated, or scratch — hardware claim. *Ticked against `docs/evidence/boot-from-source-cold.txt` lines 85-86 (`Loading Ramdisk to 3e135000, end 3fb3fa65` / `Loading Device Tree to 000000000a0eb000, end 000000000a0ff681`) and line 134 (`Domain0 Next Arg1 : 0x000000000a0eb000`): a real cold boot of the current stage 1, accepted by the coordinator as this task's evidence; classified in `stage1-memory-map.md` §2.3.*
- [ ] 2.3 Choose the splash address against the completed map. Start from `0x10000000` / 4 MiB (design.md; `0x1f000000` is rejected there because it sits inside the kernel's CMA pool); move it only if 2.1 shows U-Boot's relocated code or heap within it, or the map shows a stage 1 load reaching it. Verify by writing the chosen address, its size and the reason into the map, and releasing the board — hardware claim for the inputs, a written decision for the output

**Proves group 2 — hardware claim.** `docs/evidence/stage1-memory-map.md` with a `bdinfo` transcript and `bootm` load lines from `/dev/ttyACM0`.

## 3. Stage 1 lights the panel

- [ ] 3.1 Carry LILYGO's logo port into `nix/uboot-k230.nix` as patches applied after the overlay copy, with a Kconfig fragment setting `CONFIG_K230_BARE_DISP_LOGO=y` and `CONFIG_K230_BARE_DISP_LOGO_RM69A10=y`, and replace their `#define RM69A10_LOGO_FB_ADDR` with a Kconfig symbol fed from one flake constant. Verify with `nix build .#uboot-k230` succeeding and `grep -c k230_display_logo result/u-boot` being non-zero — laptop claim
- [ ] 3.2 Change the connector table to the system's mode — 49.5 MHz, 748x1268 total, the `m/n/voc` from 1.3, `hs_freq 0x87` — and match `VID_MODE_CFG` and `DPI_COLOR_CODING` to what `canaan_dsi.c` writes, recording every value that differs from LILYGO's in `docs/evidence/dts-divergence.md`'s table. Verify with `nix build .#uboot-k230` and the divergence table listing each register once — laptop claim
- [ ] 3.3 Add the splash asset derivation: a PNG under `assets/`, rendered to 568x1232 XRGB8888, failing the build unless the output is exactly 2 799 104 bytes (568 x 1232 x 4, the value LILYGO's `RM69A10_LOGO_XRGB_SIZE` check compares `filesize` against; `docs/evidence/lilygo-uboot-logo.md`). Verify with `nix build .#bootSplashImage` and `stat -c %s result/logo.xrgb` printing `2799104` — laptop claim
- [ ] 3.4 Put `logo.xrgb` on the boot partition from `nix/sd-image.nix`, behind the option from 6.1, and add the splash file to the list of things stage 1 requires of the partition in `docs/evidence/uboot-env.txt`. Verify with `nix build .#sdImage` and `debugfs -R 'ls /' <boot partition>` listing `logo.xrgb` beside `Image` — laptop claim
- [ ] 3.5 Add a `reserved-memory` node for the splash buffer to `nix/dts/k230-tdisplay.dts`, taking its `reg` from the same flake constant as 3.1 through the preprocessor. Verify with `nix build .#deviceTree` and `fdtget result/k230-tdisplay.dtb /reserved-memory/framebuffer@10000000 reg` printing the chosen address and size (path adjusted if 2.3 moved it) — laptop claim
- [ ] 3.6 **Hardware.** Flash a second card, keep the known-good one, take the board, and boot. Verify by committing a photograph of the splash on the glass and a `./tools/capture-boot.py` capture in which the moment of the photograph precedes `Starting kernel`, both under `docs/evidence/` and referenced from `docs/evidence/boot-splash.md` — hardware claim
- [ ] 3.7 **Hardware.** Measure the U-Boot-lit image with `tools/panel-measure.py` exactly as `dsi-hsfreqrange-hardcoded.md` measured the Linux one. If it rolls or is dark, fall back to LILYGO's full table (39.6 MHz / `0x96`) to prove the path, then change one parameter at a time until our mode is stable, recording each step. Verify by committing the measurement table to `docs/evidence/boot-splash.md` with motion figures at or below the `0x87` row of the earlier document, and releasing the board — hardware claim

**Proves group 3 — hardware claim.** A photograph plus a timestamped console capture showing the splash before `Starting kernel`, and a measurement showing no roll. The laptop half is `nix build .#uboot-k230 .#bootSplashImage .#deviceTree .#sdImage`.

## 4. The kernel leaves a lit panel alone

- [ ] 4.1 In the U-Boot overlay, set an environment variable only when `k230_display_logo()` loaded the image and sent the init sequence, and in `ft_board_setup()` write it into `/chosen` as a boolean. Verify with `nix build .#uboot-k230` and `strings result/u-boot | grep` finding the property name — laptop claim
- [ ] 4.2 Patch `panel-canaan-universal.c` in `nix/kernel.nix`: read the `/chosen` flag at probe, request the reset GPIO `GPIOD_ASIS` when set, and in `prepare()` skip both reset pulses and the init sequence on the first prepare only, logging that it did and clearing the flag so a later prepare runs the full path. Patch `canaan_drv.c` to skip `drm_fbdev_generic_setup()` when the flag is set. Record both in `docs/evidence/kernel-patches.md` with their drop conditions. Verify with `nix build .#packages.x86_64-linux.xuantie-kernel` succeeding and each `sed` guarded by its `grep -q` as the existing patches are — laptop claim
- [ ] 4.3 **Hardware.** Boot the new kernel on the card from 3.6 and leave the board at the serial prompt with nothing opening the display. Verify by committing a capture to `docs/evidence/boot-splash-handoff.md` showing `/proc/device-tree/chosen` carrying the flag, `dmesg` containing the panel driver's "left as stage 1 set it" line and no `dcs` write from the init sequence, `ls /dev/fb0` failing, and a photograph of the splash still on the glass at the prompt — hardware claim
- [ ] 4.4 **Hardware.** Film the first modeset: with the webcam recording, run `modetest -M canaan-drm -s <connector>:568x1232@XR24` from the serial console with a buffer that reproduces the splash. Verify by committing the frame-by-frame result to `docs/evidence/boot-splash-handoff.md`: either no dark frame across the `k230_display_rst()` reset, or the measured length of the dark interval and whether the panel recovered without its init sequence. **This task decides the fallback**: if it shows a dark interval, restore reset + init in prepare, re-run, record the blink, and restate the boot-splash requirement to what was measured — hardware claim
- [ ] 4.5 **Hardware.** Boot the same kernel on a card with `logo.xrgb` removed. Verify by committing a capture showing the flag absent from `/proc/device-tree/chosen`, the panel driver sending the init sequence, `/dev/fb0` present, and a photograph of the console on the panel — this is the "stage 1 did not light it" scenario and it must still look like `panel-lit.md`. Release the board — hardware claim

**Proves group 4 — hardware claim.** `docs/evidence/boot-splash-handoff.md` with both boots captured and the first-modeset film. The laptop half is `nix build .#packages.x86_64-linux.xuantie-kernel`.

## 5. Something on the Linux side owns the screen

- [ ] 5.1 Measure what Plymouth costs to cross-build for riscv64 against the pinned nixpkgs with the same method as `docs/display-environment-options.md`: derivations to build and unpacked size for `boot.plymouth.enable = true` with a minimal theme, on top of the existing closure. Verify by committing `docs/evidence/boot-splash-owner.md` with the numbers beside the shell stack's 89 / 875 MiB budget and a one-line verdict applying the design's rule — laptop claim
- [ ] 5.2 If 5.1 is within budget: enable `boot.plymouth` in `nix/hardware.nix` with a theme whose first frame is the 3.3 asset, running from the systemd initrd, and remove `console=tty0` from the default command line. Verify with `nix build .#nixosConfigurations.k230.config.system.build.toplevel` and `lsinitrd`-equivalent inspection of the initrd showing `plymouthd` and the theme present — laptop claim
- [ ] 5.3 If 5.1 is over budget: add a minimal DRM splash program to the closure — opens `/dev/dri/card0`, sets the mode with a dumb buffer holding the 3.3 asset, holds it, and exits on a signal from the shell's session without clearing — and start it as the first thing in the main system. Verify with `nix build .#nixosConfigurations.k230.config.system.build.toplevel` and the unit present in the closure; record in `docs/evidence/boot-splash-owner.md` that there is no animation and why — laptop claim
- [ ] 5.4 **Hardware.** Film a complete boot from power-on to the owner's last frame — and, if `the-screen-runs-a-shell-not-a-console` has landed, to the compositor's first frame. Verify by committing the frame timings to `docs/evidence/boot-splash-handoff.md` showing no dark frame between the splash appearing and the last frame filmed, and the first Linux frame indistinguishable from the last stage 1 frame. Release the board — hardware claim

**Proves group 5 — hardware claim.** The filmed boot in `docs/evidence/boot-splash-handoff.md`. The laptop half is `nix build .#nixosConfigurations.k230.config.system.build.toplevel` with the measurement committed.

## 6. The switch, and the specs

- [ ] 6.1 Add `k230.panelConsole` (default false) to the NixOS module: true keeps `console=tty0` and omits `logo.xrgb` from the boot partition; false does the reverse. Verify with `nix eval .#nixosConfigurations.k230.config.system.build.toplevel.drvPath` succeeding with the option in both states, and `nix build .#sdImage` with it true producing a boot partition without `logo.xrgb` — laptop claim
- [ ] 6.2 Resolve the `UNVERIFIED` markers in `display/boot-splash` and `image/boot-chain` against the captures from groups 3, 4 and 5, restating any requirement 4.4 changed, and confirm every carried patch is in `docs/evidence/kernel-patches.md` as `system/kernel` requires. Verify with `openspec validate the-screen-lights-before-linux` and `./scripts/build_site.py` exiting 0

**Proves group 6.** `openspec validate --all` and `./scripts/build_site.py` both exiting 0.
