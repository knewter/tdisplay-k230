# runtime/home-screen Specification

## Purpose
Define the touch-operated Home layout: exact app and widget placement, paged rearrangement, folders in the grid and dock, system-keyboard naming, and theme-aware clock, weather and battery widgets.

## Requirements

### Requirement: Home items can be dragged to a specific place instead of instant-pinned

*Grounding: docs/evidence/home-widgets-folders/closeout-2026-10-01/board/README.md and sibling paired QEMU reports; operator acceptance plus delegated board uinput proof, not new finger measurements. Additional committed native board evidence: docs/evidence/home-widgets-folders/closeout-2026-10-01/board/README.md and docs/evidence/home-widget-design/closeout-2026-10-01/board/README.md.*

Long-pressing an installed application's tile in the drawer SHALL lift that
application's icon to follow the finger instead of pinning it immediately,
and Home SHALL be revealed underneath while the drag is live. Releasing
over an empty grid cell or dock slot SHALL place the item there. Releasing
over an already-pinned application SHALL create a new folder containing
both. Releasing over an existing folder SHALL add the item to it.
Releasing over a Cancel target, or over the area the drawer's own chrome
occupied before the drag began, SHALL abandon the drag with no change to
Home. Holding the dragged item near the panel's left or right edge for
about 500ms SHALL turn Home to the neighboring page, or add a new page when
held past the last one.

#### Scenario: Dragging a drawer app onto an empty cell places it there

- **WHEN** a person long-presses a drawer application and releases over an
  empty Home grid cell
- **THEN** that application's icon appears in exactly that cell

#### Scenario: Dragging a drawer app onto another app creates a folder

- **WHEN** a person drags a drawer application and releases it directly on
  an application already pinned to Home
- **THEN** a folder now occupies that cell, containing both applications

#### Scenario: Dragging onto an existing folder joins it

- **WHEN** a person releases a dragged application directly on a folder
  already on Home or in the dock
- **THEN** that application becomes a member of the existing folder rather
  than creating a nested folder

#### Scenario: Cancelling a drag changes nothing

- **WHEN** a person releases a dragged drawer application over the Cancel
  target
- **THEN** Home's layout is exactly as it was before the drag began

#### Scenario: Holding at the edge turns the page mid-drag

- **WHEN** a person holds a dragged item within the edge zone for about
  500ms
- **THEN** Home turns to the neighboring page (or adds a new one past the
  last page) and the drag continues on the new page

### Requirement: Rearranging a pinned item on Home follows the same drop rules as a drawer drag

*Grounding: docs/evidence/home-widgets-folders/closeout-2026-10-01/board/README.md and sibling paired QEMU reports; operator acceptance plus delegated board uinput proof, not new finger measurements. Additional committed native board evidence: docs/evidence/home-widgets-folders/closeout-2026-10-01/board/README.md and docs/evidence/home-widget-design/closeout-2026-10-01/board/README.md.*

Long-pressing an item already on Home (an application, a folder, or a
widget) SHALL enter the same drag as a drawer-originated one, resolved by
the same cell/folder/dock/edge-page-switch rules, plus a Remove target that
unpins the dragged item from Home without uninstalling it. A page left
with nothing pinned to it after a move SHALL be removed automatically,
except that Home always keeps at least one page even when it is empty.

#### Scenario: Rearranging into an empty cell moves the item

- **WHEN** a person drags a pinned application to an empty cell on a
  different page
- **THEN** the application now occupies that cell and its former cell is
  empty

#### Scenario: Dragging one pinned app onto another creates a folder

- **WHEN** a person drags a pinned application directly onto another pinned
  application
- **THEN** a folder now occupies the target cell, containing both, and the
  application's former cell is empty

#### Scenario: An emptied page disappears

- **WHEN** a person's last move off a page leaves it with nothing pinned
- **THEN** that page no longer appears among Home's pages

#### Scenario: Dragging a widget moves the whole widget

- **WHEN** a person long-presses any cell within a multi-cell widget's span
  and drags it
- **THEN** the entire widget moves as one unit to wherever it is dropped,
  if its full span fits there

