# runtime/notification-center Specification

## Purpose
Defines a bounded, privacy-aware way for the handheld shell to preview, revisit, act on, and dismiss system and application notifications.

## Requirements

### Requirement: Preview and history share one event state

*Grounding: operator acceptance and explicit additional-proof waiver in `docs/evidence/coherent-shell/operator-closeout-2026-10-10/README.md`; prior host/QEMU/board evidence retains its original provenance. This is acceptance of the installed result, not a newly recorded individual-case test or timing measurement.*
<!-- UNVERIFIED: operator acceptance and the proof waiver do not supply a new individual-case physical confirmation/failure/focus/priority recording. Existing implementation and host/QEMU results keep their original limits. -->
The shell userspace SHALL show a brief preview for an eligible new event and retain it in a reachable history until dismissal or expiry. The top-edge shade SHALL expose Notifications and indicate pending events; a preview SHALL open its event when tapped. The history SHALL show source, time, readable summary, and whether an action remains available; a trusted known app MAY show its resolved desktop-entry icon beside its text name, while unknown or privacy-redacted sources SHALL use a neutral icon and label. Dismissing a preview SHALL NOT silently erase history.

#### Scenario: Preview times out
- **WHEN** a non-urgent preview times out without interaction
- **THEN** the preview leaves the active surface and its event remains reachable in history

#### Scenario: History is empty
- **WHEN** the person opens Notifications with no retained events
- **THEN** it shows an empty message and the shade can be dismissed back to the prior scene

#### Scenario: Scroll through history
- **WHEN** the person drags or flicks a longer notification history
- **THEN** the list follows the finger, coasts within its content bounds, and can be stopped by a new touch without opening an entry

### Requirement: Actions and dismissal are explicit

*Grounding: operator acceptance and explicit additional-proof waiver in `docs/evidence/coherent-shell/operator-closeout-2026-10-10/README.md`; prior host/QEMU/board evidence retains its original provenance. This is acceptance of the installed result, not a newly recorded individual-case test or timing measurement.*
<!-- UNVERIFIED: operator acceptance and the proof waiver do not supply a new individual-case physical confirmation/failure/focus/priority recording. Existing implementation and host/QEMU results keep their original limits. -->
The shell userspace SHALL offer only actions whose target is currently available and SHALL distinguish opening an event from dismissing it. A failed action SHALL leave the event reachable with a short error and Retry or contextual dismissal route. Dismiss All SHALL require a clearly labeled control and SHALL NOT dismiss an ongoing critical system event.

#### Scenario: Target app is gone
- **WHEN** a person selects an event whose action target has exited
- **THEN** the shell reports the unavailable target and keeps the event until the person dismisses it

#### Scenario: Swipe an event sideways
- **WHEN** the person swipes a dismissible history item sideways
- **THEN** the item follows the finger and exposes a Dismiss cue; a short or reversed swipe returns it without dismissal, while a completed swipe removes only that event from history

### Requirement: Privacy and interruption have safe defaults

*Grounding: operator acceptance and explicit additional-proof waiver in `docs/evidence/coherent-shell/operator-closeout-2026-10-10/README.md`; prior host/QEMU/board evidence retains its original provenance. This is acceptance of the installed result, not a newly recorded individual-case test or timing measurement.*
<!-- UNVERIFIED: operator acceptance and the proof waiver do not supply a new individual-case physical confirmation/failure/focus/priority recording. Existing implementation and host/QEMU results keep their original limits. -->
The shell userspace SHALL hide sensitive body text in unsolicited previews by default, showing a neutral source and summary until the person opens history. It SHALL distinguish ordinary, important, and critical events: ordinary previews SHALL not take keyboard focus; important previews SHALL remain non-modal; critical events SHALL explain the immediate condition and preserve a visible recovery route. Unknown senders SHALL use ordinary priority with a hidden body.

#### Scenario: Typing during ordinary event
- **WHEN** an ordinary notification arrives while the person types
- **THEN** input focus stays in the app and the preview does not cover the focused input or keyboard region

#### Scenario: Unknown event source
- **WHEN** an event with no trusted source metadata arrives
- **THEN** its preview omits private body text and app-specific icon, and its history entry identifies the source as unknown

### Requirement: The shade offers quick-toggle controls without a trip into Settings

*Grounding (2026-10-16): host tests in `service_ui.rs` cover the keyboard
row's hit region and its unavailable state (tasks B.1–B.3). On the board, with
injected pointer events on HDMI at 1280x800, the toggle was reachable, showed
and hid the keyboard with the Shade staying open, and showed "Unavailable"
and ignored a tap once wvkbd was stopped
(`docs/evidence/coherent-shell/shade-quick-toggles/README.md`). Brightness is
the existing Shade slider. Real-finger use and the DSI panel orientation were
not exercised.*

The notification shade SHALL offer at least a brightness-step control and a
keyboard show/hide toggle directly in the shade, without requiring
navigation into Settings, reusing the same `ControlState`/`ControlValue`
and `ServiceRequest` types Settings' own rows already send so the two
surfaces cannot disagree about a capability's live state. An unavailable
capability SHALL render the same unavailable/read-only treatment the
Settings row for that capability already uses, not a silently missing
control.

