## Status (2026-09-28)

**KEEP**, per the user's "stale as suggested" decision on
`docs/closeout/stale-triage.md`. Schedule one short board session for task
group 2 (the two power-cycle observations over J3: card removed, and
SW3/BOOT0 held). The optional destructive card-corruption test in task group
3 is **skipped for now** — see the note on that task group below; it is not
withdrawn, only deferred, and remains conditional on task group 2's result if
it is picked up later.

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
- If BootROM entry works, characterize the vendor `k230_flash` tool by writing
  a disposable deliberately nonbootable-stage1 card and verify that the board
  boots afterward. An unsafe or unattempted write remains incomplete; it is
  not converted into a success claim. If entry does not work, document the
  observed limit and retain the card-reader and UMS recovery procedures.
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

The negative-result boundary is explicit: absence of a device is a grounded
limitation only after both power-cycle tests are captured; a missing or unsafe
write leaves recovery verification incomplete.