### Requirement: Folders group pinned applications in the grid and the dock

*Grounding: docs/evidence/home-widgets-folders/closeout-2026-10-01/board/README.md and sibling paired QEMU reports; operator acceptance plus delegated board uinput proof, not new finger measurements. Additional committed native board evidence: docs/evidence/home-widgets-folders/closeout-2026-10-01/board/README.md and docs/evidence/home-widget-design/closeout-2026-10-01/board/README.md.*

A folder SHALL display as a single rounded tile showing up to four of its
members' icons in a 2x2 arrangement. Tapping a folder tile SHALL open an
overlay showing every member application in a grid and the folder's name.
The folder's name SHALL be editable. Removing an application from a folder
that would leave exactly one member SHALL dissolve the folder, leaving that
one application pinned directly in the folder's former cell.

#### Scenario: Tapping a folder opens its contents

- **WHEN** a person taps a folder tile on Home (outside rearrange mode)
- **THEN** an overlay opens showing every application in that folder and
  its name

#### Scenario: Tapping an app inside an open folder launches it

- **WHEN** a person taps an application shown inside the open-folder
  overlay
- **THEN** that application launches (or is focused, if already running)
  and the overlay closes

#### Scenario: A two-member folder dissolves when one member is removed

- **WHEN** an application is removed from a folder that has exactly two
  members
- **THEN** the folder is gone and the remaining application is pinned
  directly in the cell the folder occupied

### Requirement: Home offers Clock, Battery, and Weather widgets drawn by the shell

*Grounding: `nix/shell.nix`'s existing `k230-weather` desktop entry is
the reused wttr.in source; this board's actual power-supply hardware is
UNVERIFIED beyond "no such sysfs device exists today" (design.md Decision
6). Native board widget appearance and cached weather are recorded in
`docs/evidence/home-widget-design/closeout-2026-10-01/board/README.md`; their content logic (battery absent/present, weather
cache freshness/staleness/offline) is host-tested. Additional committed native board evidence: docs/evidence/home-widgets-folders/closeout-2026-10-01/board/README.md and docs/evidence/home-widget-design/closeout-2026-10-01/board/README.md.*

Home SHALL support placing a Clock widget, a Battery widget, and a Weather
widget, each occupying a fixed cell span, rendered by the shell itself
rather than delegating to an external application. The Clock widget SHALL
show the current time and date in the active theme's colors, updating at
least once per minute, aligned to the minute boundary. The Battery widget
SHALL show a clean "no battery info" state when no battery device is
present, and SHALL reflect a battery device that later appears without
requiring a restart. The Weather widget SHALL show a condition indicator
and the current temperature from the same source `k230-weather` already
uses, fetched no more often than every 30 minutes, cached to disk, and
SHALL continue showing its last successful reading when offline rather
than an error or a blank tile.

#### Scenario: A fresh install seeds a Clock widget

- **WHEN** the shell starts with no previously saved Home layout
- **THEN** a Clock widget appears on Home's first page showing the current
  time and date

#### Scenario: The clock redraws at the minute boundary

- **WHEN** the wall-clock minute changes while Home is showing
- **THEN** the Clock widget's displayed time updates to match

#### Scenario: No battery device exists

- **WHEN** the running system has no `power_supply` class device of type
  Battery
- **THEN** the Battery widget shows a clean "No battery info" state, not an
  error, a dash, or a stale reading

#### Scenario: A battery device appears later

- **WHEN** a battery device becomes available after Home has already
  started (for example, a keyboard base with a fuel gauge is connected)
- **THEN** the Battery widget begins showing its charge level within about
  30 seconds, without restarting the shell

#### Scenario: Weather is shown from cache while offline

- **WHEN** the network is unreachable and a previously cached weather
  reading exists
- **THEN** the Weather widget continues showing that cached reading rather
  than an error or a blank tile

### Requirement: Home's persisted layout carries folders and widgets, migrating older files

