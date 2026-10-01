## Context

`the-shell-presents-a-pinned-home-screen` shipped a paged icon grid, a
fixed dock, and long-press pin/unpin/rearrange, all backed by
`home_state::HomeLayout { pages: Vec<Vec<Option<String>>>, dock:
Vec<Option<String>> }` — one desktop-entry id per cell, nothing else.
`home_screen::HomeScreen` drives a single touch contact through
`home_pager::HomePager` (page physics) and `home_grid` (slot geometry),
exactly mirroring `navigation::DrawerNavigation`'s own shape. `render.rs`
paints Home directly from that layout on every dirty frame; there is no
cached-layer/dirty-rect system anywhere in this client, only whole-surface
SHM repaints gated by a `dirty` flag per surface.

The drawer (`navigation.rs`) is a wholly separate `Layer::Overlay` Wayland
surface from Home's `Layer::Bottom`. A touch that begins on one
surface is delivered to that same surface for its whole lifetime — Wayland
grants touch focus at `down` and does not reassign it — so a drag that
visually "moves from the drawer to Home" cannot be a real cross-surface
touch handoff; it has to be the drawer's own touch continuing to arrive at
the drawer's own listener while the *drawer stops painting its own content*
and Home (already always mapped underneath) shows through.

## Goals / Non-Goals

Goals: replace instant-pin with drag-to-place; extend pinning to folders
(grid and dock) and three widgets; widen persistence to carry all of it
with migration; do all of this without touching `nix/card-shell/` (another
agent owns compositor-side rendering there concurrently) or the theme
picker.

Non-goals for this pass: the widget picker sheet, drag-to-place *for*
widgets from a picker (only rearranging an already-placed widget is
covered), a live system-keyboard grab for folder rename, dragging an app
out of an *open* folder card, widget resizing, and cached-layer rendering.
Each is called out below with why it was cut rather than silently dropped.

## Decisions

### 1. `HomeItem` replaces the bare id, with schema migration, not a rewrite

```rust
enum HomeItem { App { id: String }, Folder(FolderData), Widget { widget: WidgetKind } }
struct FolderData { name: String, apps: Vec<String> }
enum WidgetKind { Clock, Battery, Weather } // span(): (4,2) / (2,2) / (2,2)
```

`HomeLayout::pages`/`dock` become `Vec<Option<HomeItem>>`. A multi-cell
widget stores itself only at its own anchor cell; the cells it also covers
stay `None` in storage but are excluded from "free" by walking every
anchored item's own `span()` (`home_state::occupied`) — no redundant
"reserved" markers to keep in sync. `HomeLayout::anchor_at` resolves any
covered cell back to the widget's anchor, so a tap/long-press anywhere in a
Clock's 4x2 footprint hits the clock.

`home_state::load` tries the current schema first; on failure, tries the
old bare-string shape and converts every `Some(id)` to `HomeItem::App`. The
file itself is not rewritten until the next save, matching this client's
existing best-effort-state conventions (`home_state.rs`'s own doc already
frames the state directory as "must not be silently dropped", so a
migration that only touches memory, not disk, until an explicit save is the
conservative choice — a crash between migrate and save just re-migrates
next boot instead of losing anything).

### 2. One drop resolver for both a rearrange and a drawer-drag

Rejected: two separate code paths (one for "move an existing icon", one for
"place a new one from the drawer"). Instead `HomeScreen::drop_dragged_item`
takes a `DragSource` (`Existing(HomeSlot)` or `FromDrawer(String)`) and
both funnel into the same `merge_two`/span/dock-eligibility decisions —
folder-create, folder-join, and same-span-swap-or-revert behave identically
regardless of where the dragged item came from. This also means the
"cancel a drawer drag" and "the drop happened to land nowhere resolvable"
cases share `HomeLayout::place_first_fit` as the same fallback the original
pin already used.

### 3. The drawer's long-press-drag: tick-armed, not release-detected

