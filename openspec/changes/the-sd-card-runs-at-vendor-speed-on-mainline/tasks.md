## 1. Source (host)

- [ ] 1.1 Add the fixed 100 MHz SD core clock to `nix/dts/k230-tdisplay-mainline.dts` for `mmc_sd0`/`mmc_sd1` and extend `k230-sdhci-clocks.patch` to claim `base`; build `.#kernelMainlineDrmShellBootFiles`. Proof: build succeeds and the DTB decompiles with the new clocks.
- [ ] 1.2 Drop the redundant PDMA single-clock claim in `k230-peridma.c`. Proof: kernel builds.
- [ ] 1.3 Make `tools/mainline-drm-system-trial.py` use the baseline normal `uname` for its return-to-normal banner check, with a test. Proof: `python3 tests/test_mainline_drm_system_trial.py`.

## 2. Board

- [ ] 2.1 Stage and trial-boot the new bundle; record `mmc0`/`mmc1` ios, `clk_summary` for SD gates, `dd` throughput, a repeated read checksum match and PDMA audio playback without crash. Proof: serial record in `docs/evidence/mainline-sd-throughput/`.
- [ ] 2.2 Install the new bundle as the normal; verify an ordinary reboot (7.3.0-rc5, services, no failed units) and Wi-Fi association. Proof: install result and post-boot record.
- [ ] 2.3 Reboot at least 10 times and count `Got command interrupt` occurrences; record the result as fixed or characterised. Proof: count table in the evidence README.

## 3. Publication

- [ ] 3.1 Review, land, push, verify CI and the published page; archive when every task above holds. Proof: `openspec validate --strict`, CI run id, page revision.
