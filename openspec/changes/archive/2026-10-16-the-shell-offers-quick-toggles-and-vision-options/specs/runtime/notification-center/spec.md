## ADDED Requirements

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
