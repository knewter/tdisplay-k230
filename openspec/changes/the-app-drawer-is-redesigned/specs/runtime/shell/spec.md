## ADDED Requirements

### Requirement: A drawer scroll gesture never converts into a close

*Grounding: `docs/design/app-drawer-review.md` §1 (an earlier revision
of this document) traces the reported bug ("swipe down in the app drawer
to scroll back up, it closes the drawer") to two independent mechanisms
that each decided close-eligibility once, at the start of a touch, and
never revisited it as the gesture actually unfolded. Fixed in
`nix/rust-shell-client/src/navigation.rs` (`Contact::scrolled_away`,
gating `DrawerNavigation::up`'s release-only dismiss check) and
`service_ui.rs` (`drawer_close_candidate_after_scroll`, gating the live
"follow the finger" close drag `main.rs`'s `motion` handler runs on
every sample). Landed in its own commit, separately from the redesign
this change otherwise covers. Regression tests reproduce the exact
gesture: `navigation.rs::scrolling_away_from_the_top_then_reversing_never_closes_within_one_gesture`,
`main.rs::drawer_live_close_drag_never_engages_after_a_mid_gesture_scroll_reversal`.*

A downward drag on the app drawer's grid or its top chrome SHALL close
the drawer only when the grid was at rest at its own scroll top — with
no fling still decelerating toward it — at the moment the finger touched
down. Once a gesture has actually scrolled the grid away from its own
top, that same held gesture SHALL NOT close the drawer for the remainder
of its duration, even if the grid's scroll position later returns to (or
clamps at) its top before the finger releases. After a fling has fully
decelerated to a stop at the top, a new, separate downward drag MAY close
the drawer.

#### Scenario: Scrolling down then reversing within one gesture never closes

- **WHEN** a person, in one continuous touch starting with the grid at its
  own top, drags to scroll down through the list and then, without
  lifting, reverses and drags back down past where the touch began
- **THEN** the grid keeps scrolling for the gesture's entire duration and
  the drawer does not close, regardless of where the gesture ends

#### Scenario: A downward drag from rest at the top still dismisses

- **WHEN** a person drags downward on the drawer's grid or top chrome
  while the grid is already at rest at its own top, with no gesture-borne
  scroll in between
- **THEN** the drawer closes, following the finger

#### Scenario: A fling settles before a new close drag begins

- **WHEN** a scroll fling has fully decelerated to a stop at the grid's
  own top, and the person then begins a new, separate downward drag
- **THEN** that new drag may close the drawer

### Requirement: The app drawer filters its grid by a live search query

*Grounding: `docs/design/app-drawer-review.md` §2.4. Reopens an explicit
prior deferral (`the-handheld-presents-a-coherent-shell/design.md`
decision 2, `shell-ux-critique.md` §4) at the coordinator's direction, on
review of a first redesign attempt that omitted it. Implemented via a
new compact, lowercase-only on-screen keyboard
(`navigation::search_keyboard_key_at`) distinct from the existing WiFi
password entry keyboard (hardcoded to that screen's own full-height
layout, not reusable without a separate refactor) and a plain
case-insensitive substring filter (`service_ui::filter_app_indices`).*

The app drawer SHALL present a tappable search field above its icon
grid. Tapping it SHALL raise an on-screen keyboard and filter the grid,
live, to applications whose name contains the entered text, matched
without regard to letter case. Clearing or leaving the field empty SHALL
restore the full, unfiltered grid. Selecting a filtered result SHALL
launch or pin the same real application selecting it from the
unfiltered grid would have.

#### Scenario: Typing a search query filters the grid live

- **WHEN** a person taps the search field and types characters matching
  part of an installed application's name, in either case
- **THEN** the grid immediately shows only applications whose name
  contains those characters, updating with each keystroke

#### Scenario: A filtered result launches the correct application

- **WHEN** a person taps an application shown while a search query is
  active
- **THEN** the same application that name identifies launches, exactly
  as if it had been tapped in the unfiltered grid

#### Scenario: Clearing the search restores the full grid

- **WHEN** a person clears the search field's text
- **THEN** every installed application reappears in the grid

### Requirement: A cheap per-frame timing signal exists for the app drawer

*Grounding: `docs/design/app-drawer-review.md` §3 measured a real,
previously-uncached per-frame cost (whole-tile repaint on every scroll
tick) and replaced it with a pre-rendered, cached grid bitmap
(`render::DrawerGridCache`) that an ordinary scroll/fling frame reuses
instead of rebuilding, but could not verify the resulting board frame
time without board access — estimated, labeled UNVERIFIED, at
17.3-34.6ms per frame against this repo's own established 20-40x
host-to-board multiplier (`docs/evidence/card-shell/
backdrop-blur-feasibility.md` §3), which straddles a ~20ms target.
`main.rs`'s `draw` now emits a rate-limited `K230_DRAWER_FRAME ms=…` log
line so this estimate can be replaced with a real board measurement
without a `K230_TRACE_PATH` capture session.*

Whenever the app drawer route renders a frame, the system SHALL be able
to report that frame's render duration in milliseconds through the
shell's existing log/journal output, at a bounded rate that does not
flood the journal during a sustained scroll or fling.

#### Scenario: An operator reads drawer frame cost from the journal

- **WHEN** an operator scrolls the app drawer on the board and reads the
  shell process's own journal/log output
- **THEN** a `K230_DRAWER_FRAME ms=` line appears at least once every few
  hundred milliseconds of sustained scrolling, reporting that frame's own
  render duration

## MODIFIED Requirements

### Requirement: Apps discovers installed desktop applications

*Grounding: `docs/evidence/shell-features/desktop-launcher/README.md`, its
console, PNGs and camera recording establish physical-panel discovery, launch,
refresh and error recovery using injected input. The user separately confirmed finger usability on 2026-09-22; normal source-image reboot persistence is demonstrated by the separate
image-launcher video and console, without restoring home-directory state.
Grid presentation added by this change: `docs/design/
app-drawer-review.md` §2, `nix/rust-shell-client/src/navigation.rs`
(`COLUMNS = 4`, `ROW_HEIGHT = 110.0`) and `render.rs`
(`paint_drawer_tile`: a plain icon and label, no card/plate; a round,
theme-tinted circle-with-initial icon fallback), host-rendered
before/after evidence at `docs/evidence/app-drawer/`. Not yet confirmed
on the physical panel or by a real finger — see that evidence
directory's own limits section.*

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
  with the desktop entry's configured working directory

#### Scenario: A launch fails

- **WHEN** the selected application cannot be launched
- **THEN** the launcher reports the failure and lets the user return or choose
  another action without a physical keyboard

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
