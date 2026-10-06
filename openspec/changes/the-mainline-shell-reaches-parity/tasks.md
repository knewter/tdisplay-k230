## 1. Shared kernel fixes (host build, then board)

- [ ] 1.1 Move `k230-clk-spi2axi-critical.patch` and `k230-clk-vpu-ddrcp2-dphy.patch` into `nix/kernel-mainline.nix` and append `nix/kernel-firewall.config` to the mainline kernel config. Host proof: `nix build .#kernelMainline .#kernelMainlineDrm --no-link` and the built `.config` contains the firewall symbols.
- [ ] 1.2 Board: boot the full mainline shell; `systemctl is-active firewall` is active and `systemctl --failed` is empty. Hardware proof: guarded `tools/mainline-drm-system-trial.py begin` on `kernelMainlineDrmShellTrialBootFiles`, then recover.
- [ ] 1.3 Board: boot the console mainline variant with ordinary cleanup to a qualified login. Hardware proof: the same controller on the console bundle.

## 2. Clock table record (documentation)

- [x] 2.1 Commit the vendor-versus-mainline gate comparison to `docs/research/` with the recorded reasons for the shared USB bit and the unmodelled `clkext` gate. Proof: committed file; `openspec validate the-mainline-shell-reaches-parity --strict`.
      [Comparison](../../../docs/research/k230-clock-gates-vendor-vs-mainline.md) committed with the shared-USB-bit and clkext reasons.

## 3. Touch in the shell and controller retrieval (tooling, then board)

- [ ] 3.1 Replace raw `evtest` read-back with a bounded board-side summary line in `tools/mainline-drm-system-trial.py`, with fixtures. Host proof: `python3 tests/test_mainline_drm_system_trial.py` and a new focused test.
- [ ] 3.2 Board (operator present): on the full mainline shell, a deliberate tap on a Home target changes the panel as under the vendor kernel; camera video plus sway input log. Hardware proof: controller `touch --real-touch` reports complete contact; camera recording.

## 4. Power key (kernel + DT, then board)

- [ ] 4.1 Forward-port `k230-pmu-pwrkey.c` to 7.3 with a PMU DT node claiming the PMU APB gate. Host proof: `nix build .#kernelMainlineDrm` and the object has the driver.
- [ ] 4.2 Board (operator present): pressing the side button shows the power sheet on the mainline shell; key event logged. Hardware proof: trial boot, camera, `evtest` summary.

## 5. Audio (kernel + DT, then board)

- [ ] 5.1 Forward-port `sound/soc/canaan` with the external-I2S-switch patch and owned audio/codec clocks; DT nodes from the vendor tree. Host proof: kernel builds; `aplay -l` lists the card in a board boot log.
- [ ] 5.2 Board (listener or recording microphone): a test tone through the default PipeWire sink is heard; lowering the shell volume makes it quieter. Hardware proof: trial boot plus audio recording or operator confirmation.

## 6. Wi-Fi (DT + Nix, then board)

- [ ] 6.1 Enable `mmc_sd0` SDIO with owned clocks in the mainline DT and build the RTL8189FTV module against the mainline kernel. Host proof: `nix build` of the module for the mainline kernel, or a committed failure log with a successor task.
- [ ] 6.2 Board: the interface appears, associates through the protected credential path, gets an address and reaches a host, each stage recorded separately with no secrets in evidence. Hardware proof: trial boot and staged connectivity checks.

## 7. Thermal and remaining drivers (kernel, inventory)

- [ ] 7.1 Forward-port `canaan_thermal.c` (bounded read loop) with its DT node. Host proof: kernel builds.
- [ ] 7.2 Board: the thermal zone reads a plausible temperature that rises under load. Hardware proof: trial boot and two readings.
- [ ] 7.3 Record ADC, PWM and crypto disposition (ported or non-goal with the consuming unit) in `docs/research/mainline-kernel-inventory.md`. Proof: committed inventory diff.

## 8. Land and publish

- [ ] 8.1 Independent review per group, land on master, push, and verify the exact CI run and published work page. Proof: `openspec validate the-mainline-shell-reaches-parity --strict`, CI run id, page revision.
