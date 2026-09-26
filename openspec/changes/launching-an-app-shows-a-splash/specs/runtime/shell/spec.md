## MODIFIED Requirements

### Requirement: Apps discovers installed desktop applications

*Grounding: `docs/evidence/shell-features/desktop-launcher/README.md`, its
console, PNGs and camera recording establish physical-panel discovery, launch,
refresh and error recovery using injected input. The user separately confirmed finger usability on 2026-09-22; normal source-image reboot persistence is demonstrated by the separate
image-launcher video and console, without restoring home-directory state.*

<!-- UNVERIFIED: the splash itself (see the new "Launching an app shows an
instant splash until it appears" requirement) is proven on host and,
if practical, under QEMU; real-glass splash timing and readability remain
open board tasks. -->

The system's Apps surface SHALL list visible application desktop entries from
the user's XDG data directories and Nix profile data directories, applying
user-over-system precedence and desktop visibility rules. Reopening Apps SHALL
reflect entries added or removed since the previous open. The surface SHALL
provide readable application names and touch-accessible pages when the list
exceeds the portrait display. Launching an entry SHALL preserve desktop-entry
argument expansion and working-directory semantics, and SHALL show the
instant launch splash defined below rather than leaving the previously
active app visible while the process starts. Terminal applications SHALL
open in the configured terminal. A launch failure SHALL be shown through
that same splash's recoverable failure state, with a way back to Apps or
Home; it SHALL NOT silently leave the previous app in an unexplained,
unresponsive state.

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

## ADDED Requirements

### Requirement: Launching an app shows an instant splash until it appears

<!-- UNVERIFIED: host build, `cargo test`/`cargo clippy`, and a full system
closure build are recorded for this requirement; real-glass timing,
readability, and touch-dismiss feel remain open board tasks. -->

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

When the tapped entry already has a running instance, the shell SHALL focus
that instance instead of starting a new process, and SHALL show the splash
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

- **WHEN** the tapped application already has a running window
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