*Grounding: `home_state.rs`'s existing schema-1 round-trip tests are
the migration source this change's schema-2 loader is tested against
directly (`a_schema_1_file_migrates_to_plain_apps_on_load`). Additional committed native board evidence: docs/evidence/home-widgets-folders/closeout-2026-10-01/board/README.md and docs/evidence/home-widget-design/closeout-2026-10-01/board/README.md.*

The on-disk Home layout SHALL record folders (their name and member
application ids) and widgets (their kind) alongside plain pinned
applications, for both grid pages and the dock. A layout file written by an
earlier version of the shell that predates folders and widgets SHALL load
successfully, with every previously pinned application preserved in its
existing cell.

#### Scenario: An older layout file still loads

- **WHEN** the shell starts with a saved layout file written before this
  change, containing only plain pinned applications
- **THEN** Home shows every one of those applications in its previously
  saved cell, with no error and no data loss

### Requirement: Cross-page dragging pages fluidly with a visible edge affordance

*Grounding: implemented and host-tested (`home_screen`/`home_pager`
unit tests, including the dwell-timing, page-creation, and fling tests
named below). The rendered edge glow/arrow and "no room" highlight are
evidenced by a host Cairo render harness
(`docs/evidence/home-widget-design/`), not a board or QEMU capture; real
touch feel and daylight visibility of the affordance are UNVERIFIED on
hardware. Additional committed native board evidence: docs/evidence/home-widgets-folders/closeout-2026-10-01/board/README.md and docs/evidence/home-widget-design/closeout-2026-10-01/board/README.md.*

While a person holds a dragged Home item (an icon, a folder, or a widget)
within about 40px of the panel's left or right edge, Home SHALL show a
visible themed highlight and a growing arrow at that edge, and SHALL turn
to the neighboring page after about 350-400ms of continuous holding there.
Continuing to hold at the edge past that first turn SHALL keep turning
pages with a shorter repeat delay of about 260ms. Holding at the true last
page's right edge past that same dwell SHALL create a brand-new, empty page
and slide onto it rather than remaining inert. Every page turn this
triggers, and any triggered by a quick horizontal fling below, SHALL
animate as a smooth slide, never an instant jump, and the dragged item's
own on-panel position SHALL continue following the raw finger position
throughout, unaffected by the page transform. Page-count dots SHALL render
enlarged while any drag is live. A quick, deliberate horizontal drag motion
during a hold (independent of edge proximity) SHALL also turn one page
immediately. A multi-cell widget's drag hovering over a target it cannot
fit SHALL show a visibly distinct "no room here" highlight instead of the
ordinary accepting one.

#### Scenario: The edge affordance appears before the page turns

- **WHEN** a person holds a dragged item within the edge zone for less than
  the first-dwell threshold
- **THEN** a themed edge highlight and arrow are visible, growing toward
  full, and the page has not yet turned

#### Scenario: A held edge drag turns the page, smoothly, under the finger

- **WHEN** a person holds a dragged item at the panel's right edge past the
  first-dwell threshold
- **THEN** Home slides to the next page with an eased animation, and the
  dragged item stays visually under the finger throughout

#### Scenario: Continuing to hold keeps paging, faster than the first turn

- **WHEN** a person keeps holding a dragged item at the edge after the
  first page turn
- **THEN** each subsequent page turn fires after the shorter repeat delay,
  not the longer first-dwell delay

#### Scenario: Holding at the true last page's edge creates a new page

- **WHEN** a person holds a dragged item at the right edge of Home's
  current last page past the dwell threshold
- **THEN** a new, empty page appears and Home slides onto it

#### Scenario: A quick fling pages over without waiting for the edge

- **WHEN** a person makes a quick, deliberate horizontal drag motion during
  a hold, anywhere on the panel
- **THEN** Home turns one page immediately, without needing to reach an
  edge or wait out a dwell

#### Scenario: A widget dragged somewhere it cannot fit shows "no room"

- **WHEN** a person drags a multi-cell widget so it hovers over a cell (or
  cells) already fully occupied by another item of equal or larger span
- **THEN** the drop-target highlight shows the distinct "no room here"
  styling instead of the ordinary accepting highlight

