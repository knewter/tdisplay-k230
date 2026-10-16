## ADDED Requirements

### Requirement: A multi-cell widget responds anywhere inside its painted area

*Grounding: reproduced on the host from the board's saved layout at 1280x800
(`HomeScreen::filled_slot_at` regression test). On-board behaviour is
<!-- UNVERIFIED --> until task 2.1 is recorded.*

A press, long press or secondary click anywhere inside the rectangle where Home
paints a multi-cell widget SHALL resolve to that widget, including points that
fall in the gaps between the widget's grid cells. Single-cell icons SHALL keep
their tile-only hit area, so the gaps between separate icons stay inert.

#### Scenario: Long press in a gap inside a widget

- **WHEN** the operator presses and holds at a point inside a 4x2 widget's
  painted area that lies in the gap between two of its cells
- **THEN** Home enters rearrange mode and picks up that widget

#### Scenario: Gap between two icons

- **WHEN** the operator taps the gap between two separate app icons
- **THEN** no icon opens