#### Scenario: A person adjusts brightness from the shade

- **WHEN** a person opens the notification shade and taps the brightness
  quick-toggle
- **THEN** brightness changes the same way it would from Settings, without
  the shade closing or navigating to Settings first

#### Scenario: A person shows the keyboard from the shade

- **WHEN** a person taps the keyboard quick-toggle in the shade
- **THEN** the on-screen keyboard shows or hides exactly as the equivalent
  Settings control would, and the shade's own notification list, dismiss-all,
  and Settings-entry regions remain reachable and unaffected

#### Scenario: A capability is unavailable

- **WHEN** a capability's `ControlState` is unavailable or read-only
- **THEN** the shade's quick-toggle for it shows the same unavailable/
  read-only treatment as the matching Settings row, not an interactive
  control that silently does nothing

### Requirement: Shade tap targets meet the shell's 48dp-equivalent floor

*Grounding (2026-10-16): task B.5 gave every Shade tap target, including
"Dismiss all", a hit region of at least 99 logical px, with a unit test that
asserts each region's height (`service_ui.rs`). Host-tested only; no
real-finger measurement.*

Every shade tap target, including "Dismiss all", SHALL meet or exceed a
48dp-equivalent hit region on this panel's measured density (~99 logical
px), independent of how much smaller its visible label is, consistent with
`runtime/handheld-shell-design`'s existing "Shared portrait shell language"
requirement's own stated target once that target is corrected to the same
48dp-equivalent value (see this change's companion critique,
`docs/design/shell-ux-critique.md` §7, for the arithmetic showing the
currently-stated "56 logical px" floor is only ~27dp, not "comfortably
above" 48dp as that requirement's own text currently assumes).

#### Scenario: A person taps near "Dismiss all"

- **WHEN** a person taps anywhere within a 48dp-equivalent (~99 logical px)
  region around the "Dismiss all" control
- **THEN** the dismiss-all action fires, rather than requiring a tap
  precisely within the current, narrower 74px-tall hit region

### Requirement: The shade states each fact once

*Grounding: the 2026-10-26 design review of native grim captures on the board (`the-shell-and-its-apps-look-finished` design.md); fixed-build captures in `docs/evidence/shell-design-review/README.md`.*

*Grounding (2026-10-29, wide layout): board grim captures with injected touch in `docs/evidence/shade-pass/board/`, the operator's glass check of build `37g1magg…` on 2026-10-29 (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`), and an ordinary boot of `2867v7pm…` (`docs/evidence/shade-pass/board/ordinary-boot/README.md`).*

<!-- Grounding: injected-touch grim captures in docs/evidence/shell-design-review/README.md, and the operator's on-glass acceptance of build 1r8zfd5s on 2026-10-26 (docs/evidence/shell-design-review/operator-report.md). -->
The shade SHALL draw its notification count only when there is at least one notification, SHALL centre its empty state in the list column, and SHALL format battery state as "<percent>% · <state>". The keyboard tile SHALL describe its action rather than repeat its title. On the wide (landscape) layout, the controls column SHALL lead with the time and date, then one status line, then quick tiles for Wi-Fi and Keyboard, plus Location and Cellular once the modem has answered, then the brightness and volume sliders. The "Notifications" heading SHALL title the list column.

#### Scenario: Empty shade
- **WHEN** the shade opens with no notifications
- **THEN** it shows one empty-state message, centred in the list column, and no "0 notifications" line

#### Scenario: Landscape shade at a glance
- **WHEN** the shade opens on the landscape panel
- **THEN** the time and date head the left column, "Notifications" heads the list, and Wi-Fi and Keyboard are one tap away as tiles

### Requirement: A glance outside the shade reveals only a count

*Grounding: the broker's privacy rules for previews in `tools/notification_center.py` (`History.snapshot`, `private`) and the existing "Privacy and interruption have safe defaults" requirement; the shell's rule that a sliding surface declares no opaque region (`runtime/shell`, "A surface that slides SHALL NOT declare an opaque region while it moves").*
*Grounding (board, 2026-10-27): Home's count from a private event showed only the integer, with no source or text, in a native capture (docs/evidence/home-notification-count/board/README.md).*
Any indicator of pending notifications shown while the shade is closed SHALL show a number or a dot and nothing else. It SHALL NOT show a source, summary, body, app icon or priority, and SHALL NOT differ between a private and a non-private event. It SHALL be drawn into a surface the shell already owns and SHALL NOT declare an opaque region on a surface that slides.

#### Scenario: A private text arrives
- **WHEN** a received text with private body text is retained and the shade is closed
- **THEN** the indicator reads the same as for any other single event, and no capture of it shows the sender or text

#### Scenario: The indicator sits on a surface that slides
- **WHEN** a frame carrying the indicator is committed while its surface is moving
- **THEN** the frame declares no opaque region because of the indicator

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
