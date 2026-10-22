## ADDED Requirements

### Requirement: Compositor repaints for drawer scroll and keyboard motion are measured against the render allowance

UNVERIFIED: the iterations' board measurements are pending.

The shell's compositor SHALL be measured on the installed board during
sustained drawer scroll and keyboard show, hold and hide. The measurement
SHALL use its own benchmark, comparing repaint wall time with the configured
render allowance and presented intervals with the card frame budget. A surface
SHALL declare itself opaque only where its pixels are proven fully opaque.
Debug-level compositor logging SHALL NOT run in the board image.

#### Scenario: Drawer scroll repaint

- **WHEN** the drawer is scrolled with injected native touch while the compositor benchmark is armed
- **THEN** the recorded repaint wall time and presented interval are compared with the 12 ms allowance and the 33.334 ms budget, and a miss is recorded as a miss

#### Scenario: A translucent drawer theme

- **WHEN** the drawer sheet has any translucent pixel
- **THEN** that part of the drawer surface declares no opaque region, and the compositor blends it over the layers beneath
