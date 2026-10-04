## 1. Research: what mainline actually supports

- [x] 1.1 Determine the current kernel.org latest stable/longterm and the
      newest mainline tag/commit carrying any Canaan K230 support, cited by
      exact tag diff (`git show v7.2:arch/riscv/boot/dts/canaan/` vs.
      `master`). Recorded in
      `docs/research/mainline-kernel-inventory.md` ("Target version").
- [x] 1.2 Build the full hardware-function-by-function mainline status table,
      checking every driver-file claim directly
      (`gh api repos/torvalds/linux/contents/<path>`, 200/404) rather than
      inferring from changelogs. Recorded in the same document's
      "Inventory" table.
- [x] 1.3 Check each of our eleven vendor-kernel patches individually against
      the file it targets upstream, and record a per-patch port/no-port
      disposition, not an aggregate one. Recorded in the same document's
      "Our eleven vendor-kernel patches" section (net result: zero port,
      one already fixed upstream by an independent change, ten target files
      that do not exist upstream).
- [x] 1.4 Write the phased plan, naming the actual first hardware milestone
      correctly ("reaches the serial console", not "SD rootfs", since SD is
      still in review upstream). Recorded in the same document's "Phased
      plan" section.

## 2. Nix: a parallel mainline kernel source pin and build

- [x] 2.1 Pin the mainline commit in `nix/kernel-mainline-src.nix`
      (`fetchFromGitHub torvalds/linux`, dereferenced `v7.3-rc5` commit
      `72d3fcf802c45d00b300f25b848a93c3a2bd7c7e`), hash obtained with
      `nix run nixpkgs#nix-prefetch-github -- torvalds linux --rev
      72d3fcf802c45d00b300f25b848a93c3a2bd7c7e`.
- [x] 2.2 Add `nix/kernel-mainline.nix`: `defconfig = "defconfig"`,
      `autoModules = false`, `ARCH_CANAAN`/`PINCTRL_K230`/`RESET_K230`/
      `COMMON_CLK_K230` turned on, an initrd-capable config
      (`BLK_DEV_INITRD`/`RD_GZIP`/`RD_ZSTD`) with no initramfs content
      supplied yet. Wire `packages.kernelMainline` in `flake.nix` via
      `pkgsCross.linuxPackagesFor`, parallel to but independent of
      `k230Kernel`/`packages.kernel`.
      Proven: `nix build .#kernelMainline --out-link result-kernelMainline
      --max-jobs 2 --cores 8 --print-out-paths` exited 0, producing
      `/nix/store/7idv37hka94mcgnkw0cf6ggrdp8aypky-linux-riscv64-unknown-linux-gnu-7.3.0-rc5`
      (rooted at `result-kernelMainline` in this worktree) — a real
      `file`-confirmed "Linux kernel RISC-V boot executable Image,
      little-endian", 38 504 448 bytes, plus `System.map` and a `dtbs/`
      tree. The generated `.config` was checked directly and carries
      `CONFIG_ARCH_CANAAN=y CONFIG_PINCTRL_K230=y CONFIG_RESET_K230=y
      CONFIG_COMMON_CLK_K230=y CONFIG_BLK_DEV_INITRD=y`. Build proof
      only — no board exists this could have booted on yet.

## 3. Nix: a parallel mainline board device tree

- [x] 3.1 Add `nix/dts/k230-tdisplay-mainline.dts` (mainline's own
      `k230-evb.dts` as template; our board's own 1 GiB memory size and
      model/compatible strings, per design.md decision 3) and
      `nix/device-tree-mainline.nix` (same dtc-invocation shape as
      `nix/device-tree.nix`, against `kernelMainlineSrc` headers). Wire
      `packages.deviceTreeMainline` in `flake.nix`.
      Proven: `nix build .#deviceTreeMainline --out-link
      result-deviceTreeMainline --max-jobs 2 --cores 8 --print-out-paths`
      exited 0, producing
      `/nix/store/0bwb48mn4dzz8ihhsvh9mrhx6gvixd5a-k230-tdisplay-mainline.dtb`,
      and the derivation's own round-trip check (`dtc -I dtb -O dts`)
      passed as part of that same build. Independently re-decompiled after
      the build (`dtc -I dtb -O dts result-deviceTreeMainline/k230-tdisplay-mainline.dtb`)
      to confirm by hand: `compatible = "lilygo,t-display-k230",
      "canaan,kendryte-k230"`, `ddr: memory@0 { reg = <0x00 0x00 0x00
      0x40000000>; }` (1 GiB, matching the vendor board file, not the
      512 MiB `k230-evb.dts` default), `aliases { serial0 =
      "/soc/serial@91400000"; }`, and `uart0`'s `status = "okay"`. Build
      proof only.

## 4. Nix: a boot-files bundle for a future one-shot board test

- [x] 4.1 Add `packages.kernelMainlineBootFiles` in `flake.nix`: a plain
      directory collecting `Image-mainline` and
      `k230-tdisplay-mainline.dtb` under clear names (not the vendor
      blinux flow's fixed `/Image`/`/force.dtb`, since this is a different,
      manual `ext4load` flow the coordinator will drive — see design.md
      decision 5 for why no initrd is bundled yet).
      Proven: `nix build .#kernelMainlineBootFiles --out-link
      result-kernelMainlineBootFiles --max-jobs 2 --cores 8
      --print-out-paths` exited 0, producing
      `/nix/store/23civ9kg8yr675wmlmdjbc718m0hjffv-k230-mainline-boot-files`
      containing exactly `Image-mainline` (38 504 448 bytes) and
      `k230-tdisplay-mainline.dtb` (4660 bytes). Build proof only.

## 5. Milestone 1: boot-critical SD/GPIO/USB forward-port and a full system variant

Coordinator-directed continuation, after the coordinator merged `c5158fa8`
to `master`: "do the actual porting ... so it can mount our SD rootfs."

- [x] 5.1 Forward-port GPIO (`drivers/gpio/gpio-k230.c`), SD/MMC
      (`drivers/mmc/host/sdhci-of-kendryte.c`) and USB
      (`drivers/usb/dwc2/{params.c,core.h,core.c}` hunks) from the pinned
      vendor tree, plus the matching DT nodes in
      `nix/dts/k230-tdisplay-mainline.dts` (real `&sysclk`/`&rst` phandles
      from mainline's own `<dt-bindings/clock/canaan,k230-clk.h>`/
      `<dt-bindings/reset/canaan,k230-rst.h>`, replacing the vendor tree's
      unimplemented `&dummy_sd`/`&clk_dummy` stub clocks). Two real
      vendor-to-mainline API migrations found via failed builds and fixed
      against mainline's own already-migrated reference drivers
      (`gpio-dwapb.c`, `sdhci-of-dwcmshc.c`) — see the new spec requirement
      "Forward-ported drivers are grounded in the vendor tree and checked
      against the pinned mainline API" for the exact citations.
      Proven: `nix build .#kernelMainline --out-link result-kernelMainline
      --max-jobs 2 --cores 8 --print-out-paths` exited 0, producing
      `/nix/store/appd6jgmwfr6rg4k18zjv155xc5841lm-linux-riscv64-unknown-linux-gnu-7.3.0-rc5`
      (38 522 368-byte Image). The generated `.config` carries
      `CONFIG_GPIO_K230=y CONFIG_MMC=y CONFIG_MMC_SDHCI=y
      CONFIG_MMC_SDHCI_PLTFM=y CONFIG_MMC_SDHCI_OF_DWCMSHC_KENDRYTE=y
      CONFIG_USB=y CONFIG_USB_DWC2=y`, confirmed by direct `grep`. Also
      confirmed: `nix build .#deviceTreeMainline` still exits 0 and its
      DTB's `gpio0`/`gpio1`/`usb0`/`usb1`/`mmc_sd0`/`mmc_sd1` nodes
      round-trip with resolved `&sysclk`/`&rst` phandles (`dtc -I dtb -O
      dts`, checked by hand). Build proof only — none of this has probed
      real hardware; the clock-gate/reset-ID choices for these three
      peripherals are UNVERIFIED best-effort mappings, named as such in
      `nix/dts/k230-tdisplay-mainline.dts`'s own header.
- [x] 5.2 Add a full NixOS system variant,
      `nixosConfigurations.k230-mainline-console`, substituting
      `kernelMainline` for the vendor kernel via the same specialArg
      mechanism `k230-rvv-trial` already uses, based on the shell-off
      `k230-console` (not the coordinator's suggested
      `k230-coherent-shell-mainline` name — deviation flagged in
      `flake.nix`'s own comment and in this change's report: the graphical
      shell's Sway/wlroots stack wants a DRM/KMS device mainline does not
      provide yet, and its build would either fail or produce services
      that cannot start). `boot.extraModulePackages`/`boot.kernelModules`
      force-cleared to drop the out-of-tree RTL8189FTV module, which
      `nix/hardware.nix` builds against `config.boot.kernelPackages.kernel`
      dynamically and has no expectation of compiling against a kernel
      seven major versions newer than its 6.6-era origin.
      Proven: `nix build .#toplevel-mainline-console --out-link
      result-toplevel-mainline-console --max-jobs 2 --cores 8
      --print-out-paths` exited 0, producing
      `/nix/store/d488a1cibw8r7ip7hbbb9j52hy0kzb0h-nixos-system-nixos-26.11.20260919.20b1ddd`.
      The build log confirms no `k230-wifi-driver` derivation was built at
      all (the `mkForce [ ]` overrides took effect) and that
      `unit-k230-wifi.service-disabled.drv` was built instead of the
      enabled unit. Build proof only.
