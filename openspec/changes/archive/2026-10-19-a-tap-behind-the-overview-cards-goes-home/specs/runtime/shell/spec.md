## ADDED Requirements

### Requirement: A tap behind the Overview cards goes Home

*Grounding: landscape panel captures and filtered journal in
`docs/evidence/overview-backdrop-tap/README.md`, and the operator's
physical glass confirmation in
`docs/evidence/overview-backdrop-tap/operator-signoff.md` (2026-10-19).*
Multi-contact rejection has host policy proof; the physical report covers
backdrop taps and retained apps. The system userspace shell owns this
behavior.

In the card Overview, a tap on the backdrop that is not on a card, the
Close control or the footer SHALL show Home exactly as the footer's Home
tap does, keeping every app window available in Overview. A contact that
moves beyond the tap slop, or that is joined by another contact, SHALL NOT
go Home. Taps on a card SHALL keep opening that card.

#### Scenario: Tapping above the card

- **WHEN** a person taps the Overview backdrop above or beside the centred
  card
- **THEN** Home is shown
- **AND** returning to Overview shows the same open apps

#### Scenario: A drag that starts behind the card

- **WHEN** a person touches the backdrop and drags before lifting
- **THEN** Overview stays open and nothing is launched or closed
