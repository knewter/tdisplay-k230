## ADDED Requirements

### Requirement: The mainline touch candidate is not reported as working without board evidence

The project MAY describe the board's Goodix-compatible touch controller in
the opt-in mainline DRM device tree. It SHALL preserve the candidate's
reported digitizer dimensions and GPIO/interrupt source from the board DTS,
and SHALL leave controller compatibility, probe, coordinate mapping, and
physical touch behavior UNVERIFIED until serial probe evidence and deliberate
on-panel interaction are recorded.

*Grounding: the candidate node in
`nix/dts/k230-tdisplay-mainline-drm.dts` follows the board wiring recorded in
`nix/dts/k230-tdisplay.dts`; the exact host DTB check and limits are in
`docs/evidence/mainline-display-dtb.md`. The pinned mainline Goodix Berlin
I2C driver includes `goodix,gt9916`, but no board probe has established that
this controller accepts that compatible.*

#### Scenario: Someone asks whether touch works under the mainline candidate

- **WHEN** only the candidate source or a round-tripped host DTB is available
- **THEN** the response leaves controller compatibility, probe, and touch
  interaction UNVERIFIED
