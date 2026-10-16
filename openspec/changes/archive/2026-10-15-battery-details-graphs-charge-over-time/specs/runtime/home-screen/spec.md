## ADDED Requirements

### Requirement: Battery - Details graphs the charge over the last 12 hours

*Grounding: requested by the operator on 2026-10-15 after the widget showed
live discharge figures on the board. Host renders and board captures are
<!-- UNVERIFIED --> until recorded under
`docs/evidence/battery-details-widget/history/`.*

The shell SHALL record the battery percentage and whether the battery was
charging about once a minute while it runs, and immediately when the charging
state changes, to a per-user history file beside the Home layout. Recording
SHALL happen whether or not a Battery - Details widget is placed. The file
SHALL keep at least the last 24 hours, SHALL survive shell restarts and
reboots, and SHALL be pruned so it does not grow without bound. The Battery -
Details widget SHALL draw the last 12 hours of recorded percentage as a line
graph from 0 to 100 percent. Charging spans SHALL be visually distinct from
discharging spans, and spans with no samples for more than 5 minutes SHALL be
shown as gaps rather than joined.

#### Scenario: History survives a reboot

- **WHEN** the shell recorded samples, the board reboots and the shell starts
  again
- **THEN** the widget's graph still shows the earlier samples, with a gap for
  the time the shell was not running

#### Scenario: Discharge then charge

- **WHEN** the history holds a discharge from 90 to 40 percent followed by a
  charge back to 70 percent
- **THEN** the graph falls and then rises, with the charging part drawn in the
  charging style

#### Scenario: Bad or future samples

- **WHEN** the history file has an unparsable line or a sample dated after the
  current time
- **THEN** those samples are ignored and the rest of the graph still draws

#### Scenario: No history yet

- **WHEN** the history has fewer than two samples in the window
- **THEN** the widget shows its other metrics without a graph line
