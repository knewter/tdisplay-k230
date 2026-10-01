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

### 2. Reachable Home, Overview and Drawer

User decision, 2026-09-27: "swipe up from windows list" shows Home and
"swipe up from home" shows the app drawer. This supersedes the earlier
"keep every gesture unchanged" decision: that left Home hidden behind apps.

- App → bottom-edge swipe → Overview, preserving existing card entry.
- Overview → upward swipe from its bottom navigation area → Home.
- Home → bottom-edge upward swipe → All apps, through the existing tracked
  drawer reveal stream.
- An upward swipe beginning on a card still closes that card; a horizontal
  card swipe still browses running apps.
- Tapping a running app's Home icon focuses its existing window; launching
  an app from Home/Drawer makes the new window visible.

Userspace: the compositor owns a Home visibility state and suppresses normal
app scene layers while Home is selected, without moving/unmapping/closing
windows or changing their identities. Ordinary app focus exits that state.
Session-lock surfaces remain outside this app-layer suppression. Output
teardown restores normal scene state. Home's Rust Layer::Bottom surface
continues rendering icons and accepting its existing page/pin interactions.

The Overview-to-Home transition moves the whole Overview with the finger,
revealing Home underneath. Release settles smoothly to Home when qualified,
or back to Overview when cancelled/too short. The next swipe is a distinct
contact; the Home gesture must never accidentally open the drawer too.
Multi-touch cancels navigation without leaking part of the contact sequence
into an app or into Home. Existing card close/open and overlay escape paths
retain their ownership rules.

Rejected: closing apps, parking them in the scratchpad, or putting them on a
special workspace merely to expose Home. Those were diagnostic shortcuts,
not the user's navigation model, and would complicate launch/focus behavior.
Physical gesture proof remains UNVERIFIED until task 10's board trial.

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

### 5. App menu and deliberate icon movement

User correction, 2026-10-01: secondary click opens the app menu in mouse
mode, including supported New Window and named desktop actions, identified
running windows, and pin/unpin or rearrange actions where relevant. The
operator explicitly rejected long-press menus because that contact is how
icons are grabbed and moved. Preserve the existing long-press-to-grab flow,
drawer-to-Home dragging, dock/page placement and remove targets. Opening or
dismissing a right-click menu must not alter placement; outside click and
Escape dismiss it. Touch has no new app-menu gesture in this scope.
Rearrangement remains contextual, with Done/tap-empty exit and no permanent
navigation chrome or idle wobble animation.

### 6. GNOME activation and an explicit New Window action

Primary tap/click activates the most recently used reliably identified window
of that app, or launches through GIO desktop-entry semantics when none exists.
A missed identity match must fall back to launch, never focus an unrelated
app. Run tree/catalog/launch work off Wayland dispatch. Existing
`focus_or_launch` is a starting point, not proof of full multi-window parity.
New Window bypasses the focus shortcut. Prefer the desktop file's `new-window`
action, expose other named desktop actions through GIO, and avoid duplicate
New Window entries. A generic fresh launch is offered only when the app's
capabilities support it; honor single-window metadata and do not invent
application CLI flags. No guarantee of a second window for single-instance
applications. Select a listed running window by its verified container ID.

Reference behavior checked 2026-10-01: [GNOME Help](https://help.gnome.org/gnome-help/shell-introduction.html)
describes primary activation and an icon menu for window selection/new windows.
[Shell appDisplay](https://github.com/GNOME/gnome-shell/blob/main/js/ui/appDisplay.js)
opens the menu for long-press/secondary click.
[Shell appMenu](https://github.com/GNOME/gnome-shell/blob/main/js/ui/appMenu.js)
uses desktop actions and suppresses a duplicate generic New Window item.
These sources establish the interaction reference, not K230 hardware proof.
Rejected: always spawning on primary tap and taking long-press away from
icon movement. GNOME is the activation/menu reference, not a requirement to
copy its conflicting long-press gesture. The existing historical implementation remains until group
11 is implemented and verified.

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

## Navigation implementation follow-up, 2026-09-27

Tasks 1–9 document the first Home implementation. Task 10 now authorizes
compositor navigation changes and a reserved board trial. The older
no-board/no-gesture-change migration notes describe that original pass,
not the newly authorized navigation work. Broad task 8.1 stays open.