- [x] 5.3 Add `nix/kernel-mainline-boot-files.nix` and wire
      `packages.kernelMainlineConsoleBootFiles`: Image, a DTB with this
      system's real bootargs baked into `/chosen` (`fdtput`, same mechanism
      `nix/sd-image.nix` already uses — `cfg.boot.kernelParams` +
      `init=${toplevel}/init`, deliberately with **no** hardcoded `root=`
      device path, since this system's inherited `fileSystems."/" =
      { device = "/dev/disk/by-label/NIXOS_SD"; }` already resolves root by
      ext4 label through the initrd's own fstab — matching the vendor
      image's own proven mechanism instead of guessing an `mmc_sd1` device
      node path), and the system's initrd wrapped as a U-Boot ramdisk image
      (`mkimage`, same invocation shape as `nix/sd-image.nix`'s
      `initrd.uimg`).
      Proven: `nix build .#kernelMainlineConsoleBootFiles --out-link
      result-kernelMainlineConsoleBootFiles --max-jobs 2 --cores 8
      --print-out-paths` exited 0, producing
      `/nix/store/d0idhc2j28n3nn4q1cwq2lin69rnx76r-k230-mainline-console-boot-files`
      containing `Image-mainline` (38 522 368 bytes), `k230-tdisplay-mainline.dtb`
      (7974 bytes, `/chosen/bootargs` confirmed by `dtc -I dtb -O dts`:
      `"console=tty0 consoleblank=0 console=ttyS0,115200n8 root=fstab
      loglevel=4 lsm=landlock,yama,bpf loglevel=7
      init=/nix/store/d488a1cibw8r7ip7hbbb9j52hy0kzb0h-.../init"`), and
      `initrd.uimg` (`file`-confirmed "u-boot legacy uImage, initrd,
      Linux/RISC-V, RAMDisk Image", 27 313 961 bytes uncompressed, CRCs
      present). Build proof only.
- [x] 5.4 Confirm `nix flake check --no-build` still passes with all new
      outputs (it does: `nixosConfigurations.k230-mainline-console` and
      every new package evaluate cleanly) and that no existing output's
      derivation changed:
      `git diff --stat 4ffe809a1b448f98379ea1165d7bca067d01cfdb -- nix/kernel.nix
      nix/kernel-src.nix nix/device-tree.nix nix/k230.nix nix/hardware.nix
      nix/sd-image.nix nix/shell.nix` returns empty.

