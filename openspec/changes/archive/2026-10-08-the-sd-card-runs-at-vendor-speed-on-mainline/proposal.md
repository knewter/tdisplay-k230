## Why

On the board's default mainline kernel the SD card reads at 6.1 MB/s, against
23.3 MB/s on the vendor 6.6 kernel with the same card, the same High-Speed 4-bit
3.3 V mode and the same CPU speed
(`docs/evidence/mainline-sd-throughput/README.md`). Every boot, package
activation and app launch pays for it. The SDHCI driver derives its base clock
from the `core` clock's rate. Vendor binds `core` to a fixed 100 MHz clock;
our mainline DTS binds it to the 333 MHz `HS_SD*_BASE_GATE`, so the driver
divides by 8 and the card actually runs at about 12.5 MHz.

Three smaller mainline leftovers ride along: the PDMA driver takes its AXI gate
twice, the guarded trial tool's "returned to normal" check still looks for a
`6.6.36` banner that the new mainline normal never prints, and an intermittent
`mmc1: Got command interrupt ... even though no command operation was in
progress` register dump appears on about 1 in 6 mainline boots.

## What Changes

- The mainline DTS gives both SD controllers a fixed 100 MHz `core` clock, as
  the vendor tree does. The driver patch keeps holding `HS_SD*_BASE_GATE` under
  a new `base` name, so no gate becomes unclaimed.
- `k230-peridma.c` drops the redundant single-clock claim; the bulk claim
  already holds every PDMA clock.
- `tools/mainline-drm-system-trial.py` detects a premature return to normal
  by the installed normal's kernel string from the committed baseline rather
  than a `6.6.36` literal.
- The spurious mmc1 command interrupt is counted across repeated boots after
  the clock fix and recorded as fixed or as a known, characterised leftover.

Non-goals: UHS/1.8 V signalling (both kernels cap at High-Speed 50 MHz), switching
`.#sdImage` to mainline, and the audible headset check.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `system/kernel`: SD storage and the SDIO radio run at the vendor kernel's
  clock rate under mainline.

## Impact

- Nix: `nix/dts/k230-tdisplay-mainline.dts`, `nix/patches/mainline/k230-sdhci-clocks.patch`,
  `nix/patches/mainline/k230-peridma.c`; the mainline kernel and boot bundle rebuild.
- Board: the installed mainline normal is updated through the coherent
  stage/trial/install flow, and the rollback roots are retained. Wi-Fi association
  (SDIO, mmc0) must be re-proven because its base clock changes too.
- Tooling: `tools/mainline-drm-system-trial.py` and its tests.