The old `DrawerAction::LongPress` fired at `up()`, after the finger already
lifted — fine for an instant pin, useless for a *drag* the person is still
supposed to be watching happen. `DrawerNavigation::take_long_press_drag`
is now polled every tick (mirroring `HomeScreen::tick`'s own long-press
timer exactly), fires once at `LONG_PRESS_MS`, and **consumes the
contact** (`self.contact = None`) the instant it fires — the rest of that
gesture belongs entirely to `HomeScreen`'s external-drag API from that
point on, and the navigation model's own `motion`/`up` simply see no
contact and no-op. `main.rs` remembers which touch id this is
(`drawer_home_drag: Option<i32>`) and, for that id only, skips the
drawer's ordinary scroll/close-drag/search dispatch entirely in favor of
forwarding straight into `home.external_drag_motion`/`release_drag`.

### 4. "Reveal Home" is rendering, not a route change or a real surface handoff

Rejected outright: reassigning the Wayland touch to Home's surface
mid-gesture (protocol does not support it) and tearing down/reopening the
drawer's layer-shell surface mid-drag (`main.rs::hide()` destroys `self.layer`
synchronously; a still-live touch bound to a since-destroyed `wl_surface`
would very likely be cut short by the compositor, and even if it were not,
`begin_animated_close()`'s own settle animation is *the* mechanism that
later destroys the surface, so starting it mid-drag races the drag itself).

Instead: while `drawer_home_drag.is_some()`, the drawer's own `draw()`
skips its normal `draw_with_hud` call and paints a small, purpose-built
frame instead (`RendererCache::draw_drawer_drag`): fully transparent except
a translucent Cancel band across its former top-chrome zone. Home's own
`Layer::Bottom` surface (already always mapped, underneath) keeps painting
itself exactly as it does for an on-Home rearrange — including the lifted
icon and drop-target highlight — so it simply shows through. This is a
real, correct "reveal", just implemented as "stop drawing the top layer"
rather than an actual slide/fade transition. **Deferred:** an animated
slide/fade for the reveal itself (currently instant) and for the drawer's
return-to-normal on Cancel (also currently instant) — both are pure
`render.rs`/`main.rs` polish with no data-model dependency, safe to add
later without touching this change's own logic.

The drawer's own top-chrome band is reused as the Cancel target (task:
"a Cancel target at the top, or releasing over the drawer area") — since
the drawer's grid is hidden during the drag, that top band is the one part
of its surface that still reads as "the drawer" to release back onto,
so a single zone serves both phrasings rather than adding a second,
separate top-of-Home pill that would sit on the wrong surface entirely
(the drop point is delivered to the drawer's touch listener, not Home's).

### 5. Folders: fold-into-the-held-item, not fold-into-the-target

`merge_two(dragged, existing)` always keeps *the item under the finger* as
the survivor: an app dropped onto a folder joins that folder; a folder
dropped onto a lone app absorbs that app into the *dragged* folder, not the
reverse. This is one predictable rule instead of four direction-dependent
ones, and it matches where a person's attention already is (the thing they
are actively carrying). Folder+folder does not merge (two folders' worth of
apps combining unprompted felt like real data loss risk for a first pass);
it swaps positions instead, the same fallback any other non-mergeable,
same-span drop gets.

A folder dissolving at one member (`HomeLayout::remove_app`) is a property
of removal, not of the drag/drop path — it fires identically whether the
last-but-one app left via a drag-out, a future "remove from folder" action,
or (today, since drag-out-of-an-open-folder is deferred) nothing at all yet
actually reaches it outside tests. The logic is real and tested now so
whichever removal path lands next has nothing left to implement here.

### 6. Widgets: fixed spans, poll/cache for content, no resizing

Each `WidgetKind` gets exactly one span from the task's own listed options
(Clock 4x2; Battery and Weather 2x2, the smaller of each pair's two
choices, since a 4x2 weather tile would waste a full row's width on two
fields). Resizing is the task's own explicitly optional item and is cut
entirely for this pass — supporting it later needs per-instance span
storage (`HomeItem::Widget` would need to carry its own span override, not
just `WidgetKind`), a bounded but real follow-on.

Battery is a plain synchronous `/sys/class/power_supply` scan on a 30s poll
(the task's own explicit fallback, since this board's current hardware has
no supply device at all to inotify-watch yet — the fuel gauge lives on the
not-yet-connected keyboard base). It runs on the main thread: reading a
handful of small sysfs files is cheap enough not to need a worker.

