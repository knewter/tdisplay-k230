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

A person SHALL be able to add or remove an installed application through
its mouse app menu or long-press grab and deliberately drag icons from the drawer to Home or rearrange
them between pages and dock slots. A long-press SHALL grab an icon for movement, not open a menu;
a deliberate drag SHALL preserve direct manipulation without also activating
the app. Rearrangement SHALL provide contextual Done/remove controls, with no
permanent navigation chrome. Pinning an already-pinned app SHALL preserve its
placement rather than duplicate it.

#### Scenario: A person pins an app through its menu

- **WHEN** a person right-clicks a drawer icon and selects Add to Home
- **THEN** the app is pinned once, without launching it or moving an existing pin

#### Scenario: A person moves or removes an icon

- **WHEN** a person deliberately drags a Home icon in rearrange mode
- **THEN** it can move between page/dock slots or to the contextual remove target
- **AND** removing a pin leaves the application installed and reachable in the drawer

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

Tapping or primary-clicking a Home/dock icon outside rearrange mode SHALL
activate its most recently used identifiable window if already running,
or launch it if none is,
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

### Requirement: App icons provide explicit window and desktop actions

<!-- UNVERIFIED: source, host and paired cross checks are implemented; native
board pointer delivery/dismissal and operator hold-and-drag acceptance are
recorded under docs/evidence/home-screen/app-actions/board/. Explicit
New Window/primary-focus operator acceptance remains open in task 11.4. -->

Home/dock and the shared launcher app-icon path SHALL provide the same menu
through secondary click in mouse mode. Long-press SHALL retain the existing
icon-grab/rearrange behavior and SHALL NOT open this menu. The menu SHALL offer named
supported desktop actions and identified running windows; New Window SHALL
bypass primary focus behavior when supported, prefer the desktop entry's
new-window action and not appear twice. Single-window apps SHALL NOT be
promised an unsupported second window. Menu dismissal SHALL preserve layout,
application focus and ordinary pointer/touch ownership.

#### Scenario: Explicitly open another window

- **WHEN** a person opens an app icon's menu and chooses supported New Window
- **THEN** the shell requests a new window through the desktop-entry launch/action path instead of focusing the existing window

#### Scenario: Secondary click opens app actions

- **WHEN** a person right-clicks an icon
- **THEN** its app menu opens without activating, pinning or moving that app

#### Scenario: Long-press remains an icon grab

- **WHEN** a person holds an icon to move it
- **THEN** the existing grab/rearrange flow remains available and no app menu opens

#### Scenario: Deliberate movement remains a drag

- **WHEN** an icon contact deliberately moves beyond drag slop
- **THEN** it takes the supported icon-placement path and cannot also trigger the stationary-hold menu or launch
