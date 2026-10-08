## Context

`sdhci-of-kendryte.c` (vendor driver forward-ported, `nix/patches/mainline/`) sets
`SDHCI_QUIRK_CAP_CLOCK_BASE_BROKEN`, so `host->max_clk` is `clk_get_rate("core")`.
Vendor `k230.dtsi` binds `core` (and `bus`) to `dummy_sd`, a 100 MHz `fixed-clock`.
Our mainline DTS binds `core` to `K230_HS_SD{0,1}_BASE_GATE`, a child of the
333 MHz SD AXI source in mainline `clk-k230.c`. The driver therefore programs
/8 for 50 MHz. The measured 6.1 MB/s matches a 100 MHz reference divided by 8.
Earlier mainline work found that every SD gate must stay claimed, or
`clk_disable_unused` gates it.

## Goals / Non-Goals

**Goals:** vendor-equal SD card clock on both controllers with no gate released;
remove the PDMA double claim; make the trial tool's return-to-normal check track
the installed normal.

**Non-Goals:** UHS modes, `.#sdImage`, upstreaming.

## Decisions

- **Fixed 100 MHz `core`, `BASE_GATE` kept as `base`.** A new `fixed-clock`
  node supplies the rate. The driver patch grows its bulk list from
  axi/block/timer to base/axi/block/timer, so `BASE_GATE` stays prepared and
  enabled exactly as today. We rejected re-pointing `core` alone (it would
  release `BASE_GATE` to unused-clock cleanup), a `fixed-factor` child of the
  gate (it encodes a false rate relation), and `CLK_IS_CRITICAL` (an extra clk
  driver patch for what is a consumer description).
- **Same change for mmc0.** The SDIO controller shares the driver and the
  wiring; vendor uses the same `dummy_sd`.
- **Trial tool reads the baseline.** `mainline-drm-system-trial.py` already
  loads `rd.NORMAL_BASELINE`, and the "Linux version <normal uname>" check uses
  its `uname`. Because normal and candidate now share 7.3.0-rc5, that banner
  check alone cannot tell them apart; `U-Boot SPL` remains the primary signal.

## Risks / Trade-offs

- A wrong base rate could over-clock the card → keep High-Speed 50 MHz and
  confirm `actual clock` and data integrity (sha256 of a large file read twice).
- Wi-Fi regressions → association proof on the board.
- The spurious interrupt may be unrelated to clocks → it is counted, not
  claimed fixed.

## Migration Plan

Build, then stage, trial-boot and install through the coherent tools (as in
`docs/evidence/mainline-default-boot/`). Rollback is the stage's `install.py rollback`.
