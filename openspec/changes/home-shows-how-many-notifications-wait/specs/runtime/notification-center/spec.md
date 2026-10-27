## ADDED Requirements

### Requirement: A glance outside the shade reveals only a count

*Grounding: the broker's privacy rules for previews in `tools/notification_center.py` (`History.snapshot`, `private`) and the existing "Privacy and interruption have safe defaults" requirement; the shell's rule that a sliding surface declares no opaque region (`runtime/shell`, "A surface that slides SHALL NOT declare an opaque region while it moves").*
<!-- UNVERIFIED: no glance has been drawn or captured; Home's count is built by `home-shows-how-many-notifications-wait` and awaits its board proof. -->
Any indicator of pending notifications shown while the shade is closed SHALL show a number or a dot and nothing else. It SHALL NOT show a source, summary, body, app icon or priority, and SHALL NOT differ between a private and a non-private event. It SHALL be drawn into a surface the shell already owns and SHALL NOT declare an opaque region on a surface that slides.

#### Scenario: A private text arrives
- **WHEN** a received text with private body text is retained and the shade is closed
- **THEN** the indicator reads the same as for any other single event, and no capture of it shows the sender or text

#### Scenario: The indicator sits on a surface that slides
- **WHEN** a frame carrying the indicator is committed while its surface is moving
- **THEN** the frame declares no opaque region because of the indicator
