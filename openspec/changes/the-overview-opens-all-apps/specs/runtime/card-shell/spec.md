## ADDED Requirements

### Requirement: The overview offers a way to All apps

*Grounding: board, injected touch, 2026-10-27 (docs/evidence/overview-all-apps/README.md).*

The card overview SHALL show an "All apps ›" label at the right of its title row. A tap on it that misses every card SHALL return Home and then open the app drawer. Its target SHALL be at least 99 px tall and SHALL NOT take a tap that lands on a card.

#### Scenario: Starting a new app from the overview

- **WHEN** a person in the overview taps "All apps ›"
- **THEN** the overview settles to Home and the app drawer opens

#### Scenario: A card under the title row

- **WHEN** a tap lands on a card
- **THEN** the card takes the tap and the drawer does not open
