## Context

Today, on this 568x1232 portrait panel:

- The compositor (`nix/card-shell/`, patched Sway) owns a live application-card
  overview. It is titled "Home" on screen (`nix/card-shell/adapter.c`'s
  `rebuild_chrome`, the `touch_first()` branch, hardcoded `"Home"` label) and
  is entered by a bottom-edge gesture from a running application, or a
  persistent recovery route, per `the-shell-manages-apps-as-cards` and
  `the-handheld-presents-a-coherent-shell`. With zero running applications it
  shows an empty "No running apps" canvas, still labeled "Home".
- The Rust client (`nix/rust-shell-client/`) owns the drawer ("All apps",
  reached by swiping up from the idle/empty state — see
  `card_shell_drawer_up` in `nix/card-shell/route.c`, gated on `!shell.active`
  so it never fires while the overview itself is open), the notification
  shade, Settings, and the Quattro-style theme carousel. It also owns a
  persistent `Layer::Background` wallpaper surface (`nix/rust-shell-client/
  src/main.rs`'s `WallpaperState`/`ensure_wallpaper`) that is visible whenever
  nothing else covers it — this is the literal "nothing is open" screen a
  person sees today, and it has no icons on it at all.
- Decision 1 of `the-handheld-presents-a-coherent-shell/design.md` (still
  unarchived) reads: "Home is the deck, not a grid... This shell chooses the
  Palm-style live deck as Home rather than an Android home grid or hold-for-
  recents path", with "an Android-style second home grid" listed as a
  non-goal. That decision was reasoned from Palm webOS's own model (app→card,
  card→Launcher) and from wanting exactly one home destination. The user has
  since asked directly for a grid of pinned icons with swipeable pages, which
  is precisely what that decision ruled out. This proposal does not dispute
  the reasoning that *two* home destinations would be confusing; it disputes
  which screen should be named Home, and picks the one every mainstream
  handheld launcher — including webOS itself, past its very first release —
  actually uses that name for.

## What webOS 3 and Android actually do (research, not K230 proof)

Both of the ecosystems this shell already draws from (Palm/HP webOS via the
[Palm Pre User Guide](https://support.bell.ca/_web/guides/User-Guides/Mobile/
PalmOne/Palm-EN/palm_pre_userguide_en%28en%29.pdf), cited by the sibling
change, and later webOS TV/webOS 3.x devices; Android via
[Android's navigation guide](https://support.google.com/android/answer/
9079646?hl=en) and [gesture guide](https://support.google.com/android/answer/
9079644?hl=en)) converged on the same three-layer shape, not two:

| Layer | webOS (post-Pre "Just Type"/launcher era, and webOS 3 Smart TV launcher) | Android |
| --- | --- | --- |
| **Home** | A grid of app icons the person places, paged, with a persistent **Quick Launch** bar of ~5 icons pinned at the bottom that stays fixed across every page | A grid of app icons/widgets the person places, paged, with a persistent **hotseat** row pinned at the bottom that stays fixed across every page |
| **App switcher / recents** | The card deck (webOS's original and still most-cited contribution): live thumbnails of running apps, swipe to browse, throw up to close | The Overview/Recents screen: live thumbnails of running apps, swipe to browse, swipe up to close |
| **App drawer / catalog** | webOS 3's launcher exposes "all apps" as a separate paged grid one level beyond Home (distinct from the curated Home pages); the original Pre instead used a persistent Launcher edge-swipe to the full catalog | The all-apps drawer, opened from Home (swipe up on the hotseat area, or a dedicated affordance), alphabetical/searchable, separate from Home's curated pages |

The Pre's very first release *did* fold "Home" into the card deck (an empty
deck was the resting state, because the Pre had no persistent grid at all) —
that is the specific, early-Pre-only precedent the sibling decision generalized
from. Every later webOS revision, and Android throughout, treat "Home" as the
pinned grid and keep the live-card view as a separate, differently-named
surface (Card view / Overview) that is *entered from* Home or from a running
app, not conflated with it. This proposal follows the converged, later model:
three distinct, named layers (Home, Overview, Drawer), not two.

## Goals / Non-Goals

**Goals:** a pinned-icon Home with swipeable pages and a persistent
quick-launch dock; pin/unpin/rearrange; sane fresh-install defaults; state
that survives a restart and reboot; tap-to-launch-or-focus; a coherent,
written-down place for Home in the existing gesture map, changing as little
of the existing, already-evidenced card-overview and drawer machinery as
possible.

