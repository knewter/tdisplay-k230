# Shell polish review — September 2026

Requested by the operator: "have a design agent review our whole shell setup
and make it polished af." Scope: Home, dock, drawer, shade/quick settings,
Settings, the card overview, app switching, transitions/easing, typography,
spacing/grid, icon treatment, corner radii, elevation/scrim, theme colour
use, touch targets, and empty/error states — judged against Android 14-16 /
Material 3 Expressive and webOS, on this hardware's own terms (568×1232
portrait, RGB565, Pixman software rendering on one slow RISC-V core, touch
only, no blur, no extra full-screen passes).

## 0. What this document is and isn't

This repo already carries three prior design passes and this one does not
re-derive their findings: `docs/design/shell-ux-critique.md` (25 Sep),
`docs/design/webos-polish-review.md` (24 Sep), and
`docs/design/handheld-shell/visual-gap-audit.md`. All three were written
against slightly earlier trees. Re-reading the current source
(`feat/android-sized-cards` at base `2c838d0b`, an ancestor of
`integrate/apps-video-catalog`) found that a substantial fraction of their P0
findings are **already fixed**:

- Card header identity (`webos-polish-review.md` P0-1) — fixed.
  `card_display_title` (`nix/card-shell/adapter.c:850-868`) now resolves
  through `desktop_identity_name`, a real `.desktop` `Name=` lookup
  (`adapter.c:824-827`, cached per `app_id`), with the old 3-entry `strcmp`
  allowlist demoted to a fallback for a sandboxed build with no
  `XDG_DATA_DIRS`. A matching `desktop_identity_icon` feeds `card_icon_header`
  (`render.h:38-41`), so the card header and the drawer now share one
  resolution path.
- Dead panel space (`webos-polish-review.md` P0-2) — fixed for Settings/Themes/
  Wi-Fi. `settings_panel_h`/`content_sized_panel_h`
  (`nix/rust-shell-client/src/render.rs:1342-1361`) sizes the sheet to its
  real content bottom, clamped to `MIN_PANEL_H = 420.0` and the available
  height, for the plain controls screen, the Wi-Fi flow, and the theme
  chooser alike. Shade stays a fixed `h * 0.65` deliberately (see §5).
- Settings row spacing (`webos-polish-review.md` P0-4) — fixed. A
  `settings_row_y(index)`/`settings_layout()` helper
  (`render.rs`, referenced at `render.rs:1963-1977`) replaced the four
  hand-typed `y` literals; Power/Reboot/confirm-dialog positions are now
  derived from the same rhythm.
- Font consistency (`webos-polish-review.md` P1-1) — fixed. Both renderers
  now name the same literal, `"DejaVu Sans"`
  (`nix/card-shell/render.h:16-22`'s `CARD_SHELL_FONT_FAMILY`, `render.rs:36`'s
  `FONT_FAMILY`), with the C side's comment explicitly citing this finding.
- Singular/plural notification count (`webos-polish-review.md` P1-4, half of
  it) — fixed: `render.rs:1640-1645` now branches `"1 notification"` vs
  `"{count} notifications"`. The preview/history duplication half of P1-4 is
  **not** fixed (see §5).
- Shade drag-to-close and a stationary, smoothstep-eased dim backdrop have
  **shipped since** those documents (`tray_backdrop_alpha`,
  `render.rs:50-79`; drag-to-close evidence at
  `docs/evidence/card-shell/shade-drag-to-close/` and
  `docs/evidence/card-shell/shade-backdrop-fade/`), which is new scope none
  of the three prior documents anticipated — covered in §5.
- The overview's own card size was **already revised once**, from the
  critique's measured "8.7% peek, 46.5%-of-panel card" to the current
  50%-width/60%-height webOS-fan (`card-shell-policy.c:42-58`, comment dated
  2026-09-25, "after board/real-glass review"). This document's Part B
  supersedes that revision again, toward a larger, Android-recents-style
  card — see §6.

Findings below are new, or are prior findings **re-confirmed still open**
against the current tree with updated file:line citations. Where a finding
restates an open prior one, it is cited by ID rather than re-argued. No board
or `/dev/ttyACM0` access was used to write this document; every claim is a
direct source read of this worktree, or a captured evidence file already
committed under `docs/evidence/`. Claims about on-glass feel are marked
UNVERIFIED.

