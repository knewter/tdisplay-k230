## ADDED Requirements

### Requirement: A steady HDMI connection avoids periodic monitor-refresh stalls

While a previously discovered HDMI monitor remains connected, routine background link detection SHALL retain cached monitor metadata instead of repeatedly reading it in the modeset critical section. The system SHALL continue detecting physical cable changes. Initial discovery, missing cached metadata, link-status transitions and explicitly requested mode/monitor refresh SHALL retain their refresh behavior. The active HDMI profile and panel-return/input policy SHALL remain unchanged by this fix.

Qualification SHALL distinguish source/API tests, injected motion/timing evidence and fresh physical cable/input observations. It SHALL NOT claim a universal latency bound or portrait acceptance from the bounded landscape test.

*Grounding: `docs/evidence/landscape-drm-holder/README.md` associates five late inputs with connector-poll lock holds; `docs/evidence/landscape-hdmi-detect/README.md` measures the EDID path at170–184ms and99.76–99.78% of three complete slow holds. Pinned generic bridge and probe-helper source establishes the polling context and refresh call ordering. Source/host and cross-build results are committed separately; candidate bounded timing is qualified separately. Operator physical acceptance, guarded persistent promotion, ordinary boot/build-ID and normal-state cleanup are committed in `docs/evidence/hdmi-stable-poll/physical-a/operator-acceptance.json` and `docs/evidence/hdmi-stable-poll/persistent/summary.json`; source, injected, operator and SSH runtime evidence retain their individual limits.*

#### Scenario: The discovered monitor stays connected during card motion

- **WHEN** the same monitor stays connected while repeated landscape card motion and background detection are observed
- **THEN** at least three complete monitored polling cycles use the cached metadata, show no repeated EDID-reader path or >100ms poll-held mutex interval, and the paired bounded motion report retains every measured latency without inferring physical smoothness from injected events

#### Scenario: Metadata is absent or the link changes

- **WHEN** monitor discovery has no cached metadata or detection observes a link-status transition
- **THEN** monitor metadata is refreshed/cleared as appropriate and normal connector status notification remains available

#### Scenario: A caller requests fresh modes or a hotplug handler has already updated status

- **WHEN** detection/mode refresh runs outside routine polling, including a hotplug path whose status field is already current
- **THEN** the existing explicit metadata refresh is preserved

#### Scenario: The operator checks the cable and touch path on the candidate

- **WHEN** the operator physically unplugs/replugs HDMI and performs a real Overview gesture on the candidate kernel
- **THEN** the visible panel/HDMI and touch/trackpad transitions still work without reboot and HDMI returns to the retained landscape profile; fresh physical observations are committed separately from host/injected evidence
