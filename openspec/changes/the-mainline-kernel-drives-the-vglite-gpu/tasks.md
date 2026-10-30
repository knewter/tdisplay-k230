## 1. Host build (laptop claims)

- [ ] 1.1 Port the vendor driver to 7.3 as sources under `nix/patches/mainline/vglite/` plus `nix/vglite-kernel-module.nix` (out-of-tree, same pattern as `nix/k230-wifi-driver.nix`), enabling the `vglite` clock and resetting via the mainline binding. Proof: `nix build .#k230-vglite-module --out-link <scratch>/vglite-ko` yields `vglite.ko` whose `modinfo` vermagic is `7.3.0-rc5 SMP preempt mod_unload riscv` and which carries the alias `of:N*T*Cverisilicon,gc8000ul`. Host build only.
- [ ] 1.2 Add the `gpu@90800000` node to `nix/dts/k230-tdisplay-mainline-drm-common.dtsi`. Proof: `nix build` of the mainline display DTB attribute and `fdtget` printing compatible, reg, interrupts, clocks, resets and power-domains from the built DTB. Host build only.
- [ ] 1.3 Add the module to the mainline shell system's `boot.extraModulePackages` (kernel Image unchanged) and keep the opt-in renderer building. Proof: `nix build .#nixosConfigurations.k230-mainline-drm-shell.config.system.build.toplevel` and `nix build .#shell-compositor-vglite --no-link`; the system's kernel store path equals the one behind `/run/current-system/kernel` on the board. Host build only.
- [ ] 1.4 Add a bounded no-reboot trial route (overlay companion module). Proof: its build, plus a `dtc` round trip of the embedded overlay. Host build only.

## 2. Board bring-up (hardware claims; one operator at a time)

- [ ] 2.1 Probe: with the DTB node installed (or the trial route loaded) the driver binds and `/dev/vg_lite` exists. Proof: transcript of `ls -l /dev/vg_lite`, the probe lines in `dmesg` and the bound-driver link under `/sys/bus/platform/devices/`, committed under `docs/evidence/vglite-mainline-kernel/`. Board observation.
- [ ] 2.2 GPU smoke: the existing probe passes on the board. Proof: output and exit code of the `.#k230-vglite-probe` or `.#k230-vglite-validation` binary with the expected pixels, committed. Board observation.
- [ ] 2.3 After a reboot with the permanent DTB node: display, touch, Wi-Fi and audio unchanged, and the opt-in renderer selects the device. Proof: boot ID, shell and seatd active, a `grim` capture of the shell, an injected touch, a Wi-Fi association check and an audio device list, committed. Board observation (injected touch; no glass claim).
- [ ] 2.4 Record the rollback route used and that `/run/current-system` equals `init=` in `/boot/bootargs.txt` afterwards. Board observation.

## 3. Close-out

- [ ] 3.1 `openspec validate the-mainline-kernel-drives-the-vglite-gpu --strict` and `./tools/blob-scan.py --no-vendor`; then record the device in `the-shell-trials-vglite-composition` so its tasks 2.5, 3.2 and 3.3 can run.
