## ADDED Requirements

### Requirement: Settings offers a Do Not Disturb switch

*Grounding: the preference sits beside Reduce motion and Key backlight as a one-setting row (`docs/design/shell-ux-review-webos-firefoxos-2026-10.md`, gap 12); no board observation of this row exists.*
<!-- UNVERIFIED: the row has not been built or seen on the board. -->
Settings SHALL list a Do Not Disturb row with an on and off switch whose hit region meets the shell's 99 px floor. It SHALL read and write the same preference as the shade tile, so the two cannot disagree.

#### Scenario: Toggle from Settings
- **WHEN** a person turns the row on in Settings and then opens the shade on the landscape panel
- **THEN** the Do Not Disturb tile shows On and the status line shows the moon glyph
