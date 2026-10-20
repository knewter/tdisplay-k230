## Why

Landscape motion still suffers occasional ~200ms stalls. The committed holder diagnostic identifies connector polling as the mutex holder, but the operation consuming time inside detection is unmeasured; a fix needs that narrower grounding.

## What Changes

- Add an isolated function-entry probe measuring source-defined stages inside the polling detector, including its EDID-read path.
- Obtain one bounded idle-board trace with at least three complete EDID-stage observations after a short harmless-sleep controller smoke.
- Commit sanitized records, source hashes, monotonic clock/loss/count checks, interpretation limits, cleanup and publication proof.

Non-goals: kernel/driver/default changes, disabling polling, rebuilding/flashing, changing landscape, repeating gesture trials, or native/glass/optical acceptance. Measurements require the physical board; host fixtures prove only tooling.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None. Tooling/evidence only; `skip_specs: true`.

## Impact

Own `tools/landscape-hdmi-detect.py`, `docs/evidence/landscape-hdmi-detect/`, and this change. Reuse holder interval qualification and protected runtime guards. Add exact owned inventory rows only if binary assets are introduced. No shipped capability changes.
