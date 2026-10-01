## MODIFIED Requirements

### Requirement: Apps discovers installed desktop applications

*Grounding: `docs/evidence/shell-features/desktop-launcher/README.md`, its
console, PNGs and camera recording establish physical-panel discovery, launch,
refresh and error recovery using injected input. The user separately confirmed finger usability on 2026-09-22; normal source-image reboot persistence is demonstrated by the separate
image-launcher video and console, without restoring home-directory state.*

<!-- UNVERIFIED: functional launch splash accepted by the operator, docs/evidence/proposal-closeout/2026-10-01/splash.md; prior host/QEMU proofs remain. UNVERIFIED: quantitative one-frame timing and individual physical timeout/failure cases were not newly measured. Additional capture/fault-injection reruns are waived. Shared GNOME activation/menu parity remains the Home proposal's task group 11; this splash closeout does not claim that implementation. -->

The system's Apps surface SHALL list visible application desktop entries from
the user's XDG data directories and Nix profile data directories, applying
user-over-system precedence and desktop visibility rules. Reopening Apps SHALL
reflect entries added or removed since the previous open. The surface SHALL
provide readable application names and touch-accessible pages when the list
exceeds the portrait display. Launching an entry SHALL preserve desktop-entry
argument expansion and working-directory semantics. Terminal applications SHALL
open in the configured terminal. A launch error SHALL leave a visible explanation
and a usable Back control. The application grid SHALL present at least 4
columns of icons at this panel's width, each icon at least 56 logical
pixels square, with a single-line, ellipsized application name below each
icon and no surrounding card or plate. An application with no resolvable
icon SHALL show a round, theme-coloured fallback bearing its initial
letter, rather than leaving the tile blank.

A launch SHALL show the instant splash defined below instead of leaving the
previous app visible during startup. Terminal applications SHALL hand off
the splash correctly despite mapping under the terminal identity. A launch
failure SHALL use the splash's recoverable failure state and a reachable
return to Apps or Home, never an unexplained dead overlay.

#### Scenario: An installed application becomes available

- **WHEN** a visible application desktop entry is installed in a session data
  directory and the user reopens Apps
- **THEN** its name appears in the application list and can be selected by touch

#### Scenario: An application is removed or hidden

- **WHEN** an application entry is removed or hidden by a user override and the
  user reopens Apps
- **THEN** that application is absent from the list

#### Scenario: An application needs a terminal

- **WHEN** the user selects an installed application with Terminal=true
- **THEN** its expanded argument list runs in the readable terminal profile
  with the desktop entry's configured working directory, and the splash
  hands off correctly to that terminal window even though it maps under the
  terminal's own identity, not the launched entry's

#### Scenario: A launch fails

- **WHEN** the selected application cannot be launched, or its spawned
  process exits before any window maps
- **THEN** the splash shows a recoverable failure state naming the app and
  returns the user to Apps or Home, rather than leaving a dead overlay or an
  unexplained, unresponsive previous app

#### Scenario: The application grid presents a dense, legible layout

- **WHEN** the user opens Apps with more entries than fit in one screen
- **THEN** at least 4 columns of icons are visible per row, each icon at
  least 56 logical pixels square with a legible, ellipsized name below it
  and no surrounding card, and the list scrolls to reveal the remainder

#### Scenario: An application with no icon still gets a legible tile

- **WHEN** an installed application's desktop entry names no icon that
  resolves against the active icon theme
- **THEN** its grid tile shows a round, theme-coloured circle bearing the
  application's initial letter, not an empty or broken tile

#### Scenario: Searching uses the same system keyboard as other text fields

- **WHEN** a person focuses the app drawer's Search field
- **THEN** the normal system keyboard appears and its ordinary typed text and correction update the live app filter, with the list kept visible above the keyboard
- **AND** dismissing search, launching a result or leaving the drawer releases keyboard focus and lowers the keyboard without stranding application input

#### Scenario: Search focus and correction remain visible

- **WHEN** a person taps Search and types or presses the system keyboard's Backspace
- **THEN** a visible insertion caret and focus indication identify the active field, correction changes only the query, and the app drawer remains open

