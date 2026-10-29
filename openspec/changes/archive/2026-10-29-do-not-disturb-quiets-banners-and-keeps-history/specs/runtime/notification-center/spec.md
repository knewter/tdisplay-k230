## ADDED Requirements

### Requirement: Do Not Disturb quiets banners and keeps history

*Grounding: the broker's priority classes and delegate cap in `tools/notification_center.py` (`PRIORITIES`, `History.emit`), the Timer's `important` request in `nix/term-apps/k230_term_apps.py` (`timer_expiry_request`), and the absence of any notification sound path in `nix/` and of a speaker or vibration motor on this handheld (`openspec/changes/the-handheld-plays-through-its-speaker`, parked 2026-10-26).*
*Grounding (2026-10-27, board, injected): with Quiet on, an ordinary and a delegated urgent `busctl` notification showed no banner and were listed in history, and a 1-minute Timer's "Timer finished" banner broke through (`docs/evidence/do-not-disturb/board/README.md`). Not observed on glass: the operator waived that check on 2026-10-29 (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`).*
The shell SHALL offer a Do Not Disturb mode. While it is on, the shell SHALL NOT show a banner for a new event, and SHALL still record the event in history, count it, and list it in the shade. A banner SHALL still appear for an event whose broker preview marks it as breaking through, which the broker SHALL do for a critical event and for an important event from a trusted source that is not a delegated app. An event from a delegated app, an SMS, or an unknown sender SHALL NOT break through. A preview that carries no break-through marking SHALL be treated as not breaking through. The mode SHALL NOT change what a banner shows, and SHALL NOT claim to silence any sound or vibration, because this handheld has neither.

#### Scenario: An ordinary event arrives while quiet
- **WHEN** Do Not Disturb is on and an ordinary event arrives
- **THEN** no banner appears, and the event is listed in the shade's history with the count increased

#### Scenario: The Timer finishes while quiet
- **WHEN** Do Not Disturb is on and the Timer posts "Timer finished"
- **THEN** its banner appears as it does with the mode off

#### Scenario: A delegated app asks for urgency while quiet
- **WHEN** Do Not Disturb is on and an app through the desktop notification service sends an urgent notification
- **THEN** no banner appears, and the event is in history

#### Scenario: The mode turns on over a showing banner
- **WHEN** an ordinary banner is showing and the person turns Do Not Disturb on
- **THEN** the banner leaves and its event remains in history

### Requirement: Do Not Disturb persists and is shown

*Grounding: the key-backlight preference pattern in `nix/rust-shell-client/src/keyboard_base.rs` (`PREFERENCE_DIR`, `write_preference`) and `nix/shell.nix` (`systemd.tmpfiles.rules`).*
*Grounding (2026-10-28, board): on build `3vk5qy3a…` Quiet was still on after a reboot, with the moon glyph and "Quiet / On" in the shade (`docs/evidence/do-not-disturb/board/README.md`, task 3.4).*
The choice SHALL be stored in a file under the shell user's own state directory, SHALL survive a reboot and a shell restart, and SHALL default to off when the file is missing or unreadable. While the mode is on, the wide shade's status line SHALL show a moon glyph. Portrait and HDMI shades SHALL offer the switch in Settings.

#### Scenario: Reboot while quiet
- **WHEN** Do Not Disturb is on and the handheld reboots
- **THEN** it is still on when the shell returns, and the shade's status line shows the glyph

#### Scenario: Unreadable preference
- **WHEN** the preference file is missing or unreadable at start
- **THEN** the mode is off and banners appear as usual

### Requirement: The wide shade's tiles stay three across and two deep

*Grounding: the grid geometry in `nix/rust-shell-client/src/service_ui.rs` (`shade_tile_rect`, `shade_wide_slider_top`, `SHADE_TAP_MIN`) as read on 2026-10-27, and the 99 px floor in "Shade tap targets meet the shell's 48dp-equivalent floor".*
*Grounding (2026-10-28, board, injected): at the 200% text step on build `vf91pbq6…`, both sliders lay fully on the 1232x568 panel and no tile word was cut off. The tile words render smaller at 200% so they fit, which the operator accepted on 2026-10-29 (`docs/evidence/do-not-disturb/board/README.md`, task 3.2; `docs/evidence/do-not-disturb/host/README.md`, task 2.3). The shade has since gained a sixth tile, Clock (`openspec/specs/system/power/spec.md`; board captures in `docs/evidence/resting-display-follow-ups/board/`).*
The wide shade's quick tiles SHALL be laid out three to a row in the 480 px controls column, never more than two rows, in the order Wi-Fi, Keyboard, Do Not Disturb, Location, Cellular, with any further tile after them. Every tile SHALL be at least 99 logical px tall, and the brightness and volume sliders SHALL remain wholly on the panel at the largest vision text step. A tile's label and state word SHALL NOT be cut off.

#### Scenario: Largest text step
- **WHEN** the shade opens on the landscape panel at the largest vision text step with the modem present
- **THEN** every tile shows its full label and state word in at most two rows, and both sliders are fully on the panel

#### Scenario: Tap the tile
- **WHEN** a person taps anywhere in the Do Not Disturb tile
- **THEN** the mode flips, the tile shows its new state, and the shade stays open