### Requirement: Home's widgets are visually redesigned with distinct styles and richer content

*Grounding: implemented and host-tested (clock style formatting,
`j1` forecast selection/parsing, battery ring percent/charging state, the
procedural dot-matrix digit table). Rendered appearance is evidenced by a
host Cairo render harness (`docs/evidence/home-widget-design/`) composited
over real Omarchy theme wallpaper images, not a board or QEMU capture;
daylight readability and on-device color/font reproduction are UNVERIFIED
on hardware. Additional committed native board evidence: docs/evidence/home-widgets-folders/closeout-2026-10-01/board/README.md and docs/evidence/home-widget-design/closeout-2026-10-01/board/README.md.*

The Clock widget SHALL offer at least four selectable visual styles,
researched from current mobile-platform and community widget design
(`docs/design/clock-widget-research.md`): a heavy centered stacked hour/
minute pair, a thin centered single time line, a procedurally drawn
dot-matrix readout, and a drawn analog face (ticks and hands only, no dial
fill or ring) with an accent-colored minute hand -- each choosable from the
widget picker, which SHALL render a live preview of each widget kind's
actual content inline in its own row. The Battery widget SHALL show its
charge as a themed ring with a distinct charging indicator when charging,
and its absent state SHALL pair the existing "No battery info" wording with
a muted outline battery glyph. The Weather widget SHALL show the current
temperature as a large numeral, a drawn condition icon distinct per
condition family (at minimum sun/cloud/rain/snow/fog/storm), the location
name when available, today's high and low, and a short multi-entry forecast
strip when forecast data is available. No widget of any kind SHALL paint a
card background, surface fill, or border behind its content -- every widget
sits directly on the wallpaper; legibility SHALL instead come from a halo
or glow computed from the theme's own resolved color for that glyph (a
light halo behind a dark glyph, a dark halo behind a light glyph), never a
fixed shadow color that ignores which theme is active.

#### Scenario: A person can choose a clock style from the picker

- **WHEN** a person opens the widget picker's Widgets page
- **THEN** more than one Clock entry is listed, each showing a live preview
  of that style's actual rendered content, and long-pressing one places a
  clock in that style

#### Scenario: A charging battery shows a distinct indicator

- **WHEN** the Battery widget's underlying state reports a battery that is
  charging
- **THEN** the widget's ring shows a charging glyph distinct from its
  non-charging appearance

#### Scenario: The weather widget shows a forecast strip when data allows

- **WHEN** a fresh weather reading includes forecast entries
- **THEN** the widget shows a short strip of upcoming entries, each with its
  own time label, temperature, and condition glyph

#### Scenario: No widget paints anything behind its own content

- **WHEN** any widget (of any kind) is shown on a Home page over any
  wallpaper
- **THEN** nothing is visible behind that widget's glyphs but the wallpaper
  itself -- no card fill, no border, no corner radius

#### Scenario: A glyph's halo follows its own color, not a fixed shadow

- **WHEN** a widget paints a light-colored glyph, and separately when it
  paints a dark-colored glyph
- **THEN** the light glyph is haloed in a dark color and the dark glyph is
  haloed in a light color

### Requirement: Home presents pinned app icons across swipeable pages

*Grounding: operator accepts Home page swipes and icon taps on the installed
shell in `docs/evidence/home-screen/real-touch/operator-report-2026-10-08.md`.
Host pager fixtures and paired QEMU wiring remain separate evidence; no
physical timing or per-frame tracking measurement is inferred.*
<!-- UNVERIFIED: daylight readability has not been observed. -->

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

*Grounding: dock taps and Home page navigation accepted in
`docs/evidence/home-screen/real-touch/operator-report-2026-10-08.md`; no new
recording or measured fixed-position trace is inferred.*

Home SHALL show a fixed-position quick-launch dock beneath the icon grid,
holding a bounded number of pinned icons that do not move or scroll when the
grid pages change.

#### Scenario: The dock stays put while pages change

- **WHEN** a person swipes between Home pages
- **THEN** the dock's icons remain in the same screen position and selection
  throughout the swipe and after it settles

