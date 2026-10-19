## ADDED Requirements

### Requirement: A tap behind the Overview cards goes Home

<!-- UNVERIFIED: operator glass tap (task 2.2) remains open; injected-pointer board checks are recorded in docs/evidence/overview-backdrop-tap/README.md. -->

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
