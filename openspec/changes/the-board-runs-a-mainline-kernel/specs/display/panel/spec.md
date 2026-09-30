## ADDED Requirements

### Requirement: The mainline display candidate stays opt-in and evidence-bounded

The project MAY provide a separately named mainline DRM device tree and
boot-files candidate for the RM69A10 panel. This candidate SHALL remain
outside the vendor/default outputs and SHALL NOT claim panel operation from
source/API compilation or a host DTB check. Its display power-domain behavior
remains UNVERIFIED because the pinned mainline source has no K230 display
power-domain provider.

*Grounding: the board panel wiring and init sequence are transcribed from
`nix/dts/k230-tdisplay.dts` and
`nix/dts/display-rm69a10-568x1232.dtsi`. The opt-in DTS is
`nix/dts/k230-tdisplay-mainline-drm.dts`; host compilation and its limits are
recorded in `docs/evidence/mainline-display-dtb.md`. No board probe or panel
photograph exists for this candidate.*

#### Scenario: Someone asks whether the mainline candidate lights the panel

- **WHEN** only host DTS or source/API checks exist
- **THEN** the response says panel probe and illumination are UNVERIFIED and
  does not treat omitted display power-domain wiring as proven unnecessary
