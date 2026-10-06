## ADDED Requirements

### Requirement: The mainline full shell starts the same units as the vendor-kernel shell
The `k230-mainline-drm-shell` variant SHALL start every systemd unit the
vendor-kernel coherent shell starts, except units listed as recorded non-goals
with their reason, and it SHALL remain an opt-in trial that never replaces the
protected normal system or its boot selection.

#### Scenario: No unexpected failed units
- **WHEN** the mainline full shell has booted through the guarded trial
- **THEN** `systemctl --failed` on the serial console lists no units other than recorded non-goals
<!-- UNVERIFIED: firewall.service failed on 2026-10-06 -->

#### Scenario: Normal system unaffected
- **WHEN** the trial ends and the board returns to the normal system
- **THEN** the protected normal identities, eight boot hashes and three shell services are unchanged