### Requirement: Apps can be pinned to, unpinned from, and rearranged on Home

*Grounding: pin/unpin/rearrange and icon dragging accepted in
`docs/evidence/home-screen/real-touch/operator-report-2026-10-08.md`; the
final right-click app-action check is accepted in
`docs/evidence/home-screen/closeout-2026-10-09.md`.*

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

<!-- UNVERIFIED: physical fresh-install seeding is not observed; host fixtures are separate proof. -->

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

*Grounding: primary launch/focus accepted in
`docs/evidence/home-screen/real-touch/operator-report-2026-10-08.md`, with
matching installed executable in the October 9 closeout report. Six
injected-board multi-window/primary/New Window checks remain separate proof
in `docs/evidence/home-screen/app-actions/board/full-system/actions-result.json`.
Matching remains best-effort for apps without usable desktop identity; a miss
falls back to the normal desktop-entry launch path.*

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

*Grounding: operator navigation accepted in
`docs/evidence/home-screen/navigation/operator-acceptance-2026-10-01.md` and
`docs/evidence/hdmi-hotplug/live-switch/fast-runtime-qualification.json`.
The paired QEMU and injected-board trials in
`docs/evidence/home-screen/navigation/README.md` remain distinct from those
physical reports; no new cancellation/second-contact recording is inferred.*

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

*Grounding: right-click New Window accepted in
`docs/evidence/home-screen/closeout-2026-10-09.md`, with previous primary focus
and icon-grab acceptance on the exact same installed Rust executable. Native
pointer delivery/dismissal and six injected-board action checks remain
separate evidence under `docs/evidence/home-screen/app-actions/board/`.*

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

### Requirement: Secondary click on empty Home space opens the Home menu

*Grounding: host test
`home_screen::tests::secondary_click_on_empty_home_space_opens_the_menu_but_not_on_an_icon`;
operator report on the HDMI trackpad, 2026-10-15, system `acmin041…`
(`openspec/changes/archive/2026-10-15-home-space-right-click-opens-the-home-menu/tasks.md` 1.2).*

A secondary click on an empty, addressable Home cell SHALL open the same
Home menu that a long press on that space opens, under the same conditions.
It SHALL NOT open while that menu is already open, while rearranging, while a
folder is open, or while a drag or touch contact is active. A secondary click
on an app icon SHALL continue to open that app's menu.

#### Scenario: Right-click on empty space

- **WHEN** a person right-clicks (for example, a two-finger trackpad click)
  on an empty Home cell
- **THEN** the Home menu opens, the same as after a long press there

#### Scenario: Right-click on an app is unchanged

- **WHEN** a person right-clicks an app icon on Home
- **THEN** that app's menu opens and the Home menu does not

### Requirement: Battery - Details graphs the charge over the last 12 hours

*Grounding: requested by the operator on 2026-10-15 after the widget showed
live discharge figures on the board. Host renders
(`docs/evidence/battery-details-widget/history/README.md`), a board grim with
the recorded history file showing a discharge, a gauge recalibration and a
power-off gap (`docs/evidence/battery-details-widget/history/board/README.md`),
and the operator's look on HDMI ("graph looks fine", 2026-10-15). A charging
stretch is seen in a later board grim, but no capture of it is committed.*

The shell SHALL record the battery percentage and whether the battery was
charging about once a minute while it runs, and immediately when the charging
state changes, to a per-user history file beside the Home layout. Recording
SHALL happen whether or not a Battery - Details widget is placed. The file
SHALL keep at least the last 24 hours, SHALL survive shell restarts and
reboots, and SHALL be pruned so it does not grow without bound. The Battery -
Details widget SHALL draw the last 12 hours of recorded percentage as a line
graph from 0 to 100 percent. Charging spans SHALL be visually distinct from
discharging spans, and spans with no samples for more than 5 minutes SHALL be
shown as gaps rather than joined.

#### Scenario: History survives a reboot

- **WHEN** the shell recorded samples, the board reboots and the shell starts
  again
- **THEN** the widget's graph still shows the earlier samples, with a gap for
  the time the shell was not running