**Non-goals:** search, folders, widgets, a wallpaper picker, multi-user
profiles, haptics, the second core, changing the card overview's own
manipulation physics (drag/expand/throw-close), composition boundary, or
close-lifecycle (all owned by `the-shell-manages-apps-as-cards` and
`the-shell-has-a-card-composition-plan`), and re-litigating whether the
overview should exist at all (it should; it is Android's Overview / webOS's
card deck, not Home).

## Decisions

### 1. Home is a new, always-present `Layer::Bottom` surface, not a mode of the existing overlay

The Rust client's existing on-demand overlay (`self.layer`, `Layer::Overlay`,
used for Drawer/Shade/Settings) sits *above* every normal application window
by wlroots' own layer-shell stacking order, and is only mapped on demand. Home
must do the opposite: sit *below* every normal application window (so a
focused, full-screen app automatically occludes it with no shell-side
tracking of "is an app focused" at all) and be visible whenever nothing
occludes it. `Layer::Bottom` sits directly above the existing `Layer::
Background` wallpaper and directly below ordinary toplevels and the existing
`Layer::Overlay` surface, which is exactly the required position: below an
app, below the card overview's own compositor-native scene (inserted above
the normal window stack), and below the drawer/shade/Settings overlay when
one of those is open on top of Home.

Rejected: reusing the existing `Route::Hide` value on the overlay surface to
mean "show Home", because that surface is `Layer::Overlay` — showing Home
there would paint over a focused, full-screen application, which is wrong.
Rejected: drawing Home directly into the wallpaper surface itself, because
that surface's buffer/redraw contract is already shared by plain wallpaper,
per-theme background decode, and video-wallpaper playback
(`background_decode.rs`, `video_wallpaper.rs`); adding icon hit-testing and
page-swipe state to it risks all three. A separate surface keeps every
existing wallpaper consumer untouched and lets Home be alpha-composited over
whichever of those three the wallpaper surface is currently showing, exactly
as icons overlay a wallpaper on every reference launcher.

### 2. Reconciled topology: three named layers, each keeping its existing wiring

```
Home (new, Layer::Bottom, always mapped)
  -- swipe up (existing card_shell_drawer_up gesture; unchanged) --> Drawer ("All apps")
  -- tap icon --> launch app, or focus it if already running
  -- long-press icon --> rearrange mode (drag within/between pages, into/out of dock, or remove)
  -- occluded by: a focused application window; the card overview; Drawer/Shade/Settings

Overview (existing card-shell deck, retitled "Overview"; gesture/physics unchanged)
  -- entered by: existing bottom-edge card-entry gesture from a running app,
     or the existing persistent recovery route
  -- dismissed by: existing back/dismiss gesture --> reveals whatever is
     beneath: Home if nothing is focused, or the originating app otherwise
  -- empty state ("no running apps"): still exists as the persistent-route
     fallback (e.g. someone opens Overview with nothing running); dismissing
     it reveals Home the same way

Drawer ("All apps", existing Rust overlay; layout/scroll physics unchanged)
  -- long-press a tile --> "Add to Home" (new)
  -- tap a tile --> launch/focus (existing)
```

No existing gesture recognizer, threshold, or state machine in
`nix/card-shell-policy/` or `navigation.rs` changes. The only compositor
source changes are the "Home" -> "Overview" title string in `adapter.c` and
adding `"home"` to the surface-name allow-list in `route.c` (used later if a
compositor-driven refresh of Home's content is ever needed; the initial
implementation does not require the compositor to invoke it, since Home is
always mapped and redraws itself, but the allow-list entry keeps the naming
consistent and unblocks that path without a further C change).

### 3. Pages: full-bleed grid pages, not a shrinking coverflow

`theme_carousel.rs`'s Cover Flow model (skewed neighbor slices, blend-based
bitmap selection) fits a single hero item users browse one at a time. Home's
pages are not single items — each page is a 4-column icon grid a person reads
as a whole — so a full-bleed pager (each page is exactly one panel-width
apart, no skew, no partial-neighbor peeking beyond an intentionally minimal
edge sliver so a page boundary is not mistaken for a resize) is the right
shape, closer to `navigation.rs`'s drawer scrolling than to the carousel, but
paged (settle to a whole page) rather than free-scrolling (settle to any
pixel). This is the same "coverflow vs. off-the-shelf `ViewPager`" choice
every Android launcher and webOS's own Home page made for the same reason.

