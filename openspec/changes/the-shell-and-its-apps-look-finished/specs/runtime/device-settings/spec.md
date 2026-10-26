## ADDED Requirements

### Requirement: Settings reads plainly and scrolls cleanly

*Grounding: the 2026-10-26 design review of native grim captures on the board (`the-shell-and-its-apps-look-finished` design.md).*

<!-- UNVERIFIED: awaits board captures of the fixed build (tasks group 9). -->
Settings SHALL place its Vision and Themes links in the title row. While its body is scrolled, content passing under the section header SHALL meet a divider and a fade, never a bare cut through text. Control values SHALL be words a person uses: the Wi-Fi link SHALL read "Connected" or "Not connected" rather than a raw state, and the motion preference SHALL be titled "Reduce motion". The audio output SHALL show its name without an instruction suffix.

#### Scenario: Scrolled Settings
- **WHEN** Settings is scrolled so a card passes under the "Device controls" header
- **THEN** the card fades out against a divider and no half-cut line of text sits against bare background
