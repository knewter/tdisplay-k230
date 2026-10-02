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
and an absolute reboot command. That corrected probe remains unperformed;
it retains the exact matching bundle, strict load count/CRC checks and
unchanged normal selection. The controller and proof limits are recorded in
`docs/evidence/mainline-display/physical-2026-10-01/initrd-shell-diagnostic.md`.

The 2026-10-02 operator power swap restored the selected normal system:
fresh boot ID, exact system/profile/kernel/init, three active shell services,
eight unchanged protected hashes and photographed/native Home after IPC
commands. See
`docs/evidence/mainline-display/physical-2026-10-01/power-swap-recovery-2026-10-02/README.md`.
Normal restoration is now proved; mainline task 5b.5 stays open for usable
root login and deliberate touch evidence. These captures show the normal
vendor-kernel system, not a working mainline shell.
