## 1. Shared kernel fixes (host build, then board)

- [x] 1.1 Move `k230-clk-spi2axi-critical.patch` and `k230-clk-vpu-ddrcp2-dphy.patch` into `nix/kernel-mainline.nix` and append `nix/kernel-firewall.config` to the mainline kernel config. Host proof: `nix build .#kernelMainline .#kernelMainlineDrm --no-link` and the built `.config` contains the firewall symbols.
      Built 725cc92e: full-shell bundle 8bljkjxn…, console bundle bwvzapyq…; kernel config has NETFILTER_XTABLES/NF_TABLES/NFT_COMPAT/NFT_CT=y (structuredExtraConfig looped on NFT_COMPAT; seeded into defconfig instead).
- [x] 1.2 Board: boot the full mainline shell; `systemctl is-active firewall` is active and `systemctl --failed` is empty. Hardware proof: guarded `tools/mainline-drm-system-trial.py begin` on `kernelMainlineDrmShellTrialBootFiles`, then recover.
      2026-10-06 bundle 8bljkjxn…: controller qualified; serial console shows uname 7.3.0-rc5, firewall active, 0 failed units, shell/shell-ui/seatd active; board self-recovered (private capture ~/tmp/k230-bisect-PARITY12).
- [x] 1.3 Board: boot the console mainline variant with ordinary cleanup to a qualified login. Hardware proof: the same controller on the console bundle.
      2026-10-06 console bundle 437ggvdp… (7f087e1e): qualified ordinary login with `clk: Disabling unused clocks`, 0 failed units. Needed the SD five-clock ownership moved to the base kernel (first attempt stalled after initrd Basic System). Its `reboot` then stopped at "Restarting system" (restart handler was DRM-only), fixed in 6f86eed2: console bundle j05znfgq… then booted, rebooted itself into the normal system, and protected recovery passed with no operator reset.

## 2. Clock table record (documentation)

- [x] 2.1 Commit the vendor-versus-mainline gate comparison to `docs/research/` with the recorded reasons for the shared USB bit and the unmodelled `clkext` gate. Proof: committed file; `openspec validate the-mainline-shell-reaches-parity --strict`.
      [Comparison](../../../docs/research/k230-clock-gates-vendor-vs-mainline.md) committed with the shared-USB-bit and clkext reasons.

## 3. Touch in the shell and controller retrieval (tooling, then board)

- [x] 3.1 Replace raw `evtest` read-back with a bounded board-side summary line in `tools/mainline-drm-system-trial.py`, with fixtures. Host proof: `python3 tests/test_mainline_drm_system_trial.py` and a new focused test.
- [ ] 3.2 Board (operator present): on the full mainline shell, a deliberate tap on a Home target changes the panel as under the vendor kernel; camera video plus sway input log. Hardware proof: controller `touch --real-touch` reports complete contact; camera recording.

## 4. Power key (kernel + DT, then board)

- [x] 4.1 Forward-port `k230-pmu-pwrkey.c` to 7.3 with a PMU DT node claiming the PMU APB gate. Host proof: `nix build .#kernelMainlineDrm` and the object has the driver.
      Kernel built (ky3ac6dg…); on the board `K230 PMU Power Key` registers (IRQ 175).
- [ ] 4.2 Board (operator present): pressing the side button shows the power sheet on the mainline shell; key event logged. Hardware proof: trial boot, camera, `evtest` summary.

## 5. Audio (kernel + DT, then board)

- [x] 5.1 Forward-port `sound/soc/canaan` with the external-I2S-switch patch and owned audio/codec clocks; DT nodes from the vendor tree. Host proof: kernel builds; `aplay -l` lists the card in a board boot log.
      Kernel built with PDMA and audio; on the board `/proc/asound/cards` lists `K230_I2S_INNO` with playback and capture PCMs.
      Partial: driver/DT/Kconfig forward-ported and compile-verified (module build + dtc). The DMA blocker is now also resolved: `drivers/dma/k230_peridma.c` forward-ported as `nix/patches/mainline/k230-peridma.c` (mainline dmaengine driver for `canaan,k230-pdma`, claims `K230_SHRM_PDMA_AXI_GATE`), wired into `nix/kernel-mainline.nix`, with a `&pdma` DT node and `dmas`/`dma-names` added to the `i2s` node in `nix/dts/k230-tdisplay-mainline.dts` -- module-compile (`W=1`, zero warnings) and dtc/cpp validated, same evidence classes as the rest of this task. No full kernel build or board boot has been run from any worktree yet: `aplay -l` proof and a full kernel build remain open. See `docs/research/mainline-audio-port.md` and `docs/evidence/mainline-audio-port/pdma-*.json`.