#### Scenario: Discharge then charge

- **WHEN** the history holds a discharge from 90 to 40 percent followed by a
  charge back to 70 percent
- **THEN** the graph falls and then rises, with the charging part drawn in the
  charging style

#### Scenario: Bad or future samples

- **WHEN** the history file has an unparsable line or a sample dated after the
  current time
- **THEN** those samples are ignored and the rest of the graph still draws

#### Scenario: No history yet

- **WHEN** the history has fewer than two samples in the window
- **THEN** the widget shows its other metrics without a graph line

### Requirement: A multi-cell widget responds anywhere inside its painted area

*Grounding: reproduced on the host from the board's saved layout at 1280x800
(`HomeScreen::filled_slot_at` regression test). On HDMI, a scripted long press
in a cell gap inside the Clock entered rearrange mode
(`docs/evidence/home-screen/widget-hit-area/README.md`, injected pointer +
grim). The operator removed widgets with the physical trackpad and accepted
the result (`docs/evidence/home-screen/operator-trackpad-2026-10-15.md`).*

A press, long press or secondary click anywhere inside the rectangle where Home
paints a multi-cell widget SHALL resolve to that widget, including points that
fall in the gaps between the widget's grid cells. Single-cell icons SHALL keep
their tile-only hit area, so the gaps between separate icons stay inert.

#### Scenario: Long press in a gap inside a widget

- **WHEN** the operator presses and holds at a point inside a 4x2 widget's
  painted area that lies in the gap between two of its cells
- **THEN** Home enters rearrange mode and picks up that widget

#### Scenario: Gap between two icons

- **WHEN** the operator taps the gap between two separate app icons
- **THEN** no icon opens

### Requirement: Home widgets can be moved and removed with a mouse

*Grounding: host tests in `home_screen`. On HDMI, scripted right-clicks
entered rearrange mode with widget badges on page 1 and page 2, and a scripted
badge click removed a widget
(`docs/evidence/home-screen/widget-right-click/README.md`,
`docs/evidence/home-screen/page-settle/README.md`). The operator right-clicked
a widget on the physical trackpad and accepted the feature (`docs/evidence/home-screen/operator-trackpad-2026-10-15.md`).*

A secondary click on a Home widget SHALL enter rearrange mode without picking
the widget up and without opening any menu. It SHALL NOT do so while the Home
menu or a folder is open, while already rearranging, or while a drag or touch
contact is active. In rearrange mode every widget SHALL show a remove badge at
its top-left corner, and a click on that badge SHALL remove the widget. A
press and drag on a widget in rearrange mode SHALL move it, as for icons.

#### Scenario: Right-click a widget

- **WHEN** a person right-clicks (for example, a two-finger trackpad click) on
  a Home widget
- **THEN** Home enters rearrange mode and nothing is picked up or removed

#### Scenario: Remove a widget with its badge

- **WHEN** Home is in rearrange mode and a person clicks a widget's remove
  badge
- **THEN** that widget is removed from Home

#### Scenario: Move a widget with the mouse

- **WHEN** Home is in rearrange mode and a person presses on a widget and
  drags it to another free area
- **THEN** the widget moves there

### Requirement: Home always comes to rest on a whole page that exists

*Grounding: host tests in `home_pager` and `home_screen`. On HDMI, removing
the only page-2 widget returned Home to page 1
(`docs/evidence/home-screen/page-settle/README.md`, injected pointer + grim).
The operator swiped between pages on the physical trackpad and accepted the
result (`docs/evidence/home-screen/operator-trackpad-2026-10-15.md`). The operator's own page-2 removal is covered by that verdict
only, not by the log.*

When a page drag ends without a release, for example a two-finger trackpad pan
the shell cancels, Home SHALL settle to the nearest page rather than stop
between two. When the number of pages shrinks so that the page in view no
longer exists, Home SHALL settle onto the last page that does, including in
rearrange mode. At rest, what Home paints and where a press lands SHALL
always refer to the same page.

#### Scenario: Cancelled trackpad pan