## 1. A number that changes the touch-target finding from "probably fine" to "no"

`shell-ux-critique.md` §7 flagged, as an open question, that "56 logical px"
had never been checked against Material's 48dp/~9mm guideline at this panel's
*actual* density. It is now checked:

- Panel: 568×1232 px, 4.1″ diagonal (`openspec/config.yaml`'s own hardware
  description).
- Diagonal pixels: `sqrt(568² + 1232²) = 1356.6`.
- Density: `1356.6 / 4.1 = 330.9` **ppi**.
- This shell renders at output scale 1 — one logical pixel is one physical
  panel pixel (`openspec/specs/runtime/shell/spec.md`, cited already in
  `shell-ux-critique.md` §7).
- The shell's own "≥56 logical px" bar (`specs/runtime/handheld-shell-design/spec.md:9`)
  is therefore **56 / 330.9 inch = 4.3 mm** physical, not "a comfortable
  margin above 48dp." Material's own stated target is "a physical size of
  about 9mm regardless of screen size."

**56px on this panel is under half of Material's target**, because the
reference 48dp/9mm figure assumes a ~160dpi baseline device, and this panel
is unusually dense (330.9 ppi) with no compensating output scale. This is not
a cosmetic nit: at 4.3mm, adjacent controls (e.g. the Settings `−`/`+`
brightness stepper, `render.rs:1949-1958`, or the drawer's 56×56 minimum tile,
`navigation.rs:243`) sit close to typical fingertip-contact-patch size,
raising real mis-touch risk, not just a "could be a little bigger" aesthetic
complaint.

**Fix, in two tiers:**
- Quick win: raise the shell's own minimum from 56 to **96 logical px**
  (96/330.9in = 7.4mm — still short of 9mm but a 71% improvement, and cheap:
  it changes one constant plus whatever fixed layouts assume 56px rows).
- Structural: reaching literal 9mm needs ~120 logical px targets, which does
  not fit today's Settings row height (110px) or drawer tile pitch (160px)
  without a broader relayout — track as its own task, not a quick win.

**Cost:** zero per-frame cost; this is a layout-constant change, not a
rendering-cost change. **Priority: P1** (newly quantified; previously
UNVERIFIED).

## 2. Home and the dock

