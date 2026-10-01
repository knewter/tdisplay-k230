## Why

`the-shell-presents-a-pinned-home-screen` (still unarchived) gave this
handheld a pinned-icon Home with pages, a dock, and long-press pin/unpin/
rearrange — and explicitly listed "folders or categories" and "home-screen
widgets" as non-goals for that pass. The user now wants both, plus a
specific correction to the pin gesture itself, in their own words: "i
wouldn't want 'long press to pin to home' i want 'long press to start the
process of dragging it where it will live on home' and home should support
multiple screens i can swipe between like android bruh as well as widgets -
clock battery weather are the obvious firsts. same dealio for folders and i
can have folders in the 'dock bar' in theory."

Three concrete gaps this closes:

1. **The pin gesture is wrong.** Long-pressing a drawer app currently drops
   it into the first free slot immediately — there is no chance to choose
   *where*. Every reference launcher (Android, webOS, iOS) instead lifts the
   icon and lets a person carry it to a cell, a dock slot, or onto another
   icon to make a folder.
2. **Nothing groups icons.** Two related apps cannot become one tile. The
   dock is App-only, plain 1x1 slots.
3. **Home shows nothing but icons.** A person cannot see the time, battery,
   or weather without leaving Home to open another app, even though this
   shell already has a `k230-weather` desktop entry and a themed rendering
   pipeline capable of drawing exactly that content itself.

## What Changes

- **Drag-to-place from the drawer.** Long-pressing a drawer app now arms a
  live drag (icon lifts, follows the finger) instead of an instant pin.
  Home is revealed underneath while the drawer's own surface stops painting
  its grid/search chrome and shows only a Cancel band. Dropping on an empty
  cell places it there; on an existing app, creates a folder; on a folder,
  joins it; in the dock, places it there (or into a dock folder); holding
  near an edge for ~500ms turns the page; releasing over the Cancel band
  aborts with nothing changed.
- **The same drag model for rearranging on Home.** Long-pressing a pinned
  icon, folder, or widget already carries it through the identical
  cell/folder/dock/edge-page-switch/remove resolution, replacing the old
  swap-only behavior for anything that can merge. Empty pages are pruned
  automatically.
- **Folders**, in the grid and in the dock: a rounded tile with a 2x2
  mini-icon preview; tapping opens an overlay with the folder's apps and an
  editable name; a folder left with one app dissolves back into it.
- **Three widgets** the shell draws itself: Clock (4x2, minute-aligned
  redraw), Battery (2x2, reads `/sys/class/power_supply`, a clean "No
  battery info" state — this board currently has none, the fuel gauge lives
  on a not-yet-connected keyboard base — and a 30s poll for one appearing),
  and Weather (2x2, reuses the wttr.in source `k230-weather` already uses,
  disk-cached and fetched at most every 30 minutes, offline-safe).
- **Persistence** widens from schema 1 (a bare app-id string per cell) to
  schema 2 (`HomeItem`: App/Folder/Widget, each with its own footprint),
  migrating an existing schema 1 file in place on load.

**Non-goals for this pass (see `design.md`'s Deferred section and
`tasks.md`):** the widget picker sheet UI (long-press empty Home space to
choose a widget) and drag-a-widget-from-it; the open folder's rename field
actually taking system-keyboard input (the rename *data* — buffer, apply,
cancel — exists and is tested, the keyboard grab is not wired); dragging an
app back out of an *open* folder onto Home; cached-layer/dirty-rect
rendering and prebuilding the drawer's grid cache at idle (both explicitly
"if you can" in the task, not required); widget resizing (explicitly
"skip it if it's costly"). None of these regress what already shipped in
`the-shell-presents-a-pinned-home-screen`.

**Board dependency:** every behavior above is host-testable and covered by
`cargo test --offline` with no hardware — the drop resolution, folder
create/join/dissolve, schema migration, and both widgets' content logic
(including the battery-absent and battery-present cases, and the weather
cache's fresh/stale/offline states) are plain Rust unit tests. The drawer's
tick-driven long-press-arm and Home's external-drag hand-off are also
host-tested at the state-machine level. A QEMU injected-touch trial of the
new drag/folder/widget interactions, and the physical-board real-finger
acceptance, remain open evidence gates for the coordinator (see task 6 and
`tasks.md`'s final section) — this proposal does not touch the board.

## Capabilities

### New Capabilities

None. This extends the existing `runtime/home-screen` capability
(`the-shell-presents-a-pinned-home-screen`'s own new capability, still
unarchived — see that proposal's own `Modified Capabilities` note for why a
`MODIFIED` delta cannot legally target it yet per
`.skills/k230-spec-change/SKILL.md`). This change's own spec delta adds new
requirements to `runtime/home-screen` as `ADDED`, for the same reason: there
is nothing in `openspec/specs/runtime/home-screen/` yet to modify.

### Modified Capabilities

None archived to modify. The sibling proposal's own requirements (paged
grid, dock, pin/unpin/rearrange, seeding, persistence, tap-to-launch,
gesture topology) are superseded in spirit by this change's drag-to-place
model and widened persistence schema — see `design.md`'s reconciliation
note for exactly which of that proposal's scenarios this one revises in
place once both land, and the coordinator note left for whoever archives
first.

## Impact

Userspace only, `nix/rust-shell-client/`: `home_state.rs`'s on-disk model
(`HomeItem`, schema 2 + migration), `home_screen.rs`'s drag/drop/folder
gesture logic, `home_grid.rs`'s span/folder-overlay geometry, a new
`home_widgets.rs` (battery/weather/clock content), `navigation.rs`'s
drawer long-press arming, `render.rs`'s Home/folder/widget painting and the
drawer's drag-reveal rendering, and `main.rs`'s touch-dispatch wiring for
the hand-off plus the widgets' poll/fetch scheduling. No kernel, device
tree, boot, radio, or second-core change; no new Nix package. The existing
`.#handheld-shell-rust`/`.#card-shell` outputs and the
`k230-coherent-shell` NixOS configuration absorb it.