What remains stubbed after this task group: no rootfs population step —
this milestone produces the boot files, not a card image, and does not
place this system's own closure/profile symlink onto the physical card's
root partition (an explicit non-goal, since a re-flash is out of scope
here per the task's hard rules). No board boot has been attempted or
claimed. `&mmc_sd0` (Wi-Fi SDIO) stays disabled — no driver forward-ported
for it in this task group. Display, touch, audio, PMU/power-key, thermal,
ADC, and crypto remain exactly as inventoried (no mainline driver to port
from); RTC is picked up in task group 5a below.

## 5a. Milestone 3 (partial): RTC forward-port

Coordinator's milestone 3 named touch/RTC/PMU/thermal/ADC/audio "each
forward-ported from the vendor tree with our patches applied." RTC is the
one attempted in this pass — smallest, most self-contained, most
API-stable (RTC-class subsystem) of the group, and a genuine, small proof
that milestone 1's methodology extends.

- [x] 5a.1 Forward-port `drivers/rtc/rtc-k230.c` from the pinned vendor
      tree to `nix/patches/mainline/rtc-k230.c`, carrying this project's
      own already-board-proven `k230-rtc-mday-mask.patch` fix forward
      directly in the copied file (0xf → 0x1f day-of-month mask) rather
      than reintroducing a bug already found and fixed once. One trivial
      fix needed beyond that: `.remove_new` (a transitional
      `struct platform_driver` field from this file's 6.6-era origin)
      does not exist at `v7.3-rc5` — renamed to `.remove` (the function
      already had the matching `void(*)(struct platform_device *)`
      signature). Built cleanly otherwise, on the first attempt. Added
      `rtc@91000c00` to `nix/dts/k230-tdisplay-mainline.dts`
      (`compatible = "canaan,k230-rtc"`, `status = "okay"`, no
      clocks/resets property — the driver calls neither `devm_clk_get()`
      nor `devm_reset_control_get()` anywhere) and `RTC_DRV_K230 = yes;`
      in `nix/kernel-mainline.nix`.
      Proven: `nix build .#kernelMainline --out-link result-kernelMainline
      --max-jobs 2 --cores 8 --print-out-paths` exited 0, `.config`
      confirmed to carry `CONFIG_RTC_DRV_K230=y` by direct `grep`;
      `nix build .#deviceTreeMainline` still exits 0 and round-trips with
      `rtc@91000c00` present (`dtc -I dtb -O dts`, checked by hand); `nix
      build .#toplevel-mainline-console` and
      `.#kernelMainlineConsoleBootFiles` both still exit 0 with RTC
      included; `nix flake check --no-build` passes. Build proof only.
- [x] 5a.2 Scope (not complete) milestone 2 (display): a scratch trial
      forward-porting the vendor's full `canaan_drv.c`/`canaan_vo.c`/
      `canaan_dsi.c`/`canaan_phy.c`/`canaan_plane.c` + `panel-canaan-
      universal.c` (~3,900 lines, before re-applying this project's own
      ~10 existing patches against the panel/DSI/VO files) was attempted
      as scoping, not as a claimed forward-port. Findings: one Kconfig fix
      (a driver below `if DRM` cannot itself `select DRM` — circular
      dependency; `depends on DRM` instead), one already-removed Kconfig
      symbol (`DRM_KMS_DMA_HELPER`), and then a real, structural DRM API
      change on the very first file checked: `drm_panel_init()` was
      replaced upstream by a refcounted `devm_drm_panel_alloc()`
      allocation model (`include/drm/drm_panel.h`), changing how the
      panel struct itself is allocated, not just a symbol name. This is a
      materially larger class of problem than GPIO/SD-MMC/USB/RTC (DRM
      atomic-modeset/bridge/connector/component-framework churn across
      five interconnected files, plus re-applying this project's own
      panel/DSI/VO patches on top of whatever the ported base ends up
      looking like) and was **not carried to completion** — the trial was
      reverted (`git checkout -- nix/kernel-mainline.nix`, the scratch
      `nix/patches/mainline/drm/` directory deleted) rather than committed
      half-working, since `.#kernelMainline` must stay buildable per this
      change's own spec requirement. `git status`/`git diff` confirm the
      revert is complete and the tree matches the previous commit exactly
      for `nix/kernel-mainline.nix`.

## 5b. Milestone 2 continuation: isolated mainline DRM display

- [x] 5b.1 Port the Canaan DRM/DSI/panel sources against the pinned mainline API, then verify the copied driver objects and required DRM/input Kconfig resolution; preserve the exact command and limits in `docs/evidence/mainline-display-api-compile.md` and its log. After the full-build link exposed missing bridge-helper selections, Canaan Kconfig selects `DRM_DISPLAY_HELPER`/`DRM_BRIDGE_CONNECTOR`; the rerun resolved both symbols and compiled the modules. See `docs/evidence/mainline-display-api-compile.log` and `docs/evidence/mainline-display-full-build.log`.
- [x] 5b.2 Build the complete candidate kernel derivation with `nix build .#kernelMainlineDrm --print-out-paths`; the combined build completed successfully and produced `/nix/store/qa041skh6iy7rmx86c5zfn2xyq036f0g-linux-riscv64-unknown-linux-gnu-7.3.0-rc5` (`docs/evidence/mainline-display-full-build.log`).
- [x] 5b.3a Add a separately named, opt-in mainline DRM display/touch DT source and verify preprocessing, dtc compilation, and round-trip decompilation; record the host-only result and any compiler warnings in `docs/evidence/mainline-display-dtb.md` and its log.
- [x] 5b.3b Build the complete candidate device-tree derivation with `nix build .#deviceTreeMainlineDrm --print-out-paths`; the combined build produced `/nix/store/8v2v53z2qpxapsq507nvxsmld4y24d13-k230-tdisplay-mainline-drm.dtb` (`docs/evidence/mainline-display-full-build.log`).
- [x] 5b.4a Add a separately named boot-files output pairing only the candidate kernel image and DTB; it does not change any normal boot/default output.
- [x] 5b.4b Build and inspect that output with `nix build .#kernelMainlineDrmBootFiles --print-out-paths`; `/nix/store/bpbr6vldkm1y48k6wrdh7s6yv5szqa0k-k230-mainline-drm-boot-files` contains only the candidate Image and DTB, byte-identical to the derivation outputs (`docs/evidence/mainline-display-artifact-inspection.log`).
- [x] 5b.4c Prepare a matching opt-in console trial system and boot bundle with its own initrd, volatile bootargs, closure inventory and registration; document offline root staging and manual U-Boot trial/restoration. Host proof: `nix build .#kernelMainlineDrmTrialBootFiles --no-link --print-out-paths --max-jobs 1 --cores 4` and `nix shell --inputs-from . nixpkgs#dtc --command python3 tools/mainline-drm-trial-inspect.py <output-path>`. The built bundle is `/nix/store/9v5jwcg97kp96jfj6nll4a4yixxzqh2x-k230-mainline-drm-trial-boot-files`; see `docs/evidence/mainline-display-boot-preparation.md` and its log. This does not stage a physical card or satisfy 5b.5.
- [ ] 5b.5 After staging a compatible usable root path following `docs/evidence/mainline-display-boot-preparation.md` (the built `kernelMainlineDrmBootFiles` contains only the Image and DTB, with no initrd or root filesystem), reserve the board and perform a recoverable manual U-Boot trial. Capture the serial log with `flock /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=10`, plus a panel photograph and deliberate touch interaction. The candidate's display power-domain behavior remains UNVERIFIED until observed on hardware; the locally forward-ported provider planned in group 5c does not turn a host build into physical proof.
- [x] 5b.6 Explicitly scope the display power-domain provider gap: pinned mainline has no `sysctl_power`/`K230_PM_DOMAIN_DISP` provider, so the initial host candidate omitted that unsupported phandle (see `docs/evidence/mainline-display-dtb.md`). Group 5c now adds an isolated local provider; physical display power remains UNVERIFIED.

## 5c. Keep the optional DRM display domain powered

The coordinator authorized this bounded continuation after the source audit
found prior vendor-board evidence (`docs/evidence/dsi-phy-hang.md`) of DSI
all-ones reads and DCS timeouts without a held DISP runtime-PM reference.
Upstream at the pin still lacks the provider; a local port is opt-in only.

- [x] 5c.1 Forward-port the pinned vendor `drivers/soc/canaan/k230-power-domains.c` and its five-domain binding/table into the separate DRM candidate. Keep vendor register/repair semantics; remove unused hardlock state, make controller/domain state per-device, check genpd setup/provider errors and clean up partial registration. Enable only in `kernelMainlineDrm`. Host proof: `nix build .#kernelMainlineDrm --no-link --print-out-paths` and record the source/API/build limits in `docs/evidence/mainline-display-power-domain.md` and its log.
- [x] 5c.2 Add the matching binding header/provider node at the vendor's `0x91103000` register range and connect only the candidate's logical display subsystem to `K230_PM_DOMAIN_DISP`. Retain existing clock/reset choices. Host proof: `nix build .#deviceTreeMainlineDrm --no-link --print-out-paths`, round-trip the DTB, and inspect the provider reg/cells and consumer phandle in the evidence log. Passed: `/nix/store/nxbrd4smrcmknipjn4hjk32n87p4g9k6-k230-tdisplay-mainline-drm.dtb`; provider phandle `0xd`, consumer `<0xd 2>`, register tuple `<0 0x91103000 0 0x1000>`, one domain cell, two existing single-child graph warnings.
- [x] 5c.3 Preserve the DRM master's probe-time held runtime-PM reference, but handle a failed resume and release/disable on probe failure and removal. Host proof: `nix build .#kernelMainlineDrm --no-link --print-out-paths`; source/API/build proof only. Passed: `/nix/store/i77i3ppi72k9hw0v2xmnhilc3q7rvv50-linux-riscv64-unknown-linux-gnu-7.3.0-rc5`; full kernel log includes the provider and DRM master object compilations.
- [x] 5c.4 Rebuild `nix build .#kernelMainlineDrmTrialBootFiles --no-link --print-out-paths` and run `nix shell --inputs-from . nixpkgs#dtc --command python3 tools/mainline-drm-trial-inspect.py <output-path>`. Record exact bundle/system/kernel paths, unchanged default/console inputs, and the retained 5b.5 physical gate. Validate with `openspec validate the-board-runs-a-mainline-kernel --strict`. Passed: bundle `/nix/store/gf3aqks2dg0z3ksz33ysfprnlbk83vw3-k230-mainline-drm-trial-boot-files`, system `/nix/store/k9f4r2i9k9qj58z8z4l2kssy9rpwxxm1-nixos-system-nixos-26.11.20260919.20b1ddd`, kernel `i77i3ppi72k9hw0v2xmnhilc3q7rvv50`; matching artifact/CRC checks and `nix flake check --no-build` passed. Source/build evidence only; 5b.5 remains unchecked.

## 5d. Recoverable optional mainline restart

The source audit is committed in
`docs/evidence/mainline-display/physical-2026-10-01/mainline-restart-source-audit-2026-10-02.md`.
The vendor restart sequence is read-source grounding; its behavior in this
mainline candidate remains UNVERIFIED. This group does not close 5b.5.

- [x] 5d.1 Add a narrow vendor-derived restart patch to `kernelMainlineDrm` only. Preserve the vendor `0x91102060` register, bits 0/16, priority 128 and terminal wait; use the pinned managed sys-off API, checked probe-time mapping/registration and cleanup. Compile the changed reset object against pinned prepared headers and prove Nix patch application/evaluation; record exact reproducible commands, source hashes and limits in `docs/evidence/mainline-restart/README.md`. Proof: `bash docs/evidence/mainline-restart/object-check.sh` and `nix build .#kernelMainlineDrm.src --no-link --print-out-paths` (source derivation only; not a complete kernel or hardware reset). Passed on 2026-10-02: patched source `vnzm30w6v4na0ylpw8vclyn7dn9vvkf0`, host LLVM 22.1.8 prepared-header RISC-V object with `W=1` and no warnings; exact commands/hashes/limits are committed in the named evidence. The first full GCC run found `-Werror=return-type`; the vendor unreachable zero return is restored as `NOTIFY_DONE`, and corrected source `jvz4v73g8a67pqwm06v079h6s1cpqr9s` passes the pinned GCC 15.3.0 object check with `W=1`. The failed complete run remains recorded separately.
- [x] 5d.2 Reserve the shared build slot and build the exact patched complete candidate. Proof: `flock /tmp/k230-nix-build.lock nix build .#kernelMainlineDrm --no-link --print-out-paths --max-jobs 1 --cores 16`; preserve the full log, Image SHA-256, store path and effective reset config. Full Nix build proof only. Passed: corrected kernel `4wkhxf55y1abg1kg2xd0acsfjqr64j0h`, Image SHA-256 `70a81b2172710c64463b53693e2e505a4d82ae2f7b644b2fc93cee9016b05330`; full corrected and failed GCC logs are committed separately.
- [x] 5d.3 Build and inspect the matching trial bundle and compare vendor/default/console-only derivation identities with the base. Proof: `flock /tmp/k230-nix-build.lock nix build .#kernelMainlineDrmTrialBootFiles --no-link --print-out-paths --max-jobs 1 --cores 16`, then `nix shell --inputs-from . nixpkgs#dtc --command python3 tools/mainline-drm-trial-inspect.py <bundle-path>` and `openspec validate the-board-runs-a-mainline-kernel --strict`. Record exact kernel/system/initrd/DTB/bundle identities and unchanged default outputs in `docs/evidence/mainline-restart/README.md`. Passed: bundle `asj7l4zj5jrjkgng4nrcx3y72p7jf7aa`, system `v9qc1sf0iz53s3x6g6vwfyaxghkfpnyk`; inspector verifies Image/DTB/initrd/CRC and 629-path inventory. Nine base-relative vendor/default/console derivation identities match; corrected-source flake evaluation and strict OpenSpec validation pass. This does not stage or boot the board.
- [x] 5d.4 After source review and matching bundle proof, the board operator performs a recoverable trial with the protected normal boot selection retained. Proof: serial capture using `flock /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=10`, plus the exact named controller invocation and matching artifact hashes. Require a real kernel restart request, subsequent U-Boot SPL/normal-system boot, a fresh boot ID, protected normal identities/hashes and shell postflight. Commit transcript/timestamps/limits under `docs/evidence/mainline-restart/`. A systemd chroot refusal, manual power cycle or host build does not satisfy automatic restart; physical restart stays UNVERIFIED until observed. Keep 5b.5 open for usable mainline root and deliberate touch.
      Physical proof on 2026-10-02: the exact named minimal runtime-trace comparison with volatile `clk_ignore_unused` returned a real kernel restart, subsequent SPL/normal boot, fresh boot ID, exact protected identities, three active shell services and eight unchanged hashes. Controller exit 0; command, selected artifacts, transcript excerpt, raw hash/timestamp and reviewed normal Home are committed in `docs/evidence/mainline-restart/physical-clock-comparison-2026-10-02/README.md`. This qualifies the diagnostic boot only: baseline without the flag still stalls, permanent global bypass is not enabled, and proper SD1 clock consumers plus restart without the flag remain necessary before usable-root/touch task 5b.5 can close.
      Subsequent no-bypass physical proof: the targeted five-clock candidate `9vdk79…` / `5yqilsfy…` / `9gdms…` passed ordinary unused-clock cleanup, runtime tracing and real automatic restart → SPL → protected normal postflight with controller exit0, fresh bootID, three services and eight unchanged hashes, without `clk_ignore_unused`. Exact command/artifacts/transcript/hash/timestamp are committed in `docs/evidence/mainline-sd1-clocks/physical-no-flag-2026-10-03/README.md`. Ordinary root and deliberate touch stay open in5b.5.
      Host preparation on 2026-10-02: minimal-only `--debug-shutdown` adds volatile `initcall_debug loglevel=8` to the existing exact `asj7l4zj5jrjkgng4nrcx3y72p7jf7aa` bundle, with exact printed-bootargs validation and a fresh rolling recovery buffer. The 71-test controller suite and strict change validation pass; source checkpoints, operator command, and host-only limits are recorded in `docs/evidence/mainline-restart/shutdown-debug-host-preparation-2026-10-02.md`. This does not perform or complete automatic restart verification.

## 6. Confirm no existing output changed

- [x] 6.1 Confirm `.#kernel`, `.#deviceTree`, and
      `.#nixosConfigurations.k230.config.system.build.toplevel` are
      unaffected: `git diff --stat 4ffe809a1b448f98379ea1165d7bca067d01cfdb`
      against this change's base revision shows exactly 11 files changed,
      917 insertions(+), 0 deletions(-) — six new files
      (`docs/research/mainline-kernel-inventory.md`,
      `nix/device-tree-mainline.nix`, `nix/dts/k230-tdisplay-mainline.dts`,
      `nix/kernel-mainline-src.nix`, `nix/kernel-mainline.nix`, plus
      additive-only lines in `flake.nix`) and five new OpenSpec change
      files. `git diff --stat ... -- nix/kernel.nix nix/kernel-src.nix
      nix/device-tree.nix nix/k230.nix nix/hardware.nix nix/sd-image.nix`
      returns empty. Confirmed by direct inspection, not by rebuilding
      those unaffected derivations (their own existing evidence already
      covers them; a change that touches none of their inputs cannot
      invalidate it).

## 7. Publish

- [x] 7.1 Validate with `openspec validate the-board-runs-a-mainline-kernel
      --strict`, checking the exit code directly (never via a pipe), per
      AGENTS.md.
- [x] 7.2 Commit the proposal, design, tasks, spec delta, research
      document, and the new `nix/`/`flake.nix` files together on
      `feat/mainline-kernel`, and report the branch/base/commit hash to the
      coordinator for an early merge to `master`, per AGENTS.md's "keep
      changes moving".

## Remaining evidence gate (explicitly not performed by this change)

Reaching a serial console — and now, potentially, a full NixOS login prompt
over SD — on real hardware is a **hardware milestone**, not a host build,
per `.skills/k230-spec-change/SKILL.md`'s QEMU-vs-hardware distinction.
This change does not touch `/dev/ttyACM0`, does not request a board slot,
and does not claim either gate. The operator command a future change (or
the coordinator, directly) would run once a board slot is free:

```
flock /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=10
```

Two staged artifacts now exist, testing two different claims — do not
conflate them:

1. **`result-kernelMainlineBootFiles`** (task group 4): console-only,
   no drivers beyond UART0. `ext4load` its `Image-mainline` and
   `k230-tdisplay-mainline.dtb`, `bootm`/`booti`, expect OpenSBI + Linux
   boot output and then a panic for lack of a root filesystem (no rootfs
   staged; this is a legible-boot-output test, not a login test).
2. **`result-kernelMainlineConsoleBootFiles`** (task group 5): the
   milestone-1 candidate, with GPIO/SD-MMC/USB forward-ported and this
   system's bootargs+initrd baked in. `ext4load` its `Image-mainline`,
   `k230-tdisplay-mainline.dtb`, and `initrd.uimg`, `bootm`/`booti` all
   three. Its pass condition is a real login prompt over the SD card's
   existing `NIXOS_SD`-labeled root partition — genuinely unverified
   whether the by-label root resolves, whether `&mmc_sd1` actually probes
   with the clock/reset IDs `nix/dts/k230-tdisplay-mainline.dts` guessed,
   and whether this system's own toplevel closure/profile even exists on
   that partition (see `nix/kernel-mainline-boot-files.nix`'s own header:
   this derivation does not populate the card, only produces what a
   separate staging step would load). A failure here is expected to be
   informative (which stage failed) rather than a clean pass on the first
   try, and should be recorded as such rather than retried silently.

No rootfs is staged by test 1; a kernel panic for lack of one, with
legible OpenSBI + Linux boot output first, is that test's actual pass
condition (see `docs/research/mainline-kernel-inventory.md`'s phased plan,
milestone 2).

## 2026-10-01 physical attempt (5b.5 remains open)

Exact matching bundle rebuilt, staged as a registered GC-rooted closure, and manually booted with per-load count/CRC checks. Linux 7.3.0-rc5, DRM/fb0 and photographed boot text are observed; Goodix registers. Both temporary boots stop in initrd before root login, including a repeat with direct initrd console diagnostics; no deliberate touch events were obtained. See `docs/evidence/mainline-display/physical-2026-10-01/README.md` and `result.json`; task 5b.5 stays unchecked pending usable root, physical touch and committed normal restoration. No persistent normal boot selection was changed.

The first bounded `rdinit=/bin/sh` diagnosis reached the PID1 shell but
failed command resolution because PATH was absent; its partition-label value
is invalid as hardware evidence. The controller now supplies volatile PATH
and an absolute reboot command. One corrected-path trial then reached the
Linux 7.3.0-rc5 banner but did not return its complete fresh-token probe
marker. One standalone `K230_PROC` marker appeared; later proc/device/label
and reboot markers did not. No disk or IRQ conclusion follows. A subsequent
physical power-cycle was checked against the protected normal system and all
eight hashes. The controller, sanitized attempt record and proof limits are
recorded in
`docs/evidence/mainline-display/physical-2026-10-01/initrd-shell-diagnostic.md`.

The 2026-10-02 physical power-cycle after the corrected-path trial restored
the selected normal system with a fresh boot ID, exact system/profile/kernel/
init, three active shell services and eight unchanged protected hashes. See
`docs/evidence/mainline-display/physical-2026-10-01/corrected-probe-recovery-2026-10-02/README.md` for committed identity and reviewed visible Home proof. Mainline task 5b.5 stays open
for usable root login and deliberate touch evidence. These captures show the
normal vendor-kernel system, not a working mainline shell.

The host controller now waits for one of at most eight fresh-token built-in
receipt attempts, then requires `/bin/true`, volatile `/proc` directory setup,
and proc mount RC success before reading uptime or requesting reboot. Failed
prerequisites stop with a structured recovery-required result; the full device
survey requires explicit mode. This source/test follow-up has not been run on
hardware and does not change task 5b.5 evidence status. The preceding physical
minimal attempt remains documented as failed, with later independent normal recovery verified, in
`docs/evidence/mainline-display/physical-2026-10-01/minimal-probe-2026-10-02/README.md`.


## 2026-10-02 bounded root-label controller preparation

Task 5b.5 remains unchecked. The explicit candidate selector and gated
`--mode label` controller now pass 49 host tests, including actual sh/bash
execution of the generated device-mount payload against isolated fixtures.
Evidence: `docs/evidence/mainline-display/physical-2026-10-01/candidate-controller-host-2026-10-02.md`
and `docs/evidence/mainline-display/physical-2026-10-01/label-controller-host-2026-10-02.md`.
The label mode accepts one read-only root-partition label check only after
receipt, external-command, proc/uptime, devtmpfs and block-node gates. Unknown
completion stops input and leaves recovery unverified. The optional
`--ignore-unused-clocks` flag adds only a volatile argument for the published
source-audit comparison; it is not a permanent clock policy.
No new board trial or usable-root/touch proof is supplied by these host checks.
The operator must first review the matching restart bundle and prove its
automatic protected-normal return before relying on recovery for label trials.

The bounded `--mode root-mount` follow-up repeats the minimal/device/label gates
before one `ro,noload` root mount, strict mount-flag checks and executable
lookups for the selected system's init/prepare-root, without executing either.
Known mounts receive one bounded unmount; unknown completion stops all input
and leaves recovery unverified. Its 62 host tests include actual isolated sh/bash
mount-table and stub-utility execution. Evidence:
`docs/evidence/mainline-display/physical-2026-10-01/root-mount-controller-host-2026-10-02.md`.
This does not perform ordinary `/init` activation or close task 5b.5; matching
bundle review and physical automatic recovery remain prerequisites for the
operator's root-mount trial. The optional clock flag remains label-only.

## 2026-10-03 complete read-only root prerequisite

Task 5b.5 remains unchecked. The targeted five-clock candidate now passes the
whole corrected `--mode root-mount` protocol without a clock-ignore flag:
read-only/no-journal mount, exact flags, selected init/prepare-root executable
lookups, unmount and one automatic protected-normal return. Command and
physical result are committed in
`docs/evidence/mainline-sd1-clocks/physical-no-flag-2026-10-03/README.md`.
The earlier paused session needed the user's reset after fresh UART checks
received no response; that separate recovery is recorded explicitly.

The reviewed ordinary-init controller (`tools/mainline-drm-system-trial.py`)
has landed with host proof and protected begin/touch/finish phases; the
coordinator independently passed 122 combined tests. Its physical trial is
separate from the returned read-only prerequisite. Ordinary NixOS activation,
deliberate glass touch and protected recovery remain required before 5b.5
can close. Neither the initrd shell nor host tests establish those outcomes.

The first physical ordinary-init attempt subsequently reached initrd
systemd/udev and timed out after 180 seconds without login. No touch or
reboot retry was sent; recovery is pending operator reset and protected
postflight. See `docs/evidence/mainline-system-trial/physical-2026-10-03/README.md`.
This failure leaves task 5b.5 open.

The user subsequently reset the ordinary-trial board; fresh protected normal
postflight passed exact identities, three services and eight unchanged boot
hashes. That operator recovery is now recorded in the same physical packet.
The full mainline initrd stopping point remains unresolved; 5b.5 stays open.


## 2026-10-03 standalone udev metadata proof

The same candidate now passes one bounded `udevadm test-builtin blkid` on the
verified SD1 root partition, including unique ext4/NIXOS_SD properties,
private raw-output preservation and one automatic protected-normal return.
Exact operator command and physical result are in
`docs/evidence/mainline-blkid-trial/physical-2026-10-03/README.md`.
This narrows the unresolved ordinary-init/coldplug boundary; it does not prove
whole-device discovery or close 5b.5. The source-supported next observation is
`docs/research/mainline-initrd-debug-console-2026-10-03.md`; its controller and
physical initrd state/recovery proof are separate required work.


## 2026-10-03 debug-console readiness observation

The bounded debug controller reached the fresh mainline/systemd primary shell
prompt, but asynchronous boot messages followed it immediately. Its tail-only
readiness check timed out before sending any diagnostic command. The user reset;
protected normal recovery and qualified Home IPC passed. Exact command, result
and limits are in
`docs/evidence/mainline-system-trial/debug-readiness-physical-2026-10-03/README.md`.
The prompt-recognition correction needs host review and a separate physical
rerun; initrd unit/worker state is still UNVERIFIED and 5b.5 stays unchecked.


## 2026-10-03 corrected prompt / unacknowledged receipt

The corrected debug readiness check recognizes the fresh primary prompt, but
the first framed receipt has no command echo or reply within ten seconds. No
identity guard, snapshot or reboot followed. The user reset; protected normal
postflight and Home IPC passed. See
`docs/evidence/mainline-system-trial/debug-receipt-physical-2026-10-03/README.md`.
Debug-terminal setup and the exact UART receive boundary need source comparison
before another physical retry; no IRQ/clock/terminal cause is claimed. Ordinary
root, deliberate touch and 5b.5 remain open.


## 2026-10-03 autonomous observer READY boundary

The separately built observer bundle passed actual Image/DTB/ramdisk/archive
and closure inspection, staging and protected normal preflight. Its physical
trial produced one complete fresh READY frame, then no counter frame, primary
prompt or return. The host sent zero receipt commands; the bounded passive
wait ended without automatic recovery. The user reset; protected normal postflight
and qualified Home IPC passed. Automatic return remains UNVERIFIED. Exact
artifacts, command, timestamps,
raw-log digest and limits are in
`docs/evidence/mainline-system-trial/uart-observer-physical-2026-10-03/README.md`.
No helper, UART, console or kernel cause is inferred. Ordinary usable root,
panel photograph, deliberate glass touch and task 5b.5 remain open.


## 2026-10-03 serial-only pre-init comparison

The reviewed controller removed only volatile `console=tty0` while retaining
the same built/staged Image, hardware DT, initrd and helper. Protected normal
preflight, loads/CRCs and exact printed arguments passed. Linux reached display
and Goodix registration, then clock/power-domain/ALSA milestones; no init or
systemd banner, observer frame or automatic return was observed. Zero receipt
commands were sent. The user reset; protected normal postflight and qualified
Home IPC passed. Automatic return remains UNVERIFIED. Exact
command/artifacts/timestamps/limits are in
`docs/evidence/mainline-system-trial/uart-observer-serial-console-physical-2026-10-03/README.md`.
No clock, power-domain, UART or console cause is claimed; further source
discrimination is required. Usable root, panel/touch and task 5b.5 stay open.

## 2026-10-03 retained SBI boot-console host preparation

The user authorized the same-image comparison before a diagnostic kernel
rebuild. The observer controller now accepts explicit `--sbi-boot-console`
only with `--serial-console-only`, adding exactly volatile
`earlycon=sbi keep_bootcon` while retaining all artifact, identity, printed
argument and recovery gates. Strict observer parsing is unchanged; duplicate
readiness still sends zero receipts. The 38 focused tests and actual selected
artifact preparation pass. Commands and limits are in
`docs/evidence/mainline-uart-observer-trial/sbi-boot-console-host-2026-10-03.md`.
Host proof does not diagnose the boot stall or prove automatic return; the
separate physical comparison and task 5b.5 remain open.

## 2026-10-03 retained SBI boot-console physical boundary

The same-image serial-only comparison with volatile `earlycon=sbi keep_bootcon`
passed protected normal preflight, loads/CRCs and printed arguments. Fresh
mainline output confirmed SBI DBCN detection and actual SBI boot-console
enablement; subsequent messages were duplicated. Output ended at the ALSA
milestone (3.838138), with no visible init launch, systemd, observer frame or
automatic return. Zero receipts were sent; the bounded passive trial exited 2.
The user reset; protected normal postflight, qualified Home IPC and a private
camera observation of Home passed. Automatic mainline return remains
UNVERIFIED. Exact command, artifact hashes, sanitized
observations and limits are in
`docs/evidence/mainline-system-trial/uart-observer-sbi-boot-console-physical-2026-10-03/README.md`.
The trial does not identify a cause; optional kernel boundary markers are the
next source-supported diagnostic. Task 5b.5 stays unchecked.


## 2026-10-03 optional kernel boot-boundary host preparation

Within open task 5b.5, the user authorized finite paired kernel markers after
same-image console comparisons failed to reach usable init. Separate
`kernelMainlineBootTrace`, `k230-mainline-boot-trace` and
`kernelMainlineBootTraceTrialBootFiles` outputs add serial-only ordinary init
and exact `k230.boot_trace=1`; existing outputs/controllers are unchanged.
Seven native flag/emergency/cap tests, zero-fuzz source application, a real
RISC-V `main.o` API/lifetime check, narrow Nix evaluation and nine unchanged
existing derivation identities passed. Commands, pins and limitations are in
`docs/evidence/mainline-system-trial/boot-boundary-host-2026-10-03.md`.
Full kernel build/artifact inspection and physical marker/init/root/recovery/
touch proof remain UNVERIFIED. An enter-only marker is only the last visible
boundary; the marker itself can block. Task 5b.5 stays unchecked.

## 2026-10-03 matching boot-boundary bundle host proof

The opt-in `kernelMainlineBootTraceTrialBootFiles` full build passed at source
`7e1e3a60d7ebf607a8312324ae890b97f089b3d1`, producing `cr8bv4s6…` with kernel
`908wxcz…` and system `dxwjvz…`. Exact Image/initrd/DT/CRC/closure inspection
and actual ordinary controller preparation passed. The actual built config
has KUnit disabled; the five-clock hardware DT is unchanged except bootargs.
See `docs/evidence/mainline-system-trial/boot-boundary-build-2026-10-03/README.md`
and its result JSON for commands, paths, hashes and remaining physical gates.
No board was used for this increment; marker output/root/touch/return remain
UNVERIFIED and task 5b.5 remains unchecked.

## 2026-10-03 physical boot-boundary attempt

The exact optional trace bundle passed staging and protected normal preflight,
then emitted basic-setup-enter, initcalls-enter and initcalls-exit on the board.
It produced no next marker or ordinary login within 180 seconds; controller exit 1
closed UART without further candidate input. There is no original blocking work
between the visible post-initcall marker and the missing basic-setup-exit marker,
but the visible marker's own return/flush/scheduling is not proved. See
`docs/evidence/mainline-system-trial/boot-boundary-physical-2026-10-03/README.md`
and result JSON. The user pressed reset and protected normal recovery is verified: fresh boot,
exact normal identities, three active services, eight unchanged files and
registration absent. Automatic return remains UNVERIFIED; ordinary root/panel/
glass touch and task5b.5 stay open.

## 2026-10-03 separate direct-SBI boundary source proof

The reviewed optional `kernelMainlineBootTraceSbiTrialBootFiles` source adds
four single-attempt public DBCN records around the two printk marker calls
identified by the physical attempt. It preserves all twelve existing output
identities, including the original trace kernel/system/bundle; there is no new
console registration or retry/fallback loop. Ten focused native tests, actual
RISC-V object/API/lifetime/alignment proof and Nix/strictspec checks passed.
See `docs/evidence/mainline-system-trial/boot-boundary-sbi-host-2026-10-03.md`
for exact commands, source paths and interpretation limits. Full matching build
and physical direct-SBI output/root/login/touch/return remain UNVERIFIED; the
user-reset recovery of the previous diagnostic is verified. Task5b.5 stays open.

## 2026-10-03 direct-SBI matching full build proof

`kernelMainlineBootTraceSbiTrialBootFiles` built successfully at source `007410ee`,
producing `j0ad6h3s…` with kernel `f7h2n15…` / system `zcsfgwk…`. Matching Image/
initrd/DT/CRC/closure inspection and actual ordinary-controller preparation
passed. Four public SBI record strings are linked; actual RISCV_SBI/64BIT/
VMAP_STACK/4KiB/KUnit disabled config and hardware DT equality are recorded in
`docs/evidence/mainline-system-trial/boot-boundary-sbi-build-2026-10-03/README.md`.
No board was used for this increment. Physical direct-SBI output/root/touch/
return stay UNVERIFIED and task 5b.5 stays unchecked.

## 2026-10-03 physical direct-SBI boundary attempt

The exact direct-SBI bundle passed staging and protected normal preflight,
then emitted all four direct records plus legacy seq1–4. Both suspect marker
helpers and `do_basic_setup()` returned; the final `basic-after` ECALL return
and entry to the next marker/initramfs wait remain unknown. No login arrived
within 180 seconds; controller exit1 closed UART without further input. See
`docs/evidence/mainline-system-trial/boot-boundary-sbi-physical-2026-10-03/README.md`
and result JSON. The subsequent user-confirmed reset received zero UART bytes
in90seconds and no fresh normal prompt; no Linux command was sent. The camera
shows a dark panel with observation limits. `operator-reset-check.json` records
this failed check; power-cycle confirmation is pending. Protected recovery,
ordinary root/panel/glass/production and task5b.5 remain open.


## 2026-10-03 separate SBI-only diagnostic source proof

The reviewed optional `kernelMainlineBootTraceSbiOnlyTrialBootFiles` layers
over the original trace source and selects single-attempt fixed public SBI
records at all twenty existing diagnostic sites. Enabled mode skips only
the diagnostic helper's printk/emergency operations; regular kernel logging
is unchanged. Eleven focused /28 combined native tests, actual RISC-V object/
lifetime/table layout, exact source order, narrow Nix evaluation and all
fifteen previous derivation identities passed. See
`docs/evidence/mainline-system-trial/boot-boundary-sbi-only-host-2026-10-03.md`.
The source has landed; full matching bundle build and physical output/root/
touch/return remain UNVERIFIED. The preceding reset check failed with zero
UART bytes; protected normal recovery must pass before another board trial.
Task5b.5 stays open; visible SBI bytes do not prove the last ECALL returned.


## 2026-10-03 subsequent normal recovery / SBI-only full build

The user's second confirmed reset passed fresh protected normal postflight,
unchanged identities/eight files, three active services and registration
absence. Home IPC returned RC0 and reviewed private camera shows normal Home;
see `docs/evidence/mainline-system-trial/boot-boundary-sbi-physical-2026-10-03/operator-reset-recovery.json`.
This is operator recovery; automatic return from the failed trial stays
UNVERIFIED. The matching SBI-only bundle `brmp1qf9…` built successfully,
with actual config/source/all20 linked strings, hardwareDT, Image/initrd/CRC/
closure and ordinary-controller host preparation checks passed. See
`docs/evidence/mainline-system-trial/boot-boundary-sbi-only-build-2026-10-03/README.md`.
SBI-only physical output/login/root/glass/automatic return remain UNVERIFIED;
5b.5 stays open before the separately reserved board attempt.


## 2026-10-03 SBI-only physical boundary

The matching SBI-only bundle passed staging and protected normal preflight,
then emitted five complete fixed labels through `initramfs-wait-enter`, with
zero legacy markers. No exit/login followed within 180 seconds; controller exit 1
released UART with no further input. The preceding basic-setup SBI call
returned; the last ECALL return and actual wait entry remain unknown. The
external `Unpacking initramfs...` printk was visible, with no completion proof.
See `docs/evidence/mainline-system-trial/boot-boundary-sbi-only-physical-2026-10-03/README.md`
and result JSON. Operator reset recovery is pending; automatic return,
ordinary root/panel/glass and 5b.5 remain open. Read-only audit is evaluating
a same-Image `initramfs_async=0` comparison before another kernel rebuild.


## 2026-10-03 same-image initramfs/initcall controller opt-in

Independent source audit supports one volatile `initramfs_async=0` token
as the next bounded discriminator: the same worker is scheduled, then the
rootfs initcall joins it before later initcalls. The controller's reviewed
begin-only `--wait-initramfs-in-initcall` preserves exact artifact/identity/
CRC/argument/state/recovery gates and the 180-second passive deadline.
Corrected focused 29 tests, actual matching-bundle prepare/unchanged drv,
strict/all validation and whitespace checks passed. Evidence and exact
operator command: `docs/evidence/mainline-system-trial/initramfs-initcall-controller-host-2026-10-03.md`.
This is host proof only. Current candidate reset recovery and the new
physical comparison remain UNVERIFIED; ordinary root/glass/return and 5b.5
stay open. No kernel rebuild, board command or production fix is claimed.


## 2026-10-03 SBI-only operator recovery verified

The user hit reset and fresh protected normal postflight passed exact
identities, three services, all eight unchanged files and registration
absence. Home IPC returned RC0; reviewed private camera shows normal Home.
See `docs/evidence/mainline-system-trial/boot-boundary-sbi-only-physical-2026-10-03/operator-reset-recovery.json`.
Automatic return from the failed candidate remains UNVERIFIED. Reviewed
controller `1846fd3e` and its29 focused tests passed CI; the same-image
initramfs comparison is ready for a separately reserved physical attempt.
Ordinary root/glass/production and5b.5 remain open.


## 2026-10-03 physical initramfs/initcall comparison

The exact same staged bundle with one volatile `initramfs_async=0` argument
passed protected preflight/loads/CRCs/printed arguments and emitted18 fixed
records through `init-exec-exit`, including the earlier rootfs join and later
initramfs wait completion. No login arrived in180seconds; controller exit1
released UART without further input. `kernel_execve()` returned but retval,
last SBI return and first userspace instruction are unknown. See
`docs/evidence/mainline-system-trial/initramfs-initcall-physical-2026-10-03/README.md`
and result JSON. Operator reset recovery is pending; ordinary root/panel/
glass/automatic return and5b.5 stay open. Read-only source audit recommends
a same-image no-marker comparison preserving async=0 and normal logging;
reviewed controller support is required before another boot.


## 2026-10-03 initramfs comparison operator recovery verified

The user reset after the failed18-record comparison. Fresh protected normal
postflight, exact identities/eight files/three services/registration absence
passed; Home IPC returned RC0 and a newly reviewed private camera shows Home.
See `docs/evidence/mainline-system-trial/initramfs-initcall-physical-2026-10-03/operator-reset-recovery.json`.
This proves operator recovery only; automatic return, mainline root/panel/glass
and task5b.5 remain UNVERIFIED. Board/UART and camera are released.


## 2026-10-03 reviewed same-image marker-free controller

The begin-only `--without-boot-markers` opt-in requires the earlier initramfs
join selector and removes both original qualified trace-enable tokens only.
Same Image/closure/DT/logging/controls and exact identity/CRC/arguments/typed
resume/recovery/180-second unknown gates remain. Literal transport is safe
and below 512 bytes before first input. 36 focused tests passed independently;
actual realized-bundle prepare differs only by the two removed tokens and
uses 317 bytes. Narrow proof and operator command:
`docs/evidence/mainline-system-trial/marker-free-controller-host-2026-10-03.md`.
Host proof only; physical root/panel/glass/return and 5b.5 remain UNVERIFIED.


## 2026-10-03 marker-free physical comparison

Same staged Image/initrd/DT/closure with initramfs_async=0 retained and both
marker flags removed passed preflight, five loads/CRCs and exact printed plus
kernel-received arguments. No diagnostic records, as expected; unpacking,
initrd-free and unused-kernel-image-free messages appeared, but no systemd/login
within 180 seconds. Exit 1 released UART without further input. New private
camera appears dark with documented limits. See
`docs/evidence/mainline-system-trial/marker-free-physical-2026-10-03/README.md`
and fixed result JSON. Another operator reset/protected normal postflight is
pending. Source audit suggests a separately reviewed same-initrd Bash-PID1
comparison, not ordinary-root acceptance. 5b.5 remains unchecked; mainline
root/panel/glass/automatic return and production remain UNVERIFIED.


## 2026-10-03 marker-free comparison operator recovery verified

The user pressed reset after the failed marker-free trial. Fresh protected
normal postflight passed exact identities, all eight files, three services
and registration absence; Home IPC returned RC0 and a new reviewed private
camera shows normal Home. See
`docs/evidence/mainline-system-trial/marker-free-physical-2026-10-03/operator-reset-recovery.json`.
This is operator recovery only. Automatic return, mainline ordinary root,
panel/glass and task 5b.5 remain UNVERIFIED. Board/UART/camera are released;
the next guarded same-image Bash-PID1 controller increment is host work.


## 2026-10-03 reviewed same-image Bash PID1 controller

The explicit minimal-only `--same-image-shell-pid1` selector uses the same
qualified marker-free/async=0 bundle and three controls, adding only
`rdinit=/bin/sh`. Original artifacts, archived Bash/systemd/common loader,
safe literal transport before UART and exact printed arguments are checked.
Fresh Linux/init-entry/prompt/receipt precede proc/uptime and strict PID1/root/
Bash/kernel/cmdline/new-boot/initrd guards, renewed before one acknowledged
reboot. Both protected normal phases assert registration absence. Unknown
stops input; ordinary init is NOT_ATTEMPTED. Independent review approved;
14 focused and all 214 existing trial tests passed, strict/all56 validation
and exact realized-bundle single-variable preparation passed. Narrow commands
and operator gate:
`docs/evidence/mainline-system-trial/shell-pid1-controller-host-2026-10-03.md`.
CI covers ordinary/minimal/new focused tests. Physical shell receipt/automatic
return are still UNVERIFIED; ordinary root/panel/glass and task 5b.5 stay open.


## 2026-10-03 same-image Bash physical prompt, reception unknown

Reviewed source/CI bfce9f8b passed a reserved single trial's protected preflight,
five loads/CRCs and exact printed plus kernel-received arguments. Fresh Linux,
Run /bin/sh and primary sh-5.3 prompt prove Bash userspace startup. Eight bounded
builtin receipt attempts produced no replies/echoes; exit 2 at reception
released UART with no further input. True/proc/uptime/full identity/reboot were
NOT_ATTEMPTED. See
`docs/evidence/mainline-system-trial/shell-pid1-physical-2026-10-03/README.md`
and fixed result JSON. New private camera appears dark with explicit limits;
serial startup proof is separate. A subsequent new user reset and checker
exit 0 proved a fresh protected normal boot, exact system/profile/kernel/init,
eight unchanged files, three active services and registration absence. Home
IPC completed with exit 0 and a new privately reviewed camera frame shows
normal Home; see the packet's `operator-reset-recovery.json`. Board/UART and
camera are released. This proves operator recovery, not automatic return.
Read-only audits recommend a finite independent cached UART/IRQ/time reporter,
not a blind shell retry or TTY poll. Ordinary root/panel/glass/automatic return
and task 5b.5 remain UNVERIFIED; no archive or production fix is claimed.

## 5f. Finite independent UART/IRQ progress diagnosis (planned, no physical claim)

- [x] 5f.1 Add separately selected runtime-gated kernel source/configuration:
      normal-priority finite worker, lifecycle-safe cached 8250 snapshot,
      actual mapped timer/UART IRQ accounting and aligned bounded public SBI
      records outside all locks. No MMIO/TTY/settings/critical-path output.
      Source/protocol proof: `python3 tests/test_mainline_uart_progress.py`.
      Twelve actual-code native fixtures pass; the optional effective Kconfig
      resolves built-in reporter/dependencies and 22 existing output identities
      are unchanged. [Source/config/object evidence](../../../docs/evidence/mainline-uart-progress/source-object-host-2026-10-03.md).
      At this initial source proof, the full matching build and physical observations were UNVERIFIED; later host build proof is recorded in 5f.2–3.
- [x] 5f.2 Compile the changed 8250/timer/reporter objects against the exact
      configured RISC-V headers and verify record layout/lifetime/Kconfig.
      Host-only proof: `nix build .#kernelMainlineUartProgressExactObjects --no-link --print-out-paths`.
      Three changed RISC-V objects compile against immutable installed base
      headers plus an explicit reporter overlay; preliminary layout/API proof passed.
      ExactObjects subsequently passed against the actual selected kernel.dev
      config/autoconf without an overlay; all three ELF/lifetime/layout checks
      passed. [Exact/full host proof](../../../docs/evidence/mainline-uart-progress/exact-full-host-2026-10-03.md).
- [x] 5f.3 Build the complete optional matching system/initrd/DT/bundle and
      inspect hashes/CRCs/closure/config and unchanged existing derivations.
      Host-only proof: `nix build .#kernelMainlineUartProgressTrialBootFiles --no-link --print-out-paths`
      followed by `python3 tools/mainline-drm-trial-inspect.py BUNDLE`.
      Root's frozen 35e93757 matching build passed; gmsmqk bundle inspection,
      Image/system/initrd/DT/CRCs/closure/config checks and hardware-DT comparison
      passed. Existing identity receipts remain separate from physical proof;
      no UART/receipt/root/touch/recovery result is claimed.
- [x] 5f.4 Add a reviewed explicit minimal-shell/controller opt-in, exact
      original artifact and runtime argument qualification, at most one fresh
      receipt stimulus, bounded passive record capture, fixed public parser,
      missing/duplicate/unknown-no-input policy and protected recovery gates.
      Require the same selected kernel derivation's already-realized dev
      config before UART; exactly match its fresh received kernel arguments.
      Never issue a candidate reboot; preserve actual elapsed capture and
      host-arrival-only sample coverage, then require protected normal recovery.
      Host-only proof: `python3 tests/test_mainline_uart_progress_controller.py` and
      `python3 -m unittest discover -s tests -p 'test_mainline_drm*trial.py'`.
      Controller source/fixture preparation is recorded in
      `docs/evidence/mainline-uart-progress-controller/README.md`; this task
      actual matching bundle/config qualification subsequently passed.
      [Matching controller host proof](../../../docs/evidence/mainline-uart-progress/controller-matching-host-2026-10-03.md).
- [x] 5f.5 After fresh protected normal recovery, reserve board/UART and run one
      matching physical comparison with its exact prepared identities:
      `python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal --same-image-shell-pid1 --uart-progress --bundle BUNDLE --manifest PRIVATE_MANIFEST --normal-report PRIVATE_NORMAL --log PRIVATE_LOG --result PRIVATE_RESULT`.
      Commit fixed records/stimulus/interpretation and protected normal
      postflight or explicit pending operator recovery. This proves only the
      observations obtained, not full root/panel/glass acceptance.
      [Physical finite observation](../../../docs/evidence/mainline-uart-progress/physical-2026-10-03/README.md): exact received arguments and Bash prompt, one stimulus,
      zero receipts and zero records; subsequent protected operator reset/postflight verified
      (fresh boot, exact identities, eight files, three services, registration absence).
      This is observation-only, not successful diagnostic/root/touch acceptance.
- [x] 5f.6 Reconcile the diagnostic findings with the next narrow discriminator,
      preserve unknown markers and task 5b.5, land/push evidence and verify
      exact CI/published revision. Planning proof: `openspec validate the-board-runs-a-mainline-kernel --strict`.
      Zero-report limits and manual protected recovery are committed in the
      [physical packet](../../../docs/evidence/mainline-uart-progress/physical-2026-10-03/README.md).
      Recovery revision 5cdff03b passed CI 37166330080 and published work/evidence
      checks; the reviewed continuation is preserved as planned group 5g below.
      No ordinary-root/touch/automatic-recovery result is inferred.


## 5g. Worker-entry/first-post-sleep comparison (planned, no physical claim)

- [x] 5g.1 Add a separately layered runtime-gated breadcrumb reporter source:
      exactly two fixed <=64-byte aligned ordinary-rodata records in the
      normal-priority worker, entry before first sleep and post-sleep before
      first snapshot, at most one SBI attempt each and no IRQ/TTY/PID1 output.
      Preserve six original samples, delays/getters/stop checks and all existing
      package/source/config/trial identities. Actual-code fixtures cover exact/
      absent/bare/invalid gates, extension absence, placement/stop behavior,
      full/partial/zero/error no-retry and total eight-attempt cap.
      Source/fixture proof: `python3 tests/test_mainline_uart_progress_breadcrumbs.py`.
      Source-host increment: thirteen actual patched-worker native fixtures and
      twelve original source/API fixtures passed; evaluation preserves all 91
      existing package identities and ten kernel source/config pairs. Exact
      original-source layering and inherited config/params are recorded in
      [source-host evidence](../../../docs/evidence/mainline-uart-progress-breadcrumbs/source-host/README.md).
      This is not a full matching build, actual configured object or physical proof.
- [x] 5g.2 Add/build the separately selected matching kernel/system/initrd/DT/
      bundle, preserving original artifact parameters and every existing
      package plus kernel source/config and trial derivation identity. Commit
      source-layering/identity evaluation and full installed config/closure/
      hash/CRC/hardware-DT inspection, distinct from physical output.
      Host proof: `nix build .#kernelMainlineUartProgressBreadcrumbsTrialBootFiles --no-link --print-out-paths`
      then `python3 tools/mainline-drm-trial-inspect.py BUNDLE`.
- [x] 5g.3 Compile the changed reporter against that exact selected kernel.dev
      config/generated headers without a forced overlay; inspect regular
      helper/flag/strings lifetime, <=64-byte lengths, alignment64/page bounds
      and unchanged cached-getter dependencies. Host-only proof:
      `nix build .#kernelMainlineUartProgressBreadcrumbsExactObjects --no-link --print-out-paths`.
      Actual host proof: coordinator frozen 2a548135 resumed build returned 0;
      verifier source 071086bc exact-object command returned 0 under shared lock.
      Selected dev config/autoconf, three RISC-V objects/regular aligned storage,
      source 7207, full bundle hashes/CRCs/closure and complete hardware DT equality
      passed. [Exact/full host evidence](../../../docs/evidence/mainline-uart-progress-breadcrumbs/exact-full-host/README.md).
      The initial coordinator session 143/broken-pipe interruption is distinct
      from the successful completion receipt. No hardware/RX/return result is
      inferred; tasks 5g.5–6 and task 5b.5 remain open.
- [x] 5g.4 Add a separate explicit minimal-only typed breadcrumb selector and
      strict fixed-record parser; preserve default/common/numeric protocols,
      exact artifact/dev/received-args preflight, sole volatile gates and fresh
      readiness for at most one receipt stimulus. Test early/late records,
      stale/echo/unknown/truncated/duplicate/reordered/interleaved bytes, split
      transport chunks, missing receipt/no retry/no reboot, bounded private
      capture and independent protected normal recovery. Host-only proof:
      `python3 tests/test_mainline_uart_progress_breadcrumbs_controller.py`
      and `python3 -m unittest discover -s tests -p 'test_mainline_drm*trial.py'`.
      Controller host preparation is recorded in
      `docs/evidence/mainline-uart-progress-breadcrumbs/controller/README.md`.
      Pre-UART qualification additionally ties the same kernel drv to its
      immutable reviewed worker source and unique compiled Image marker/gate
      bytes, rejecting the old reporter even with CONFIG=y. Actual matching
      bundle/dev/source preparation passed on 2026-10-04UTC against mhq10143…,
      as recorded in
      `docs/evidence/mainline-uart-progress-breadcrumbs/positive-controller-host/README.md`
      and `result.json`; the named fixture commands also passed, preserving a
      separate quota failure and bounded ~/tmp rerun. This is host-only proof;
      group5g.5 and task5b.5 remain open, without candidate reboot or hardware claim.
      [Integrated source/controller checks](../../../docs/evidence/mainline-uart-progress-breadcrumbs/integration-host-2026-10-03.md) include strict CRLF/embedded-CR framing and CI coverage.
- [x] 5g.5 After fresh protected normal recovery and exact host/controller proof,
      reserve board/UART for one comparison, capture fixed breadcrumb/sample/
      receipt facts and limits, then verify protected normal return or record
      distinct pending operator recovery. Hardware proof operator command:
      `python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal --same-image-shell-pid1 --uart-progress --uart-progress-breadcrumbs --bundle BUNDLE --manifest PRIVATE_MANIFEST --normal-report PRIVATE_NORMAL --log PRIVATE_LOG --result PRIVATE_RESULT`.
      No further input or candidate reboot after the single stimulus; this is
      observation only, not ordinary-root/touch or automatic-return acceptance.
      Actual comparison: matching mhq10143 bundle staged with return 0; fresh
      protected preflight/load checks passed. Both fixed breadcrumbs, one
      matching Bash receipt and samples 0/1 arrived; samples 2–5 and normal return
      did not arrive in 180.084 seconds. No further input or candidate reboot.
      [Physical evidence](../../../docs/evidence/mainline-uart-progress-breadcrumbs/physical-2026-10-03/README.md)
      records fixed facts/deltas, firmware-return limits and distinct operator-reset
      recovery verified after the capture. This is observation proof only; task 5b.5 stays open.
- [x] 5g.6 Reconcile presence/absence and firmware-return limits, retain unknown
      states and task5b.5, commit public-safe evidence and land/push with exact
      CI/published revision. Planning proof: `openspec validate --all`.

The group 5g observation and interpretation landed as 278769d0. CI run
37171186624 passed build/deploy; both published work and physical evidence pages
returned HTTP 200 with exact revision 278769d0. The committed deployment receipt
is `docs/evidence/mainline-uart-progress-breadcrumbs/physical-2026-10-03/deployment.json`.
Independent review matched the fixed public facts/deltas to the private capture.
Both markers and receipt are proven; later sample/firmware-return/normal-return
remain unknown. The separately proposed next discriminator targets the sample 1
write return versus third sleep. The subsequent user reset passed fresh protected
normal postflight and Home IPC, with separately reviewed camera Home;
`docs/evidence/mainline-uart-progress-breadcrumbs/physical-2026-10-03/operator-reset-recovery.json`
records exact limits. Automatic return and task 5b.5 stay open.


## 5h. After-n1-write/third-post-sleep comparison (captured; new points UNVERIFIED)

- [x] 5h.1 Add a separately layered PostSample reporter source with exact new
      runtime gate, requiring both existing gates/config/DBCN. Two fixed <=64
      aligned ordinary-rodata records occur only after sample1's numeric SBI
      return and after sample2's sleep/stop check before snapshot. Preserve six
      samples/two prior breadcrumbs/sleeps/getters/stop behavior and all old
      package/source/config/trial identities; no IRQ/TTY/PID1/priority changes.
      Actual-code fixtures cover exact/absent/bare/invalid/config/availability
      gates, placement/stop behavior, full/partial/zero/error one-attempt and
      ten-call cap. Source-host proof:
      `python3 tests/test_mainline_uart_progress_post_sample.py` plus unchanged-output/source/config identity evaluation.
      Native 15 new fixtures and 13/12 prior fixtures passed; all 95 prior
      package identities and 11 exposed kernel source/config pairs were equal.
      Source-only/native/pure-evaluation receipt: [source host proof](../../../docs/evidence/mainline-uart-progress-post-sample/source-host/README.md).
      No matching full build, target object or physical claim follows.
- [x] 5h.2 Build separately selected matching kernel/system/initrd/DT/bundle;
      inspect full installed config, source layering, Image/CRC/closure/hash/
      original artifact parameters and complete hardware DT comparison, distinct
      from physical output. Host proof:
      `nix build .#kernelMainlineUartProgressPostSampleTrialBootFiles --no-link --print-out-paths`
      then `python3 tools/mainline-drm-trial-inspect.py BUNDLE`.
      Matching full build from frozen `75cc49df` returned 0; actual inspector,
      installed config, source layering, linked Image and complete hardware DT
      comparison passed. [Exact/full host proof](../../../docs/evidence/mainline-uart-progress-post-sample/exact-full-host/README.md); no physical claim.
- [x] 5h.3 Compile actual changed worker/getter/timer against the exact selected
      kernel.dev config/generated headers without overlay; inspect ordinary
      helper/flag/strings lifetime, lengths/alignment64/page bounds and unchanged
      getter dependencies. Host-only proof:
      `nix build .#kernelMainlineUartProgressPostSampleExactObjects --no-link --print-out-paths`.
      Narrow offline exact-object build from source checkpoint `e3edc5e6`
      returned 0 against actual selected dev, without overlay; three RISC-V
      objects, four aligned ordinary-rodata records, original 256-byte buffer
      and unchanged getter dependencies passed inspection. Same host proof;
      controller/physical/receipt/recovery gates remain separate and open.
- [x] 5h.4 Add explicit minimal-only `--uart-progress-post-sample` requiring all
      previous comparison selectors. Preserve exact pre-UART artifact/source/
      linked Image/dev checks, sole new volatile gate, received args/freshness,
      protected normal checks, one stimulus and no later input/reboot. Strict
      record tests cover split transport, complete/partial, stale/echo/extra/
      duplicate/reorder/interleave and missing-point/numeric/receipt facts.
      Host-only proof: `python3 tests/test_mainline_uart_progress_post_sample_controller.py`
      plus existing minimal/progress/breadcrumb controller regression commands.
      Keep this task unchecked until actual NEW matching bundle/dev/source/Image
      positive preparation passes. Fixtures and old-artifact rejection alone
      do not satisfy that gate or establish a performed protected board check.
      Preparation evidence: [PostSample controller host note](../../../docs/evidence/mainline-uart-progress-post-sample/controller/README.md)
      records 20 focused tests plus unchanged 18 breadcrumb/20 progress/100
      minimal/14 shell/36 ordinary tests, the strict source/Image/config gate,
      and actual old matching artifact rejection before UART access. Actual NEW
      positive preparation now passed against frozen `75cc49df` and realized fjmxf6
      bundle/js4by9 dev: [positive host proof](../../../docs/evidence/mainline-uart-progress-post-sample/positive-controller-host/README.md).
      Same-drv config, reviewed aee68 source, linked unique Image strings, actual
      archived executables/common loader and exact sole additional gate passed;
      literal transport 419 bytes versus 386. No UART/build or performed protected
      board check by this qualifier. One fresh stimulus is followed only by
      passive bounded capture; no candidate reboot, extra input or physical claim
      is authorized by marker presence. Tasks 5h.5–6 and 5b.5 remain open.
- [x] 5h.5 After independently verified protected recovery and exact host/
      controller proof, reserve board/UART for one comparison; commit fixed
      point/sample/receipt facts and independent protected recovery or explicit
      pending operator reset. Hardware operator command:
      `python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal --same-image-shell-pid1 --uart-progress --uart-progress-breadcrumbs --uart-progress-post-sample --bundle BUNDLE --manifest PRIVATE_MANIFEST --normal-report PRIVATE_NORMAL --log PRIVATE_LOG --result PRIVATE_RESULT`.
      Missing output remains unknown; no further input or candidate reboot.
      This is diagnostic observation, not ordinary-root/touch/automatic return.
      Actual fjmxf6 comparison completed: [physical capture](../../../docs/evidence/mainline-uart-progress-post-sample/physical-2026-10-03/README.md).
      Fresh args/Bash/worker-entry, one stimulus, no receipt/samples/new points
      during 180.0975s; no protocol errors or candidate reboot. New operator
      reset subsequently passed fresh guarded normal postflight and reviewed
      Home: [reset receipt](../../../docs/evidence/mainline-uart-progress-post-sample/physical-2026-10-03/operator-reset-recovery.json).
- [x] 5h.6 Reconcile point reach/return/output and sleep/scheduling limits,
      preserve task 5b.5 and unknown states, land/push public-safe evidence and
      verify exact CI/published revision. Planning proof:
      `openspec validate the-board-runs-a-mainline-kernel --strict`.


Group5h source, exact/full artifacts, actual positive preparation and physical
capture are complete. Independent review matched private facts/hash. Evidence
08ea7370 passed CI37175128998; work and physical pages returned HTTP200 with
that exact revision: committed physical deployment.json. Only worker-entry
arrived; neither entry ECALL return nor first sleep/output is established.
The subsequent NEW reset passed guarded fresh normal postflight/Home evidence;
automatic return and5b.5 stay open. Group5i
is a separate output-removal intervention, not a claimed cause or silent scope
completion of ordinary mainline acceptance.

## 5i. Memory progress with one final observer output (planned, UNVERIFIED)

- [x] 5i.1 Implement separately selected layered source/recipes/exact gate;
      retain all previous identities, six sleeps/cached snapshots/stop checks.
      Suppress every worker output only in Memory mode, publish consistent finite
      stages/bitmap/index and create independent normal-priority observer with
      one45s kernel wait/one final <=256-byte aligned DBCN attempt. Freeze grammar;
      fixtures cover gates, ordering, stop/timeout/creation failure and one-call
      counts. Narrow proof: `python3 tests/test_mainline_uart_progress_memory.py`.
      Actual-code 13 fixtures and prior 15/13/12 fixtures passed; all 99 prior
      package drv identities and 12 exposed kernel source/config pairs equal.
      [Source/native/pure-evaluation proof](../../../docs/evidence/mainline-uart-progress-memory/source-host/README.md); no matching full artifact, target-object,
      controller or physical claim follows. Other 5i gates stay open.
- [x] 5i.2 Build matching Memory kernel/system/bundle/dev, inspect source/config,
      CRC/closure/archive/original args/complete hardware DT. Host proof:
      `nix build .#kernelMainlineUartProgressMemoryTrialBootFiles .#kernelMainlineUartProgressMemory.dev --no-link --print-out-paths`
      then `python3 tools/mainline-drm-trial-inspect.py BUNDLE`.
      Matching frozen `7af8f7b8` full build returned0; actual selected source,
      config/Image/initrd/CRCs/closure/original args/full hardware DT passed.
      [Exact/full host proof](../../../docs/evidence/mainline-uart-progress-memory/exact-full-host/README.md); no physical claim.
- [x] 5i.3 Compile exact selected-header worker/getter/timer/observer objects;
      inspect consistent publication dependencies, ordinary lifetime/aligned
      buffer/page bounds and unchanged getter behavior. Host-only proof:
      `nix build .#kernelMainlineUartProgressMemoryExactObjects --no-link --print-out-paths`.
      Offline narrow build from source checkpoint `29979175` returned0 against
      actual selected dev, no overlay; three RISC-V objects, Memory observer/
      state/completion/256-aligned buffer, target acquire/release/API and
      inherited buffers/getters passed. Same host proof; concurrency/physical
      output/receipt/recovery remain unverified.
- [x] 5i.4 Implement typed minimal-only Memory controller, reject conflicting
      breadcrumb/post-sample selection, retain exact qualification/normal guards,
      one fresh stimulus/passive capture and strict single-summary facts. Actual
      NEW matching positive preparation required before checking this task.
      Narrow proof: `python3 tests/test_mainline_uart_progress_memory_controller.py`.
      Preparation: [Memory controller host proof](../../../docs/evidence/mainline-uart-progress-memory/controller/README.md)
      records 20 exact-summary/real-pump/transport/qualification fixtures plus
      unchanged 20 PostSample/18 Breadcrumbs/20 numeric/100 minimal/14 shell/36
      ordinary checks. Actual fjmxf6 old artifact fails the new reviewed worker
      gate before UART. Consistent incomplete/timeout summary, worker completion,
      receipt and protected return remain independent facts; no candidate reboot
      or extra input follows. [Actual NEW positive host proof](../../../docs/evidence/mainline-uart-progress-memory/positive-controller-host/README.md)
      now passes against frozen `7af8f7b8`, realized lznjjfx1 bundle/1pvqbm4 dev,
      same-drv config, reviewed 307d7c source, unique linked summary format/setup,
      actual archived executables/shared loader and sole additional gate
      (353 to 381-byte literal command). No UART/build or performed protected
      board check by this qualifier. Tasks 5i.5–6 and 5b.5 remain open.
- [ ] 5i.5 After NEW guarded protected recovery plus exact host/controller proof,
      reserve board/UART and run one comparison; commit fixed public facts and
      independent protected recovery or explicit pending operator reset.
      Command: `python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal --same-image-shell-pid1 --uart-progress --uart-progress-memory --bundle BUNDLE --manifest PRIVATE_MANIFEST --normal-report PRIVATE_NORMAL --log PRIVATE_LOG --result PRIVATE_RESULT`.
      Memory progress/output/receipt/recovery remain separate;5b.5 stays open.
- [ ] 5i.6 Independently reconcile changed-output intervention limits, review,
      land/push public evidence and verify exact CI/published revision.
      Planning proof: `openspec validate the-board-runs-a-mainline-kernel --strict`.
