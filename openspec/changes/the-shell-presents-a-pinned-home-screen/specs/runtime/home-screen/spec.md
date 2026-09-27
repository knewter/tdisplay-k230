## Purpose

Defines the handheld's pinned-icon Home: the paged icon grid and quick-launch
dock a person sees whenever no application owns the panel, its pin/unpin/
rearrange interactions, its fresh-install defaults and persistence, and its
place in the shell's gesture topology alongside the existing card overview
and drawer.

## ADDED Requirements

### Requirement: Home presents pinned app icons across swipeable pages

<!-- UNVERIFIED: implemented and host/QEMU-tested in this change; no
real-finger or daylight-readability board observation exists yet. -->

Whenever no application is focused and the card overview is not active, the
shell SHALL present Home: the current theme wallpaper with a grid of
touch-sized pinned application icons, arranged across one or more
horizontally swipeable pages. A page swipe SHALL track the finger 1:1, apply
momentum on release, and settle to the nearest whole page with an ease-out
motion. When more than one page exists, Home SHALL show a row of page-count
indicator dots that are visual indicators only and never a tappable control.

#### Scenario: A person swipes between Home pages

- **WHEN** Home holds more icons than fit on one page and a person drags
  horizontally across the grid
- **THEN** the page follows the finger 1:1 during the drag and settles onto
  the nearest whole page on release, matching whichever page-count dot is lit

#### Scenario: A fast flick advances more than the dragged distance

- **WHEN** a person flicks quickly and releases before the drag alone would
  cross a page boundary
- **THEN** momentum carries the page to the next page and it settles there,
  the same coast-then-settle behavior the existing theme carousel and drawer
  scrolling already use elsewhere in this shell

#### Scenario: A slow release settles immediately

- **WHEN** a person drags partway across a page and releases with
  negligible velocity
- **THEN** the page settles immediately to whichever page it is nearest,
  without coasting past it

### Requirement: A persistent quick-launch dock spans every Home page

<!-- UNVERIFIED: implemented and host/QEMU-tested in this change; no
real-finger board observation exists yet. -->

Home SHALL show a fixed-position quick-launch dock beneath the icon grid,
holding a bounded number of pinned icons that do not move or scroll when the
grid pages change.

#### Scenario: The dock stays put while pages change

- **WHEN** a person swipes between Home pages
- **THEN** the dock's icons remain in the same screen position and selection
  throughout the swipe and after it settles

### Requirement: Apps can be pinned to, unpinned from, and rearranged on Home

<!-- UNVERIFIED: implemented and host-tested in this change; no real-finger
board observation exists yet. -->

A person SHALL be able to add an installed application to Home by long-
pressing its entry in the drawer, without a further confirmation step. A
person SHALL be able to long-press an icon already on Home to enter a
rearrange mode in which that icon, or any other pinned icon, can be dragged
within a page, across a page boundary, into or out of the dock, or off Home
entirely (unpinning it, without uninstalling it). Rearrange mode SHALL end
when a person taps empty space or a visible "Done" affordance, and SHALL NOT
persist as permanent on-screen chrome. Long-pressing an application already
pinned to Home from the drawer SHALL leave its existing placement unchanged
rather than duplicating or moving it.

#### Scenario: A person pins an app from the drawer

- **WHEN** a person long-presses an installed application's tile in the
  drawer
- **THEN** that application's icon appears on a Home page with a free grid
  slot, creating a new page if every existing page is full

#### Scenario: A person removes an app from Home

- **WHEN** a person long-presses a Home icon, enters rearrange mode, and
  drags it to the remove target
- **THEN** the icon leaves Home, the application remains installed and still
  reachable from the drawer, and rearrange mode's remove target is not shown
  outside that mode

#### Scenario: A person moves an icon to a different page

- **WHEN** a person is in rearrange mode and drags an icon to the pager's
  edge and holds it there
- **THEN** the grid pages to the neighboring page and the drag continues,
  letting the icon be dropped on the new page

### Requirement: A fresh Home seeds sensible defaults from installed desktop entries

<!-- Grounding: `nix/rust-shell-client/src/catalog.rs`'s `installed_apps()`
is the existing, already-shipped desktop-entry discovery this requirement
reuses rather than reimplementing; the specific curated id list is new to
this change and is UNVERIFIED against a real fresh-install image. -->