**Grid.** `nix/rust-shell-client/src/home_grid.rs`: 4 columns
(`COLUMNS = 4`, matching this panel's ~1:2.17 aspect to "the same 4-column
density most phone launchers settle on," `home_grid.rs:9-14`), `ROW_HEIGHT =
184.0` fixed pitch, 5 rows fit at 1232px height, `SIDE_MARGIN = 22.0`,
`TILE_GAP = 18.0`. This is a reasoned, already-documented grid (the module's
own header comment cites the icon-cache-size coincidence: 4×5 + 4-slot dock =
24, exactly `icon.rs::CACHE_LIMIT`) — no P0/P1 finding against the grid
math itself.

**Dock.** `DOCK_SLOTS = 4`, deliberately equal to `COLUMNS` so dock icons
align under grid columns (`home_grid.rs:15-18`), rendered as a translucent
themed tray (`render.rs:2316-2327`, `service_card(..., "launcher", ...)`
reusing the same rounded-panel primitive as Drawer/Shade/Settings — good
reuse, no separate one-off dock-chrome code path). Android's Pixel Launcher
hotseat is visually near-identical in concept (a fixed row of app icons on a
translucent scrim, independent of which Home page is showing) — no
divergence worth flagging.

**Finding: dock and grid tiles share the icon-plate primitive, but the dock
tray's corner radius has not been checked against the new card radius
token (§6).** Once §6's token set lands, confirm `service_card`'s existing
`16.0` (`render.rs:424`) is deliberately smaller than the new card radius
(24-28px) rather than an accidental mismatch — panels and cards are
different visual weights and *should* use different radii, but the token
table in §11 should say so explicitly rather than leave it implicit.
**Priority: P2. Quick win** (a one-line comment plus confirming the token
table, no code change expected).

**Empty state:** not applicable — Home always shows at least the dock; no
finding.

## 3. The drawer

Grid layout is decent and already improved past `visual-gap-audit.md`'s
stale seven-row-list finding: `COLUMNS = 3`, `ROW_HEIGHT = 160.0`,
`TILE_HEIGHT = 148.0` (`navigation.rs:4-6`), continuous drag/flick/coast
scrolling, tested minimum tile 56×56 (`navigation.rs:243` — now also subject
to §1's finding). `panel_travel_height` gives the Drawer a fixed `h * 0.81`
reveal fraction (`render.rs:1379`), distinct from Settings' content-sized
approach — reasonable, since a drawer is inherently a "fill the space"
scrollable list, not a short card.

**Finding: drawer corner treatment is per-tile only; the drawer sheet itself
has no visible top-corner rounding distinct from Settings/Shade.** All three
overlays share one `rounded(cr, ..., 16.0)` call for their sheet background
(`render.rs:1416-1474`), which is consistent, not a bug — flagged only so
§11's token table records it as the deliberate "sheet corner" token
(distinct from "card corner," §6) rather than leaving two different radius
constants (16 here, 24-28 for cards) undocumented as tokens.

**Search remains deferred, by explicit prior decision** (
`the-handheld-presents-a-coherent-shell/design.md` decision 2, restated in
`shell-ux-critique.md` §4). Not re-opened here per this repo's own
"record what was rejected and why" discipline — flagged only as a
**recommendation, not a requirement**, exactly as the prior document left it.

## 4. Settings

P0-2 (dead panel space) and P0-4 (row spacing) are fixed (§0). Remaining,
newly-confirmed-still-open finding from `shell-ux-critique.md` §8:

**Settings' capability rows still have no pressed-state feedback.** Checked
directly against the current `Route::Settings` paint block
(`render.rs:1877-1958`): the row loop draws `service_card(...)` with a fixed
`selected` argument of `false` for every row — there is no per-row `pressed`
parameter at all, unlike the drawer (`DrawerNavigation::pressed`,
`navigation.rs:211-221`) or Home grid (`home.pressed(...)`, `main.rs:2429`).
A tap on Wi-Fi/Brightness/Keyboard/Motion gives zero visual acknowledgement
until the resulting screen actually changes. Given this device has no
haptics (confirmed absent in hardware, `motion-research.md`), visual press
feedback is the *only* feedback channel — this is a real P1, not cosmetic.

**Fix:** thread a `pressed: Option<usize>` row index into the `Route::Settings`
arm (the function already threads a `pressed: Option<usize>` parameter for
Home, `render.rs` signature at `scene(...)`) and pass `selected: pressed ==
Some(index)` into each row's `service_card` call, matching the pattern
`navigation.rs` already demonstrates. **Cost:** free — `service_card` already
branches on a boolean; this reuses the existing selected-brush tint, no new
draw call. **Effort: quick win** (bounded to `service_ui.rs`'s Settings tap
handling plus this one render.rs loop).

**Wi-Fi error banner:** `webos-polish-review.md` P0-3 is unresolved (spot
checked: `render.rs`'s `paint_wifi`, around the error-text call near
`w - 84.0` band still reads as a plain colored line, not an elevated banner)
— re-filed here at the same priority (P1) rather than re-derived; still
owned by that document, not new scope for this one.

## 5. The shade and quick settings

The shade has changed materially since the last two documents: it now has
**drag-to-close both ways** (panel drag, backdrop drag, or backdrop tap all
close it) and a **stationary, smoothstep-eased dim backdrop** tied to reveal
fraction (`tray_backdrop_alpha`, `render.rs:50-79`, a `3p² - 2p³` ease-in-out
curve; evidence at `docs/evidence/card-shell/shade-backdrop-fade/` and
`shade-drag-to-close/`). Both are genuine, already-good motion work — no
finding against either. This section compares what's left against Android
14-16's two-stage shade (first pull: compact quick-setting tiles + notification
list; further pull: expanded tiles + a brightness slider), per surface the
coordinator asked to be covered explicitly.

**Tile grid: does not exist.** There are no quick-settings tiles in the
shade at all today. `Route::Shade`'s paint block (`render.rs:1625-1874`)
draws exactly: a title, a notification-count line, a preview card, and a
scrolling history list. Brightness (`ServiceRequest::Brightness`) and
keyboard toggle (`ServiceRequest::KeyboardToggle`) exist only inside
`Route::Settings` (`render.rs:1913-1958`), one full navigation hop away —
already flagged in `shell-ux-critique.md` §5 as P1, still open, re-confirmed
against current line numbers. **This is the single highest-leverage shade
gap:** Android's Quick Settings puts the 4-8 highest-frequency toggles
(Wi-Fi, Bluetooth, brightness, flashlight, do-not-disturb, airplane mode) one
pull away from notifications; this shell requires leaving the shade entirely.

**Brightness slider: none.** Settings has a discrete `−`/`+` stepper
(`render.rs:1949-1958`), not a drag slider. Android's Quick Settings shade
puts a full-width brightness slider directly under the clock/tile grid on
every pull. A slider is a strictly *cheaper* per-frame draw than a stepper
with two extra tap targets (one filled rounded-rect track plus one circular
thumb vs. two separate hit-tested glyphs) and reads as more "expressive" —
recommend moving brightness into the shade as a slider, not just copying the
stepper over.

**Clock/date header: none.** The shade opens straight into
`"Notifications"` / notification count (`render.rs:1499-1507`) with no
time/date. Android's shade header is anchored by a large clock the moment
you pull down, before any tile or notification content — it is the
single largest, most legible piece of text on the whole surface and doubles
as a "yes the pull registered" confirmation independent of any list content
loading. Cheap to add (one more `heading()` call, already-decoded system
time, no new asset) and high value on a device with no separate lock/status
screen.

**Notification cards.** Confirmed: per-item swipe-to-dismiss exists
(`notification_swipe_release`, referenced `render.rs:4483-4532` test),
dismiss-all exists (`ServiceRequest::NotificationDismissAll`), grouping by
source does **not** exist (flat chronological list, `NotificationSnapshot`) —
same as `shell-ux-critique.md` §5's P2 finding, re-confirmed, still correctly
P2 given this device's bounded app set (no third-party app store).
**Clear-all affordance:** present as a text action, not (checked) a distinct
button treatment separate from ordinary row text — worth a quick visual pass
once §11's tokens land, not filed as its own numbered finding.

**Empty state:** `"No new notifications"` (`render.rs:1728`) — present,
plain text, no icon/illustration. Android's empty Quick Settings/shade state
uses a small illustrated glyph, not load-bearing for function but a common
"polish" signal. **P2, quick win:** pair the existing string with the same
icon-badge primitive `card_icon_badge`/`card_icon_header` already provide on
the C side, or a Rust equivalent, rather than inventing new asset infra.

**Handle affordance.** A pill handle already renders for Drawer and Shade
(`rounded(cr, w/2.0-36.0, panel_y+11.0, 72.0, 6.0, 3.0)`, `render.rs:1494-1495`)
— 72×6px, radius 3. This is on the small side next to Android's typical
~32×4dp handle scaled to this density, but it is a decorative affordance,
not a hit target (the whole panel/backdrop drags), so this is **P2 at most**
and arguably fine as-is — flagged only so a reviewer doesn't conflate it with
the real touch-target problem in §1.

**Theme colour use.** The shade reuses the `"notifications"` theme section
for its panel background/border (`render.rs:1453`), consistent with the
Drawer's `"launcher"` and Settings' `"controls"` sections — this is the
right pattern (one themed section per surface) and not itself a finding.
`shell-ux-critique.md`'s P1-5 (opaque pre-fill guarding only `Route::Drawer`,
risking ghosting through a translucent `notifications.background` alpha)
is **re-confirmed still open**: `render.rs:1463-1474`'s route match still
lists `Route::Drawer | Route::Shade | Route::Settings` together for the
*rounding* clip but the opaque pre-fill mentioned in that finding needs a
direct re-check against the current line numbers before this document
would call it fixed — treat as open, not verified fixed, pending a closer
read; not re-derived fully here to avoid scope creep into that document's
own territory.

**Recommendation: adopt a two-stage pull, but only the header/tile half, not
a second full expansion.** On a panel this narrow (568px) a 4-6 column tile
grid has enough width for 3-4 columns of ~120px square tiles with labels —
workable, but a *second* expansion stage (Android's "tap the chevron for
more tiles") adds a second gesture recognizer and a second content-height
class for marginal benefit on a device with a small, fixed app/toggle set
(this is a personal handheld, not a multi-user phone with dozens of OEM
tiles). **Recommended shape:** one pull, one shade, with (top to bottom)
clock/date header → a single row of 4 always-visible toggle tiles (Wi-Fi,
Brightness-as-slider-or-tile-that-opens-the-slider, Keyboard, Motion — the
same four capabilities Settings already exposes, matching control names 1:1
so nothing new needs a settings-data plumbing change) → the existing
preview/history notification list. This reuses `settings.network` /
`settings.brightness` / `settings.keyboard` / `settings.motion`
(`render.rs:1908-1912`) as the tile data source directly — no new service
plumbing, only new paint code and touch routing in `service_ui.rs`.
**This is Medium effort, not a quick win** (new layout, new hit-testing,
new tile chrome) and is out of scope for this branch's implementation
commit; recorded here for a follow-on change.

**Shade quick wins to fold into this branch's implementation commit** (per
the coordinator's instruction, radius/spacing/type consistent with the card
work): none of the shade-specific gaps above are pure token fixes — the
clock header and tile grid are new layout, not radius/spacing corrections.
The one true token-only quick win is Settings' pressed-state gap (§4), which
is not shade-specific. **Decision: no separate shade quick-win commit; the
shade's real gaps (tiles, slider, clock) are Medium/structural new layout,
correctly listed here rather than implemented ad hoc alongside a card-radius
change.**

## 6. The card overview / recents and app switching

This is the section Part B implements. Current state before this change,
confirmed by direct read (`nix/card-shell-policy/card-shell-policy.c:42-58`,
`nix/card-shell/adapter.c:2306-2334`):

- `card_width = 0.5 * width` = 284px (50% of panel width).
- `card_height = 0.6 * height` = 739.2px (60% of panel height).
- `gap = 10`, giving a neighbour peek of `568 - ((568-284)/2 + 284 + 10) =
  132px`, 46.5% of a neighbour's own width — already legible (a large
  improvement on the critique's originally-measured 8.7%), confirmed
  visually in `docs/evidence/card-shell/webos-fan-switcher/dark-01-overview.png`.
- Card corner radius: **8px**, on the content-aspect-fit "plate"
  (`CARD_PLATE_RADIUS`, `adapter.c:172-179`), not the full deck slot — this
  is already the right *mechanism* (a cached, per-size rounded-rect texture,
  §6.1), just too small a radius for a card this size, and the card itself
  is far smaller than Android's recents metaphor.

**Gap versus the user's explicit ask ("more like Android does"):** Android's
recents carousel shows the focused task at roughly 80-85% of the panel
width, phone-aspect-ratio, with only slivers of neighbours visible at the
screen edges — a fundamentally different proportion than this shell's
current 50%-width "3-up fan," which is closer to a card-sorting view than a
recents view. Part B below resizes to match.

### 6.1 How the rounding is implemented, and why it's already the right mechanism

`card_plate_scene` (`nix/card-shell/render.c:316-349`) rasterizes a rounded,
optionally-stroked rect **once** into a Cairo ARGB32 surface at the plate's
exact pixel size, wrapped as a `wlr_scene_buffer`. `card_background`
(`adapter.c:1130-1156`) only rebuilds that buffer when the plate's brush,
width, or height actually changes (`memcmp`/size comparison,
`adapter.c:1134-1135`) — every other frame it is reused as-is from the scene
graph, with no per-frame Cairo work and no per-pixel software masking. This
is exactly the "compute once per card size and cache" technique the task
asks for, and it already exists — Part B's job is to widen its use (bigger
radius, radius that interpolates during transitions) without changing this
caching discipline.

### 6.2 Deck ordering and empty state

No P0/P1 finding beyond what §3 of `shell-ux-critique.md` already recorded
(card order stability UNVERIFIED without a host trace; empty state
`"No running apps"` present and reasonable). Not re-derived.

### 6.3 Transitions and easing — the one real motion gap

**Card expand/collapse is still a fixed-duration linear ramp.**
`card-shell-policy.c:692-707` (`cs_tick`, `CS_EXPANDING`):

```c
double duration=p->config.reduced_motion ? 60 : 160;
...
p->expand_progress=fmin(1,elapsed/duration);
```

`elapsed/duration` clamped to 1 — linear, no easing curve, no velocity
carry-in. This sits next to a *different*, already-good physics model in the
same file: the horizontal scroll coast uses an exponential-decay omega model
(`cs_tick`'s scroll branch, `card-shell-policy.c:632-660`,
`omega=p->config.reduced_motion?.12:...`) and the two-axis entry-drag settle
carries real release velocity (`entry_release_velocity_x`/`_progress`,
referenced throughout `card-shell-policy.c`). **Re-confirmed still open**
from `shell-ux-critique.md` §6, same file:line region, unchanged since that
document. **Priority: P1. Fix:** reuse the entry-drag's velocity-aware
settle model for `CS_EXPANDING` instead of a bare linear timer, so
tap-to-expand feels like the same physical system as the drag gestures.
**Cost:** identical CPU cost class to the current linear tick — both are one
`fmin`/exponential evaluation per frame, not a rendering-cost change.
**Not implemented in this branch's Part B** (task 3 only adds radius
interpolation to the existing linear/pad-driven progress, it does not
replace the timing curve) — recorded here as the next motion task.

## 7. Typography scale

No named type ramp exists on either renderer; sizes are ad hoc per call
site. Directly observed sizes across `render.rs`: 14 (fine-print
detail/support text), 16 (Wi-Fi error text), 17 (settings row label), 19
(secondary/medium text), 20 ("Done" action, control values), 25 (brightness
±), 28 (section headings/eyebrows), 40 (large headings/titles). That is
**eight distinct sizes with no documented relationship between them** — not
a type scale, a collection of values that happened to look right at their
one call site. §11 proposes a five-step ramp that collapses these to a
modular scale and names which existing call site maps to which step.

## 8. Spacing and grid

No shared spacing scale exists; margins/paddings are independent literals
per surface: Home's `SIDE_MARGIN = 22.0`/`TILE_GAP = 18.0`
(`home_grid.rs:20-21`), the deck's `inset = 24`/`gap = 10`
(`card-shell-policy.c:44`), Settings' row gap implied by `settings_row_y`'s
formula, the shade's fixed offsets (`panel_y + 44.0`, `+ 76.0`, `+ 130.0`,
`render.rs:1510-1530`). None of these are wrong individually — each was
clearly reasoned about at its own call site — but there is no single spacing
scale a new surface could be built against without inventing its own
numbers again. §11 proposes one.

## 9. Icon treatment

Already covered accurately by `webos-polish-review.md` P2-2 (icon rendering
is fine, vector-crisp via librsvg, not re-derived) and now further improved
by the card-header desktop-entry resolution fix (§0). One residual gap
**worth naming as new, since neither prior document could see it before the
fix landed**: `card_icon_header`'s fallback letter-badge path
(`card_icon_badge`, `render.c:143-176`) and the drawer's own fallback badge
(`icon.rs`) are two independently-implemented letter-badge painters — same
visual idea (rounded square, tinted background, one capital letter), two
code paths, one in Cairo/C, one presumably in the Rust `icon.rs` module.
Not a visible defect (both look the same in practice per available
evidence) but worth a token/consistency note: if the badge's tint or corner
radius ever changes, both places need the same edit by hand. **P2, quick
win only if both are touched for another reason** — not worth a standalone
task today.

## 10. Elevation, scrim, theme colour use

**Scrim:** the shade's `tray_backdrop_alpha` (§5) is the shell's only true
scrim — a smoothstep-eased fade to a target alpha of `0.35`
(`render.rs:79`, `tray_backdrop_alpha(progress, 0.35)`) shared by
`Route::Settings | Route::Shade` (`render.rs:76`). The Drawer has no
scrim of its own (it fills the space rather than floating over dimmed
content) — consistent with its "browse everything" role, not a finding.
**No elevation (shadow) anywhere** — reasonable given the "no blur, cheap
per-frame" hardware constraint; a flat stroke rim (already used on card
plates, `CARD_PLATE_STROKE_*`, §6.1) is the correct cheap substitute for a
drop shadow on this hardware, and is already the chosen technique. No
finding — recorded so a future reviewer doesn't propose adding a real blur
shadow, which the user has already rejected.

**Theme colour use:** each surface pulls its brush from its own named theme
section (`"launcher"`, `"notifications"`, `"controls"`, card `card`/
`selected`), which is the right shared-token architecture — Omarchy themes
supply colours, the shell supplies structure. `shell-ux-critique.md` P1-5's
translucency-ghosting risk (§5, re-flagged above) is the one open theming
defect; no new theme-colour finding beyond that.

## 11. One consistent design-token set

Proposed names, values, and homes. "Shared home" means the literal value (or
a generated header/const module) both `nix/card-shell/*.c` and
`nix/rust-shell-client/src/*.rs` read, so the two renderers cannot drift the
way font family already had to be fixed once (§0).

| Token | Value | Where it lives today | Where it should live |
| --- | --- | --- | --- |
| `radius.sheet` | 16px | `render.rs:424` (`service_card`'s `rounded(...,16.0)`) | keep as the Rust-side overlay-sheet radius; document as distinct from `radius.card` |
| `radius.card` | 24-28px (this change: see Part B) | `CARD_PLATE_RADIUS`, `adapter.c:172` | same constant, raised; cite from both this doc and the change's `design.md` so the two numbers (16 vs 24-28) read as deliberate, not drifted |
| `radius.chip` | 12px | palette swatches, `render.rs:434` | keep, already proportional to its own small scale |
| `radius.badge` | full circle (`size/2`) | `card_icon_badge`, `render.c:150-158`; drawer `icon.rs` fallback | keep; note both call sites in one comment (§9) |
| `spacing.xs` | 8px | ad hoc | new shared constant |
| `spacing.sm` | 16px | Home `TILE_GAP` (18, round down), deck `gap` (10, round up) | reconcile the two nearby values (10/18) toward this one shared step where a surface is rebuilt anyway; not a forced mass edit |
| `spacing.md` | 24px | deck `inset`, Home `SIDE_MARGIN` (22, round up) | shared constant |
| `spacing.lg` | 48px | edge_band, several panel offsets | shared constant |
| `type.detail` | 14px | scattered | step 1 of the ramp |
| `type.body` | 17-19px (reconcile to 18px) | row labels, secondary text | step 2 |
| `type.action` | 20-21px | buttons/values (reconcile) | step 3 |
| `type.heading` | 28px | section eyebrows | step 4 |
| `type.display` | 40px | large titles | step 5 |
| `motion.duration.fast` | 100ms | `reduced_motion` scroll/entry durations | already the reduced-motion floor; keep |
| `motion.duration.standard` | 160-240ms | `CS_EXPANDING` (160), entry snap (240) | reconcile toward one value once §6.3's velocity-aware rewrite lands |
| `motion.curve.standard` | `3p²-2p³` smoothstep | `tray_backdrop_alpha`, `render.rs:57-75` | promote from shade-only to the shared curve every progress-driven fade uses, including radius interpolation (Part B task 3) |
| `motion.curve.spring` | velocity-aware exponential decay (`omega` model) | `cs_tick`'s scroll/entry branches | the target curve for §6.3's future expand/collapse fix |
| `scrim.alpha` | 0.35 | `tray_backdrop_alpha(progress, 0.35)` | shared constant once a second surface (e.g. a shade tile grid) needs the same scrim |
| `touch.min` | 56px today → 96px quick win → 120px structural (§1) | scattered `>=56`/`56.0` literals | shared constant, both sides |

**Where tokens should physically live:** neither renderer currently reads a
shared token file — colours already flow C↔Rust through the Omarchy
appearance/theme transport (`card_appearance`/`AppearanceSnapshot`), which is
the existing precedent for "one source, two consumers." The lowest-risk next
step, **not implemented in this branch** (structural, its own change): add a
small generated header (`nix/card-shell-policy/card-shell-tokens.h`, plain
`#define`s) plus a matching Rust `const` module
(`nix/rust-shell-client/src/tokens.rs`) built from one source-of-truth file
(e.g. a small TOML or the existing Nix module) at build time, mirroring how
`CARD_SHELL_FONT_FAMILY` already had to be manually kept in sync across two
files — automate that sync once, rather than re-discover font-family-style
drift for every future token.

## 12. Priority table

| # | Finding | Group | Priority | Cost on this hardware |
| --- | --- | --- | --- | --- |
| 1 | Touch targets are 4.3mm physical (330.9ppi × 56px), well under Material's ~9mm | Global | P1 | Layout-constant only, zero render cost |
| 2 | Overview card is 50%-width webOS-fan, not Android-recents-sized | Overview | P0 (user's explicit ask) | See Part B — one-time layout recompute, no new per-frame cost |
| 3 | Card radius is 8px, too small for the new card scale | Overview | P0 (user's explicit ask) | Cached rounded-rect texture, unchanged cost class |
| 4 | Card expand/collapse motion is linear, not velocity-aware like the rest of the deck | Overview/motion | P1 | Same cost class as today's linear tick |
| 5 | Settings capability rows have no pressed-state feedback | Settings | P1 | Free — reuses existing selected-brush branch |
| 6 | No quick-toggle tiles in the shade; brightness/keyboard need a full hop to Settings | Shade | P1 | Medium — new layout + hit-testing, not this branch |
| 7 | No clock/date header in the shade | Shade | P1 | Quick win, not this branch (bundled with #6's layout work) |
| 8 | Brightness is a stepper everywhere, not a slider | Settings/Shade | P2 | Medium — new touch model |
| 9 | Wi-Fi error banner still buried (webos-polish-review P0-3) | Settings | P1 (existing) | Not re-scoped here |
| 10 | Translucency ghosting fix may not cover Shade/Settings (webos-polish-review P1-5) | Shade/Settings | P1 (existing, re-flagged) | Needs a direct re-check, not re-derived here |

## 13. Quick wins / medium / structural

**Quick wins (≤1 day each):**
- #5 Settings row pressed-state (§4).
- §1's 56→96px minimum touch-target bump, where it doesn't collide with a
  fixed row/tile height that would need its own relayout.
- §5's shade empty-state icon pairing.
- §11's token-table documentation itself (no code change) plus reconciling
  the two near-duplicate spacing literals called out there, *where* a
  surface is being touched for another reason anyway (not a forced sweep).

**Medium (this class of change, not necessarily this branch):**
- #6/#7 shade tile grid + clock header (§5) — new layout and touch routing,
  reusing existing `settings.*` control data, no new service plumbing.
- #4 velocity-aware expand/collapse motion (§6.3) — reuses an existing
  model in the same file, but needs its own real-finger acceptance pass.
- Structural 120px touch-target pass (§1) for whichever rows/tiles don't fit
  96px without a relayout.

**Structural:**
- A real shared token source (§11's generated-header-plus-Rust-const
  proposal) rather than hand-synced literals.
- §8's Wi-Fi error banner elevation (owned by `webos-polish-review.md`).
- Any future stacked-recents/"card groups" work is explicitly out of scope
  (no evidence this shell has multi-window-per-app today, per
  `shell-ux-critique.md` §3's LuneOS note).

## 14. What still needs the board

| Finding | Decidable from source alone | Needs board/glass |
| --- | --- | --- |
| §1 touch-target physical size | yes — direct arithmetic from the panel's own stated diagonal/resolution | confirming actual mis-touch rate is a real-finger question, not assumed from the math alone |
| §4 Settings pressed state | yes | none beyond normal visual review once added |
| §5 shade tiles/clock/slider | yes (absence is a grep) | discoverability/reachability of a new tile row needs a real-finger pass once built |
| §6 card resize + radius (Part B) | yes for the geometry; screenshots below are host/QEMU | real-finger flick-through-multiple-cards feel, per this repo's own evidence discipline for gesture changes |
| §6.3 expand/collapse motion | yes — direct code contrast, unchanged in this branch | not evaluated in this branch; deferred |

None of the above claims a physical/optical/real-finger pass. Per `AGENTS.md`,
Part B's implementation records which evidence class (host build, QEMU,
injected event) it actually obtained, and leaves the real-glass gesture-feel
acceptance explicitly open.
