## ADDED Requirements

### Requirement: Settings destinations are reachable from the drawer search

*Grounding (2026-10-28/29): injected board runs typed `wifi`, `about` and `ti` and opened Wi-Fi, About and Timer (docs/evidence/drawer-search/board/README.md); the operator reported "drawer search works" on glass (docs/evidence/glass-checklist-2026-10-29/operator-report.md).*
*Grounding: the Settings intents `OpenWifi`, `OpenCellular`, `OpenLocation`, `OpenDateTime`, `OpenAbout`, the Themes and Vision pages and the Do Not Disturb row were read in `nix/rust-shell-client/src/service_ui.rs` and `main.rs` at cff47b1e.*

Every Settings page and inline control that exists SHALL be findable from the drawer search by its label, and a destination whose hardware is absent SHALL NOT be findable. Opening one from search SHALL show the same screen a tap through the shade would, with the row in view for an inline control, and SHALL leave every setting as it was.

#### Scenario: A page destination

- **WHEN** a person finds Date & time in the drawer search and chooses it
- **THEN** the Date & time page opens and Back returns to Settings

#### Scenario: An inline control

- **WHEN** a person finds Brightness in the drawer search and chooses it
- **THEN** Settings opens with the Brightness row visible and the brightness unchanged
