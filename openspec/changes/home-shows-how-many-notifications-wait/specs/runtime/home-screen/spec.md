## ADDED Requirements

### Requirement: Home shows how many notifications wait

*Grounding: the client's existing broker poll and `NotificationSnapshot::count` in `nix/rust-shell-client/src/main.rs` and `service_data.rs`; Home's lack of any notification state in `nix/rust-shell-client/src/home_screen.rs`; the shell's rule against permanent controls in `runtime/shell`.*
<!-- UNVERIFIED: no count has been drawn on Home or seen on the board; its placement, legibility and non-interference with paging and the shade pull are decided by tasks 1.3a and 2.1 to 2.4. -->
Home SHALL show the number of notifications the broker holds while that number is above zero, in its top-right corner, as text painted into Home's own surface. The number SHALL equal the count the shade's list heading states, SHALL read `99+` above 99, and SHALL NOT be drawn at zero. It SHALL NOT be a touch target, SHALL NOT cover an icon, widget or dock cell, and SHALL NOT create a surface of its own. It SHALL update within about two seconds of the broker's count changing.

#### Scenario: Events wait while Home is showing
- **WHEN** three events are retained and Home is showing with the shade closed
- **THEN** Home shows 3 in its top-right corner

#### Scenario: Everything is dismissed
- **WHEN** the person dismisses every dismissible event
- **THEN** the count leaves Home, unless an ongoing critical event remains, in which case it shows 1

#### Scenario: Pull down from the count
- **WHEN** a person pulls down from the top edge at the count
- **THEN** the shade opens as it does elsewhere on the edge, and the count is not tapped