<!-- Closeout evidence: docs/evidence/proposal-closeout/2026-10-01/drawer.md. Operator report is physical
feedback; retained host/QEMU/injected evidence keeps its original class.
No additional capture, quantitative measurement or fault injection claimed. -->

### Requirement: Launching an app shows an instant splash until it appears

*Grounding: operator acceptance in `docs/evidence/proposal-closeout/2026-10-01/splash.md`, with prior source and board/QEMU evidence retaining their original classes and limits.*

<!-- UNVERIFIED: functional launch splash accepted by the operator, docs/evidence/proposal-closeout/2026-10-01/splash.md; prior host/QEMU proofs remain. UNVERIFIED: quantitative one-frame timing and individual physical timeout/failure cases were not newly measured. Additional capture/fault-injection reruns are waived. Shared GNOME activation/menu parity remains the Home proposal's task group 11; this splash closeout does not claim that implementation. -->

Tapping an installed application in the drawer, on Home, or in the dock
SHALL show a full-screen splash within one visible frame: the active
theme's background colour, the tapped application's desktop-entry icon
large and centred, and its name below the icon. The previously active
application or overlay SHALL NOT be visible at any point during this
transition, including momentarily. The splash's icon and name SHALL ease in
over roughly 200-250 milliseconds; the backdrop itself SHALL be fully
opaque from its first painted frame regardless of that easing. The splash
SHALL remain shown until the launched application's own window maps, at
which point the shell SHALL hand off to it as an ordinary running
application with no further splash. Matching that window SHALL NOT depend
solely on the launched entry's own identity, since a `Terminal=true` entry's
window maps under its terminal's identity instead.

When a tapped Home or dock entry has an identifiable running instance, the
shell SHALL focus that instance instead of starting a new process, and SHALL show the splash
for no more than one round trip confirming that focus -- never a splash
lasting as long as a genuine cold start.

If no window has mapped after approximately ten seconds, the splash SHALL
show an explicit "taking longer than usual" state offering a way to dismiss
it or return Home, and SHALL remain until the user acts. If the launched
process exits before any window maps, the splash SHALL show that the named
application could not be opened and SHALL dismiss itself shortly after,
without requiring a tap.

#### Scenario: A user taps an app in the drawer

- **WHEN** the user taps an installed application's entry in the drawer
- **THEN** a full-screen splash showing that application's icon and name
  appears within one frame, the previously shown drawer or app is never
  visible afterward, and the splash hands off to the application's own
  window once it maps

#### Scenario: A user taps an app pinned to Home or the dock

- **WHEN** the user taps an application pinned to Home or docked
- **THEN** the same full-screen splash appears at that tap, using the same
  icon and name resolution as the drawer, and hands off the same way once
  the application's window maps

#### Scenario: The tapped app is already running

- **WHEN** a tapped Home or dock application has an identifiable running window
- **THEN** the shell focuses that window directly, and any splash shown is
  no longer than the time needed to confirm that focus, never a splash that
  waits as long as a fresh launch would

#### Scenario: A terminal application's window maps under a different identity

- **WHEN** the tapped application has `Terminal=true` and its window maps
  as the configured terminal rather than under the launched entry's own
  application identity
- **THEN** the splash still recognizes that window as this launch's result,
  by the spawned process or its process tree rather than by application
  identity alone, and hands off correctly

#### Scenario: No window maps in time

- **WHEN** about ten seconds pass with no window mapping for the launch the
  splash is showing
- **THEN** the splash shows a "taking longer than usual" state with a way
  to dismiss it or return Home, and remains visible until the user acts

#### Scenario: The launched process exits before mapping a window

- **WHEN** the spawned process exits without ever mapping a window
- **THEN** the splash shows that the named application could not be opened
  and dismisses itself shortly after, without requiring the user to tap
  anything

#### Scenario: The compositor never shows a stale focused app during launch

- **WHEN** an application is launched from the drawer, which sits above the
  previously focused application
- **THEN** the compositor's existing overlay ordering keeps that previously
  focused application fully covered by the splash for the whole transition,
  with no compositor-side change required to prevent it from showing
  through

<!-- Closeout evidence: docs/evidence/proposal-closeout/2026-10-01/splash.md. Operator report is physical
feedback; retained host/QEMU/injected evidence keeps its original class.
No additional capture, quantitative measurement or fault injection claimed. -->
