## ADDED Requirements

### Requirement: The mainline touch candidate is not reported as working without board evidence

The project MAY describe the board's Goodix-compatible touch controller in
the opt-in mainline DRM device tree. It SHALL preserve the candidate's
reported digitizer dimensions and GPIO/interrupt source from the board DTS,
and SHALL record serial probe evidence separately from physical touch
acceptance. Coordinate mapping and physical touch behavior remain UNVERIFIED
until deliberate on-panel interaction is recorded.

*Grounding: the candidate node in
`nix/dts/k230-tdisplay-mainline-drm.dts` follows the board wiring recorded in
`nix/dts/k230-tdisplay.dts`; the exact host DTB check and limits are in
`docs/evidence/mainline-display-dtb.md`. The pinned mainline Goodix Berlin
I2C driver includes `goodix,gt9916`, and the later committed
`docs/evidence/mainline-display/physical-2026-10-01/README.md` records Goodix
input registration. Registration is partial probe evidence; it does not prove
coordinate mapping or deliberate finger interaction.*

#### Scenario: Someone asks whether touch works under the mainline candidate

- **WHEN** only the candidate source or a round-tripped host DTB is available
- **THEN** the response leaves controller compatibility, probe, and touch
  interaction UNVERIFIED