Physics conventions are taken from `theme_carousel.rs::Carousel` and
`navigation.rs::DrawerNavigation` (already the shell's two existing precedents
for touch physics) rather than invented fresh: 1:1 drag (dragging one panel
width moves exactly one page), momentum decay at the same `DECAY_PER_16MS =
0.88` per-16ms factor every other flick in this shell uses, a
`MIN_COAST_VELOCITY` cutoff below which a release settles immediately instead
of coasting a fraction of a page, and an ease-out-cubic settle whose duration
scales with distance exactly like `theme_carousel::settle_duration_ms` and
`service_ui::NotificationSwipeSettle`. New module `home_pager.rs` implements
this for whole-page positions (`position: f64` in page-units, not
index-units-with-skew), with its own unit tests mirroring
`theme_carousel.rs`'s (`drag_moves_one_to_one_with_the_finger`,
`slow_release_settles_immediately_to_nearest`,
`fast_flick_coasts_then_settles_and_decays_over_time`).

Page-count indicator dots are drawn, never tappable (per the user's own
"page-indicator dots are fine, since they're indicators, not controls"
constraint) — `render.rs`'s `paint_home` draws them from `HomePager::page(
count)` and `count`, with no hit-test region.

### 4. The dock is a fixed-position row, not a page

The quick-launch dock (webOS Quick Launch bar / Android hotseat) sits below
the grid, at a fixed vertical position, and never scrolls with the pager. It
holds a bounded number of slots (sized to fit 568px width at the same 56px+
touch target convention every other surface in this shell uses — 4 slots at
that width, matching the existing bottom persistent-bar precedent's target
sizing). Dock membership is part of the same persisted layout (a `dock:
Vec<Option<AppRef>>` alongside `pages: Vec<Vec<Option<AppRef>>>`), and an icon
can be dragged between the dock and a page during rearrange mode, exactly as
both reference launchers allow.

### 5. Pin/unpin/rearrange interaction

- **Add to Home**: long-press a drawer tile (`navigation.rs`'s existing tap
  timing already distinguishes a held touch from a tap via `down_ms`; a new
  `LONG_PRESS_MS = 500` threshold with the existing `TAP_SLOP` distance gate
  triggers it) opens a small non-modal confirmation using the same label/
  button chrome primitives `render.rs` already draws elsewhere (no new widget
  system). Confirming appends the app to the first page with a free slot,
  creating a new page if every existing page is full, and persists
  immediately.
- **Rearrange on Home**: long-press an icon on Home enters rearrange mode
  (a visible but small "Done" affordance appears — contextual, not permanent
  chrome, consistent with the "no permanent Back/Home buttons" constraint;
  tapping empty space also exits rearrange mode, exactly like both reference
  launchers). While in this mode, dragging an icon moves it within a page,
  across a page boundary (dragging to the pager's edge for
  `HOLD_AT_EDGE_MS` pages to the neighbor, then continues the drag), into or
  out of the dock, or (dragging to a small onscreen "Remove" target that only
  appears in this mode) off Home entirely, back to being unpinned (still
  installed, still in the drawer). Every drop position re-persists the whole
  layout. Rejected: a jiggling/wobbling icon animation — cheap to add later
  as a decoration, but drag-reorder correctness (not motion polish) is the
  actual accepted-behavior surface here, and continuous per-icon wobble
  redraw is exactly the kind of idle/always-animating cost this shell's own
  "no idle redraw" rule exists to avoid; this proposal ships a static
  "rearrange mode" affordance (dim overlay + Done button + Remove target)
  instead.
- **Tap** (outside rearrange mode): launch-or-focus (Decision 6).

### 6. Tap launches, or focuses an already-running instance

`nix/rust-shell-client/src/main.rs::launch_selected` today always calls
`gio::DesktopAppInfo::launch`, with no check for an existing window — true
for the drawer today, and the deliverable explicitly asks Home to do better.
New function `home_screen::focus_or_launch` first asks the compositor (`
swaymsg -t get_tree`, off the Wayland dispatch thread on the existing launch
worker thread, matching decision 10 of the sibling design: "keep all blocking
catalog/decode/service work outside the Wayland dispatch path") for a window
whose `app_id` matches the tapped entry, using the same heuristic
`tools/notification_center.py`'s `SwayActions` already uses to walk
`get_tree` for con nodes carrying an `app_id`/`window`, but matching by
identity instead of a stored con id: the desktop-entry id with its
`.desktop` suffix stripped, compared case-insensitively against a run's
`app_id`, and as a fallback the desktop entry's `Exec` first token's
basename. This is a best-effort heuristic, not a verified protocol (no
stable desktop-entry-id-to-app_id mapping exists in this stack yet) — marked
`<!-- UNVERIFIED -->` in the spec below pending a real multi-window board
trial: on a match it sends `[app_id="<id>"] focus` (mirroring
`notification_center.py`'s own focus call exactly) instead of launching a
second instance; on no match it falls back to today's `launch_selected`
behavior unchanged.

### 7. Fresh-install defaults come from installed desktop entries, not a hardcoded icon set

Per `openspec/config.yaml`'s standing rule ("Application defaults belong in
this repo and the NixOS image... Fresh homes must provide the usable starting
point"), first run (no saved `home.json`) seeds Home from
`catalog::installed_apps()` by matching a small ordered list of preferred
desktop-entry-id substrings — terminal, file manager, text editor, system
monitor, video player, and Settings, plus the drawer itself as a permanent,
unremovable dock-adjacent affordance the same way both reference launchers
keep an "all apps" affordance always reachable from Home — skipping any that
are not installed on this image rather than showing a placeholder, then
immediately persisting the seeded layout so a second boot is stable even if
the catalog later changes. This mirrors the existing bounded, best-effort
matching style already used for the launcher curation in
`the-launcher-explains-app-actions`, without depending on that change (which
curates the drawer's names, not Home's default membership).

### 8. Persistence path and format

`home_state.rs::state_path()` follows the exact fallback shape
`theme_thumbnails.rs::disk_cache_dir_from` already established for this
client's other on-disk state (`$XDG_STATE_HOME/k230-shell/home.json`, or
`$HOME/.local/state/k230-shell/home.json` when `XDG_STATE_HOME` is unset or
empty), matching the existing `$XDG_CACHE_HOME/k230-shell/thumbs` /
`~/.cache/k230-shell/thumbs` convention one directory family over (state, not
cache, because a cache may be silently dropped and this must not be). The
file is a versioned JSON document (`serde`/`serde_json`, already a pinned
dependency) with a `schema` integer field from the first write, an ordered
`pages: Vec<Vec<Option<String>>>` of desktop-entry ids (slot-stable, `None`
for an empty grid slot so a removal does not shift every later icon), and a
fixed-length `dock: Vec<Option<String>>`. A desktop entry that has since been
uninstalled is skipped at load (slot kept, rendered empty) rather than
crashing or silently compacting the grid, so a later reinstall of the same
package restores its position. Writes are atomic (write to a sibling temp
file, then rename), the same durability convention as every other
state-bearing write this project makes to `$HOME`.

## Risks / Trade-offs

- [A second always-mapped interactive surface adds a small fixed compositing
  cost even when nothing changes] -> Home only redraws on drag/settle/pin
  changes (event-driven `dirty` flag, same convention as every other surface
  in this client); at rest it costs one static buffer already resident, no
  per-frame work, matching the "no idle redraw" requirement.
- [The focus-or-launch heuristic can mismatch a desktop-entry id to an
  unrelated running app_id] -> marked `<!-- UNVERIFIED -->`; a miss always
  falls back to the existing, already-correct launch path rather than
  focusing the wrong window silently.
- [Two written decisions about "what Home means" now exist in the repo]
  -> this proposal's own text names the exact sentence it supersedes; the
  coordinator is asked (this change does not touch that file) to add a
  superseding note to `the-handheld-presents-a-coherent-shell/design.md`'s
  decision 1 at its next revision, the same way that file's own decision 12
  already superseded decision 11 in place.
- [Rearrange-mode drag conflicts with page-swipe drag on the same surface]
  -> rearrange mode is a distinct input state (entered only via long-press,
  exited via Done/tap-empty-space); while active, the pager does not
  recognize page-swipe drags at all, matching how the drawer's own tap/drag
  disambiguation already works (`navigation.rs::pressed`/`up`).

## Migration Plan

Land this proposal, then implement `home_pager.rs`/`home_state.rs`/
`home_screen.rs` and their unit tests, then wire the new surface into
`main.rs` and `render.rs`, then the two-line `nix/card-shell/` change, then
the QEMU smoke test and evidence captures. No image identity change is
needed: the existing `.#handheld-shell-rust`, `.#card-shell`, and
`k230-coherent-shell` build the same way; Home is additive behavior inside
the already-opt-in coherent shell, not a new opt-in flag. Real-finger board
acceptance (readability, long-press feel, dark/light capture on the physical
AMOLED) is out of scope for this pass per the coordinator's explicit "don't
touch the board" instruction and remains a named open evidence gate in
`tasks.md`.