- [ ] 5.2 Board (listener or recording microphone): a test tone through the default PipeWire sink is heard; lowering the shell volume makes it quieter. Hardware proof: trial boot plus audio recording or operator confirmation.

## 6. Wi-Fi (DT + Nix, then board)

- [x] 6.1 Enable `mmc_sd0` SDIO with owned clocks in the mainline DT and build the RTL8189FTV module against the mainline kernel. Host proof: `nix build` of the module for the mainline kernel, or a committed failure log with a successor task.
      `nix build .#k230-wifi-driver-mainline` produces `8189fs.ko` (vermagic 7.3.0-rc5); on the board the SDIO card enumerates, `8189fs`/`cfg80211` load and `wlan0` is up.
      Partial: `&mmc_sd0` enabled with its base two clocks in `nix/dts/k230-tdisplay-mainline.dts` and the three extra `K230_HS_SD0_{AXI,CARD,TIMER}_GATE` clocks in `nix/dts/k230-tdisplay-mainline-drm.dts` (mirrors the existing `&mmc_sd1` pattern), dtc/cpp-validated. Module-compile attempt against the pinned mainline dev tree found and fixed four real v7.3-rc5 API-drift classes (kbuild `EXTRA_CFLAGS`->`ccflags-y`, timer API rename, pppoe uapi flexible-array restriction, `strncpy` removal) as `nix/patches/mainline/rtl8189fs-mainline-v7.3-rc5.patch`, wired via a new `extraPatches` parameter on `nix/k230-wifi-driver.nix` and a new `k230-wifi-driver-mainline` flake output (vendor-kernel `k230-wifi-driver` unaffected). Committed failure log: the module does not link -- `CONFIG_CFG80211` is not set in the dev tree (added as a candidate `module` to `nix/kernel-mainline.nix`, itself unbuilt) and `ioctl_cfg80211.c`'s `cfg80211_ops` callbacks need a real `net_device*`->`wireless_dev*` port, out of this task's rename-only scope. See `docs/research/mainline-wifi-port.md` and `docs/evidence/mainline-wifi-port/*.json`. No `nix build`, full kernel build, or board action was run.
- [x] 6.2 Board: the interface appears, associates through the protected credential path, gets an address and reaches a host, each stage recorded separately with no secrets in evidence. Hardware proof: trial boot and staged connectivity checks.
      2026-10-06 full mainline shell (bundle rrqzwdi4…): `k230-wifi` active; separately recorded associated=yes, ipv4=yes, gateway ping=yes using the existing protected credential path; no SSID or address recorded (private capture ~/tmp/k230-parity-wifi-thermal).

## 7. Thermal and remaining drivers (kernel, inventory)

- [x] 7.1 Forward-port `canaan_thermal.c` (bounded read loop) with its DT node. Host proof: kernel builds.
      Kernel built; on the board `canaan_thermal_zone` reads 7218 (vendor kernel 7223).
- [x] 7.2 Board: the thermal zone reads a plausible temperature that rises under load. Hardware proof: trial boot and two readings.
      Same boot, converted driver: thermal_zone0 52406 m°C idle, 54506 m°C after 60 s of CPU load. The driver previously returned the raw TS_DATA code (7221); conversion uses Canaan's documented polynomial.
- [x] 7.3 Record ADC, PWM and crypto disposition (ported or non-goal with the consuming unit) in `docs/research/mainline-kernel-inventory.md`. Proof: committed inventory diff.
      Inventory records ADC/PWM and crypto as non-goals (no shipped consumer) and power key, thermal, audio and Wi-Fi as ported.

## 8. Land and publish

- [ ] 8.1 Independent review per group, land on master, push, and verify the exact CI run and published work page. Proof: `openspec validate the-mainline-shell-reaches-parity --strict`, CI run id, page revision.
