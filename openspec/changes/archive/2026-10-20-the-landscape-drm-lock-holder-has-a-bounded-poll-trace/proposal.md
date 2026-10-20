## Why

Landscape card motion still occasionally pauses for roughly 200 ms. Committed kernel-stack evidence locates four pauses in DRM modeset mutex acquisition, but does not identify the holder; fixing the wrong subsystem would leave the pauses intact.

## What Changes

- Add a bounded, isolated function-entry trace of the connector-poll critical section alongside the established scheduler/syscall diagnostic.
- Correlate measured polling-worker lock intervals with long shell DRM calls and publish a qualified result, including an inconclusive result if that is what the trace supports.
- Commit source, clock, loss, runtime, cleanup and publication evidence. The physical board is required for measurements; host fixtures prove only tooling.

Non-goals: changing polling/hotplug defaults, rebuilding/flashing the image, changing landscape geometry, claiming native/glass/optical acceptance, or completing the deferred portrait change.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None. Diagnostic tooling/evidence only; `skip_specs: true`.

## Impact

Own `tools/landscape-drm-holder.py`, `docs/evidence/landscape-drm-holder/`, this change, and exact owned binary inventory rows if compressed exports are committed. Reuse the established capture workload and strict numeric trace parser. No shipped behavior changes.