Weather cannot run on the main thread — it shells out to `curl` against a
real network endpoint, and this client's event loop is a single manual
poll (`Cargo.toml`'s own comment: "the event loop here is a manual poll,
not a calloop source"), so any blocking call on it would freeze every
surface for up to the fetch's timeout. `home_widgets::weather::refresh` is
therefore only ever invoked from a short-lived `std::thread::spawn`,
reporting back through an `mpsc::channel` `main.rs` polls non-blockingly
each tick — spawned at most once per `should_fetch` window (30 minutes),
never per-frame. A stale cache is preferred over "Unavailable" on a failed
fetch (task: "Handle offline gracefully").

### 7. What Home's own rendering does and does not do yet

`render.rs::paint_home` grew a widget-card path (`paint_widget_card`, a
themed plate plus the widget's own live text/glyph) and a folder path
(`paint_item_plate`, a 2x2 mini-icon plate instead of a single icon) that
both slot into the *existing* per-frame whole-surface repaint —
[performance task 7's "cached layers"/"clock redraws only its own area"]
are **not** implemented as actual partial-region compositing; there is
nowhere in this client's architecture to hang that today (every surface
here is one SHM buffer repainted in full on `dirty`, not a stack of
independently-damaged layers). What *is* real: the clock does not drive a
60fps or even per-frame redraw — `main.rs::tick_home_widgets` schedules the
next minute-aligned wake itself (`home_widgets::clock::
ms_until_next_minute`) and only marks Home dirty then, so between minute
boundaries nothing about the clock causes a single extra repaint. Turning
that into a genuine sub-region repaint (and prebuilding the drawer's grid
cache at idle, the task's other performance item) are both real, separably
schedulable follow-on work, not implemented here — see `tasks.md`.

## Deferred (explicitly, with why)

- **Widget picker sheet** (long-press empty Home space → "Widgets /
  Wallpaper & style / Home settings", a preview list, drag-to-place). This
  is a new overlay surface's worth of UI with its own hit-testing,
  independent of the placement engine this change delivers — the engine
  (`HomeLayout::place`, span/occupancy) is what a picker would call, and it
  is done and tested; the picker itself is cut for scope.
- **Folder rename's system-keyboard grab.** `home_screen::OpenFolder`'s
  `editing_name`/`name_buffer`/`push_folder_name_char`/
  `backspace_folder_name`/`apply_folder_rename` are real and tested; wiring
  a live `wl_keyboard` grab into the overlay (matching the Wi-Fi password
  field's own keyboard-interactivity request) is a `main.rs` integration
  this pass did not reach.
- **Drag an app out of an open folder onto Home.** Needs the open-folder
  overlay's own touch dispatch to arm a drag mid-overlay, which does not
  exist yet (today the overlay only resolves a tap on release).
- **Cached-layer rendering, prebuilding the drawer's grid cache at idle.**
  See Decision 7.
- **Widget resizing.** See Decision 6.

None of these block what already works: drag-to-place from the drawer,
rearranging (including folder create/join and widget moves) on Home,
folders opening/closing/dissolving, and both implemented widgets' live
content, are all real, wired, and tested end to end at the state-machine
level.

## Migration Plan

`home_state::load` is the only place schema 1 and schema 2 ever meet: it
attempts to deserialize the current shape first, and only on failure tries
the old bare-string shape, converting every entry to `HomeItem::App`. No
separate migration command, no version-gated code path elsewhere in the
client — every other module only ever sees today's `HomeItem`-based
`HomeLayout`. `home_state::seed_default` (fresh install, no saved file at
all) now also seeds one Clock widget onto the first page alongside the
existing curated app defaults, so a brand-new Home is not just an empty
grid with nothing that reads as intentional.

## Risks / Trade-offs

- Folding an app into a folder is nearly one-directional-feeling only for
  Folder-onto-App (see Decision 5); a person may expect the reverse for
  a folder they consider "less important" than the app they dropped it on.
  Cheap to revisit if real-finger feedback disagrees; nothing on disk
  depends on which direction it went.
- The reveal-as-transparency approach (Decision 4) means Cancel and a
  successful drop both currently *look* instant rather than animated,
  which is a visible gap against "the drawer immediately slides or fades
  away" read literally as an animation. It is functionally correct (Home
  really is revealed, the icon really does follow the finger) and safe
  (does not risk the surface-teardown-under-a-live-touch failure mode); an
  actual slide/fade is pure follow-on polish per Decision 4's own note.
