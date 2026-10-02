## ADDED Requirements

### Requirement: The mainline display candidate stays opt-in and evidence-bounded

The project MAY provide a separately named mainline DRM device tree and
boot-files candidate for the RM69A10 panel. This candidate SHALL remain
outside the vendor/default outputs and SHALL NOT claim panel operation from
source/API compilation or a host DTB check. Its display power-domain behavior
remains UNVERIFIED until physical probe/panel evidence exists. The pinned
upstream source has no K230 display power-domain provider; an optional local
forward-port SHALL remain isolated and SHALL NOT substitute build proof for
runtime power evidence.

*Grounding: the board panel wiring and init sequence are transcribed from
`nix/dts/k230-tdisplay.dts` and
`nix/dts/display-rm69a10-568x1232.dtsi`. The opt-in DTS is
`nix/dts/k230-tdisplay-mainline-drm.dts`; host compilation and its limits are
recorded in `docs/evidence/mainline-display-dtb.md`. The vendor-derived
local genpd provider, checked probe-time power acquisition, and host build
proof are recorded in `docs/evidence/mainline-display-power-domain.md`, with
prior vendor-board grounding in `docs/evidence/dsi-phy-hang.md`. Later
`docs/evidence/mainline-display/physical-2026-10-01/README.md` commits DRM/fb0
probe and photographed panel boot text. Those observations do not establish
a usable mainline system, successful DCS readback or deliberate touch; the
remaining gate 5b.5 stays open.*

#### Scenario: Someone asks whether the mainline candidate lights the panel

- **WHEN** only host DTS or source/API checks exist
- **THEN** the response says panel probe and illumination are UNVERIFIED and
  does not treat either omitted wiring or a host-built local provider as
  proof that runtime display power works