When no saved Home layout exists, the shell SHALL seed Home from the
installed desktop-entry catalog with a curated default set (a terminal, a
file manager, a text editor, a system monitor, a video player, and Settings),
omitting any entry not present on the running image rather than showing a
placeholder for it, and SHALL persist the seeded layout immediately so a
later boot is stable even if the catalog subsequently changes.

#### Scenario: First boot on a fresh image

- **WHEN** the shell starts with no previously saved Home state
- **THEN** Home shows the curated default applications that are actually
  installed on that image, arranged on its first page, and a saved layout
  file now exists

#### Scenario: A default entry is missing from the image

- **WHEN** one of the curated default applications (for example, a video
  player) is not installed on the running image
- **THEN** Home's fresh-seed omits it entirely rather than showing a broken
  or placeholder icon

### Requirement: Home's layout persists across restarts and reboots

<!-- UNVERIFIED: implemented and host-tested in this change; no reboot
observation on the physical board exists yet. -->

Every pin, unpin, rearrange, and page assignment SHALL be written to a
layout file under the shell user's XDG state directory, and SHALL be read
back and reproduced exactly on the next start of the shell, including after a
reboot. An application that was pinned and has since been uninstalled SHALL
keep its grid position empty rather than shifting later icons into it, so
reinstalling the same application restores its place.

#### Scenario: A rearranged layout survives a restart

- **WHEN** a person pins, unpins, or rearranges Home icons and the shell
  process is later restarted
- **THEN** Home reappears with the exact same page contents, dock contents,
  and page order as before the restart

#### Scenario: An uninstalled app's slot is preserved

- **WHEN** an application pinned to Home is uninstalled and later
  reinstalled, with no other Home change in between
- **THEN** its icon reappears in the same grid position it occupied before
  removal

### Requirement: Tapping a Home icon launches the app or focuses it if already running

<!-- UNVERIFIED: the running-window match is a best-effort desktop-entry-id
to app_id heuristic (see `design.md` decision 6); no verified stable mapping
or board multi-window trial exists yet. A miss always falls back to the
existing, already-correct launch path in `nix/rust-shell-client/src/main.rs`
(`launch_selected`), so this requirement cannot regress today's launch
behavior even when the heuristic does not match. -->

Tapping a Home icon outside rearrange mode SHALL bring that application to
the front if an instance of it is already running, or launch it if none is,
using the same desktop-entry argument expansion and working-directory
semantics the drawer already applies.

#### Scenario: Tapping a not-yet-running app's icon

- **WHEN** a person taps a Home icon for an application with no running
  instance
- **THEN** the application launches, the same as tapping it in the drawer

#### Scenario: Tapping an already-running app's icon

- **WHEN** a person taps a Home icon for an application that is already
  running and its window can be identified
- **THEN** that existing window is focused instead of a second instance
  being started

### Requirement: Home's gesture topology is reconciled with the card overview and drawer

<!-- UNVERIFIED: real-finger acceptance remains open. The paired QEMU and
physical-board injected-touch trials pass; see
docs/evidence/home-screen/navigation/README.md. -->

A bottom-edge swipe from a running application SHALL open Overview. An
upward swipe beginning in Overview's bottom navigation area SHALL reveal
Home without closing, unmapping or moving running apps. Swiping up from
Home's bottom edge SHALL open All apps. Swiping a card itself upward SHALL
retain the existing close-card action. Home selection SHALL end when an
existing app is focused or a new app is launched. Navigation SHALL track
contact displacement and settle smoothly after release or cancellation.

#### Scenario: Overview reveals Home while apps keep running

- **WHEN** a person swipes upward from Overview's bottom navigation area
- **THEN** Home appears with its wallpaper, icons and dock
- **AND** all previously running apps retain their window identities
- **AND** the same contact does not also open All apps

#### Scenario: Home opens All apps

- **WHEN** a person begins a new upward swipe from Home's bottom edge
- **THEN** the existing All apps drawer follows the contact and opens

#### Scenario: Returning to a running app

- **WHEN** a person selects an identifiable running app from Home
- **THEN** its existing window becomes visible and focused without a new instance

#### Scenario: A short or cancelled Overview-to-Home swipe

- **WHEN** an upward navigation swipe reverses, is too short, or is cancelled
  by an additional contact
- **THEN** Overview settles back with its apps intact and no app receives a
  partial touch sequence

#### Scenario: Card gestures remain distinct

- **WHEN** an upward gesture begins on an app card rather than the bottom
  navigation area
- **THEN** the existing close-card gesture applies to that card only
