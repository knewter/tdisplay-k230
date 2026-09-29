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

## 5. Confirm no existing output changed

- [x] 5.1 Confirm `.#kernel`, `.#deviceTree`, and
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

## 6. Publish

- [x] 6.1 Validate with `openspec validate the-board-runs-a-mainline-kernel
      --strict`, checking the exit code directly (never via a pipe), per
      AGENTS.md.
- [x] 6.2 Commit the proposal, design, tasks, spec delta, research
      document, and the new `nix/`/`flake.nix` files together on
      `feat/mainline-kernel`, and report the branch/base/commit hash to the
      coordinator for an early merge to `master`, per AGENTS.md's "keep
      changes moving".

## Remaining evidence gate (explicitly not performed by this change)

Reaching a serial console on real hardware is a **hardware milestone**, not
a host build, per `.skills/k230-spec-change/SKILL.md`'s QEMU-vs-hardware
distinction. This change does not touch `/dev/ttyACM0`, does not request a
board slot, and does not claim this gate. The operator command a future
change (or the coordinator, directly) would run once a board slot is free:

```
flock /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=10
```

— after manually interrupting U-Boot and `ext4load`-ing
`result-kernelMainlineBootFiles/Image-mainline` and
`result-kernelMainlineBootFiles/k230-tdisplay-mainline.dtb` from wherever the
coordinator stages them on the card, then `bootm`/`booti` at the loaded
addresses with a `console=ttyS0,115200` (or matching mainline-console-name)
bootarg baked into the DTB's `/chosen/bootargs` the same way
`nix/sd-image.nix` already does for the vendor image. No rootfs is staged;
a kernel panic for lack of one, with legible OpenSBI + Linux boot output
first, is this gate's actual pass condition (see
`docs/research/mainline-kernel-inventory.md`'s phased plan, milestone 2).
