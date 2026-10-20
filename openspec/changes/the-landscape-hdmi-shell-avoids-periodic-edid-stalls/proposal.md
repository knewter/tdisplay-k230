## Why

Landscape card motion occasionally pauses for ~200ms. Committed board traces identify connector polling as the lock holder, and its EDID-read path consumes99.76–99.78% of measured slow holds despite the monitor staying connected. The system should retain link detection without repeatedly refreshing already cached monitor data in that path.

## What Changes

- Skip HDMI metadata refresh only in the generic polling worker when old/new status are both connected and a cached EDID blob exists.
- Preserve detection/status notification, missing-cache reads, status transitions, forced/requested mode probes, and detection outside that worker, including HPD paths that already updated connector status.
- Cross-build, stage a recoverable candidate, verify the running board and repeated landscape motion, then physically check cable switching and user input before persistent promotion.
- Keep the current landscape profile and deferred portrait work separate. Archive only with committed named hardware proof.

Non-goals: disabling hotplug/polling, changing GPIO/IRQ/DSI timing or EDID contents, changing portrait/trackpad defaults, a universal input-latency guarantee, or accepting QEMU/host proof as physical evidence. Kernel/source tests run on the host; runtime, cable and user-input checks need the board/operator.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `display/hdmi`: steady connected monitoring avoids the measured periodic EDID stall while initial/missing-cache/transition/requested refresh and cable-selected display behavior remain qualified.

## Impact

Own `nix/kernel-mainline-drm.nix`, a narrow generic-bridge patch under `nix/patches/mainline/`, `tools/test-hdmi-stable-poll.py`, `tools/hdmi-stable-poll-proof.py`, this change and `docs/evidence/hdmi-stable-poll/`. Exact binary inventory rows only for new committed physical captures. Existing diagnostics and current landscape boot remain recoverable. A proposal/source build does not mean a deployed or accepted fix.
