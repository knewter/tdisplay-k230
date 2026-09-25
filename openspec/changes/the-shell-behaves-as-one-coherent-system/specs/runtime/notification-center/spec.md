## ADDED Requirements

### Requirement: The shade offers quick-toggle controls without a trip into Settings

<!-- UNVERIFIED: planning only; no implementation, host render, or board
observation exists yet. Grounding for the gap being closed:
nix/rust-shell-client/src/service_ui.rs:279-320 (`panel_intent`'s
`Route::Shade` arm, read directly against origin/master 80817e3d) recognizes
only notification scroll, a per-notification action tap, `OpenSettings`,
`NotificationDismissAll`, and its own swipe-to-close — no capability toggle.
`ServiceRequest::Brightness` and `ServiceRequest::KeyboardToggle` exist and
are already wired end-to-end, but only from inside `Route::Settings`
(service_ui.rs:353-370). -->

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

<!-- UNVERIFIED: planning only; no implementation, host render, or board
observation exists yet. Grounding: this panel is 568x1232 logical px at 1
logical px : 1 panel px (docs/design/handheld-shell/README.md) over a 4.1in
diagonal, giving ~330.9 ppi and ~2.07 physical px per Android dp; 46dp is
therefore ~99 logical px on this panel. nix/rust-shell-client/src/
service_ui.rs:305-310's "Dismiss all" hit region
((116.0..190.0).contains(&end.1) && end.0 > w-150.0) is 74 logical px tall
(~36dp), read directly against origin/master 80817e3d. -->

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
