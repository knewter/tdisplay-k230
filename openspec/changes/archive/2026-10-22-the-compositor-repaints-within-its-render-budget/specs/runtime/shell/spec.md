## ADDED Requirements

### Requirement: Compositor repaints for drawer scroll and keyboard motion are measured against the render allowance

*Grounding (2026-10-22): `docs/evidence/interaction-jank/compositor-repaint/README.md`.
Injected native touch on the board, build `g2yjvzv4`, test-activated and then
on an ordinary boot as the boot default. Drawer: sway repaint 10.2–10.3 ms
median, presented interval 21 ms median. Keyboard show, hold and hide contact:
19.2 ms. Keyboard show settle missed at 38.3 ms. sway ran `SCHED_RR` 1.*

The shell's compositor SHALL be measured on the installed board during
sustained drawer scroll and keyboard show, hold and hide. The measurement
SHALL use its own benchmark, comparing repaint wall time with the configured
render allowance and presented intervals with the card frame budget.
Debug-level compositor logging SHALL NOT run in the board image. The
compositor SHALL be allowed the minimum realtime round-robin priority it
requests, and the clients it starts SHALL run with ordinary scheduling. A
surface that slides SHALL NOT declare an opaque region while it moves.

#### Scenario: Drawer scroll repaint

- **WHEN** the drawer is scrolled with injected native touch while the compositor benchmark is armed
- **THEN** the recorded repaint wall time and presented interval are compared with the 12 ms allowance and the 33.334 ms budget, and a miss is recorded as a miss

#### Scenario: The compositor's scheduling on the board

- **WHEN** the shell has started on the board
- **THEN** sway runs `SCHED_RR` at priority 1, and `swaybg` and `foot` started by sway run `SCHED_OTHER`

#### Scenario: The keyboard slides

- **WHEN** the on-screen keyboard is shown, held mid-motion or hidden
- **THEN** it declares no opaque region, and the compositor blends it over the surfaces beneath
