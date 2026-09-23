## Why

The completed U-Boot UMS change proves that a running stage 1 can expose the
SD card over USB. It does not prove the independent BootROM recovery path used
when the card has no bootable stage 1. The original proposal carried those
unperformed tests alongside completed UMS work; this successor keeps the
recovery promise explicit and testable without implying that UMS evidence is
BootROM evidence.

## What Changes

- Test BootROM USB entry with the TF card removed and with SW3 held at power-on.
- Record host enumeration, VID/PID, connector, button state, and serial output
  for both outcomes, including a clear negative result.
- If BootROM entry works, characterize the vendor `k230_flash` tool with a
  disposable known image and verify the board boots afterward. If it does not,
  document the observed limit and retain the card-reader recovery procedure.
- Reconcile the `image/boot-chain` requirement and evidence links after the
  hardware result. Never remove an UNVERIFIED marker before the corresponding
  observation exists.

## Capabilities

### Modified Capabilities

- `image/boot-chain` — separates observed BootROM recovery from the already
  proven U-Boot UMS path and records the exact recovery procedure or failure.

## Impact

Hardware-only characterization, evidence files, and OpenSpec grounding. No
firmware, kernel, flake, or automatic boot behavior changes are required before
an observed recovery path justifies them.