- **WHEN** a two-finger trackpad pan moves Home partway between pages and the
  shell cancels it
- **THEN** Home settles to the nearest page, and a press on a widget shown
  there acts on that widget

#### Scenario: Last page emptied

- **WHEN** the only item on the last page is removed
- **THEN** Home settles onto the previous page and its page dots reflect the
  new count

### Requirement: Home offers a 4x2 Battery - Details widget showing the gauge and charger metrics

*Grounding: the attributes come from the board's `bq27220-0` fuel gauge and
`bq25890-charger-0` charger as read from sysfs on 2026-10-15 while charging
over USB-C (`docs/evidence/keyboard-base/charger/README.md` records the gauge's
sign convention, about +600 to +700 mA charging and -400 mA discharging, and
the charger's registers). Layout legibility is a host render
(`docs/evidence/battery-details-widget/host/README.md`). Appearance and values
on the board were matched against sysfs in grim captures
(`docs/evidence/battery-details-widget/board/README.md`). The operator placed
the widget from the picker with the physical trackpad and accepted it
(`docs/evidence/home-screen/operator-trackpad-2026-10-15.md`).*

Home SHALL offer a "Battery - Details" widget occupying 4 columns by 2 rows,
drawn by the shell and placeable on any grid page like the other widgets. It
SHALL show the battery percentage prominently with the state word (Charging,
Discharging, Full or Not charging) and, while charging, the charge type; the
time to full or time to empty when the gauge reports it; battery current in
milliamps with its sign (positive charging, negative discharging) and power in
watts; battery voltage; stored charge against full charge in milliamp-hours;
health as full charge over design charge; cycle count; battery temperature in
degrees Celsius; and a charger line stating whether input power is online, the
input current limit, the charge current and voltage targets, and the charger's
health when it is not Good. The shell SHALL find the battery and charger by
their `power_supply` type and parse one `uevent` per supply; any attribute that
is missing SHALL be omitted rather than shown as zero or a placeholder. When no
battery supply exists the widget SHALL show the same "No battery info" state as
the Battery widget. The existing Battery widget and previously saved layouts
SHALL be unaffected.

#### Scenario: Charging with a fast charge

- **WHEN** the gauge reports Charging, 55 percent, +600 mA, 4.20 V, 1627 of
  3000 mAh and a time to full of 8160 s
- **THEN** the widget shows the percentage, "Charging" with the charge type,
  "2 h 16 m to full", "+600 mA", the power in watts, "4.20 V",
  "1627 / 3000 mAh", health 100 percent and the temperature

#### Scenario: Discharging

- **WHEN** the gauge reports Discharging with a negative current and a time to
  empty
- **THEN** the widget shows the negative current with its minus sign and the
  time as "left", and the charger line reads "On battery"

#### Scenario: Attributes are missing

- **WHEN** a supply omits attributes such as cycle count or temperature
- **THEN** only those metrics are left out and the rest still render

#### Scenario: No battery

- **WHEN** no supply of type Battery exists
- **THEN** the widget shows "No battery info"

#### Scenario: Faster refresh only while the widget is on Home

- **WHEN** a Battery - Details widget is placed on any Home page
- **THEN** the battery is re-read about every 10 seconds and Home repaints
  only when a displayed value changes; with no such widget the poll stays at
  about 30 seconds

#### Scenario: Older layouts still load

- **WHEN** a layout saved before this widget existed is loaded
- **THEN** it loads unchanged

### Requirement: The widget picker fits its card and places a widget on tap

*Grounding: host tests
`home_grid::tests::every_picker_row_sits_inside_the_card_at_every_surface`,
`home_screen::tests::a_plain_tap_on_a_widget_preview_places_it_and_closes_the_sheet`,
`home_screen::tests::a_tap_on_a_widget_row_works_on_landscape_surfaces_too`;
host renders `docs/evidence/home-screen/widget-picker-fit/host/`; the board
capture of the defect is
`docs/evidence/home-screen/widget-picker-fit/board/before-widget-rows-past-the-card-1280x800-grim.png`.*
On HDMI, the rows fit the card and a scripted click placed Weather
(`docs/evidence/home-screen/widget-picker-fit/README.md`). The operator's
physical clicks placed Battery - Details and Weather (`docs/evidence/home-screen/operator-trackpad-2026-10-15.md`); the plain
Battery row was not the one clicked.

Every row of every widget-picker page SHALL lie inside the picker card at
every supported surface size, using two columns and shorter rows where one
column does not fit. A tap or click on a widget row SHALL place that widget
at the first free spot it fits on the page in view, else on the first page
with room, close the sheet and save the layout. A press-and-hold on the row
SHALL still drag the widget instead.

#### Scenario: Landscape picker rows are pressable

- **WHEN** a person opens the Widgets page on a landscape surface and presses
  its last row
- **THEN** the press lands on that row inside the card, not outside it

#### Scenario: Tap adds a widget

- **WHEN** a person taps or clicks the Battery row
- **THEN** a Battery widget appears on Home and the sheet closes

### Requirement: The Clock widget's date is readable at every text step

*Grounding (2026-10-16): `clock_date_is_readable_at_every_text_step` checks
four card sizes at four steps. Native panel captures at 100%, 160% and 200%
are in `docs/evidence/home-widgets/clock-date/` and
`docs/evidence/clock-restyle/`. The operator judged the restyled clock on
glass: "clock lookgs good" (sic). In the restyle the date is drawn at 32 px or
more.*

Every Clock widget style SHALL draw its date line at no less than 26 px on
the panel at the 100% text step. The size SHALL grow in proportion to the
Vision text step. The date line SHALL fit within the widget's cell without
ellipsizing, shrinking only to fit the cell's width. The time SHALL NOT
overlap the date at any step.

#### Scenario: The date at the default step

- **WHEN** Home shows a Clock widget at the 100% text step
- **THEN** its date line is at least 26 px tall in font size and is shown in
  full

#### Scenario: The date at the largest step

- **WHEN** Home shows a Clock widget at the 200% text step
- **THEN** its date line is larger than at 100%, unless the cell's width
  limits it, and neither the date nor the time is clipped or overlapped

### Requirement: The Clock widget marks the minute with the theme accent

<!-- UNVERIFIED: the hour/minute colours are seen in the panel captures under
docs/evidence/clock-restyle/ and approved on glass, but a theme change
re-colouring the minute without a restart has not been observed on the
board. -->

Every Clock widget style SHALL draw the hour in the active theme's foreground
colour and the minute in its accent colour. It SHALL take both colours from
the theme and SHALL keep the existing halo so the time reads over any
wallpaper. It SHALL NOT use the accent for any other element of the Clock
except the analog style's minute hand.

#### Scenario: The Bubble clock on the panel

- **WHEN** Home shows the Bubble Clock on the landscape panel
- **THEN** the hour numerals are the theme's foreground colour
- **AND** the minute numerals below them are the theme's accent colour
- **AND** the date is the foreground colour

#### Scenario: A theme change

- **WHEN** the person activates a theme with a different accent
- **THEN** the minute takes the new accent without a restart

### Requirement: The Clock widget's date is one neutral line of at least 32 px

*Grounding (2026-10-17): host tests `clock_date` check the date's size, width
and clearance at 100/130/160/200%; native panel captures at 100%, 160% and
200% are in `docs/evidence/clock-restyle/board-panel-*-home.png`, and the
operator judged the Clock on glass ("clock lookgs good").*

Every Clock widget style SHALL draw its date as one line of mixed-case text
(for example "Fri, Oct 16") in the foreground colour, at no less than 32 px at
the 100% text step. The size SHALL grow with the Vision text step. The date
SHALL fit the cell without ellipsizing, and the time SHALL NOT overlap it.

#### Scenario: The date at the default step

- **WHEN** Home shows a Clock widget at the 100% text step
- **THEN** its date is shown in full, in mixed case, at 32 px or more

#### Scenario: The date at the largest step

- **WHEN** Home shows a Clock widget at the 200% text step in either
  orientation
- **THEN** neither the date nor the time is clipped or overlapped
