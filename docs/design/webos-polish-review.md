# webOS polish review — 24 September 2026

An informal comparative review requested outside the OpenSpec workflow: how does
the installed handheld shell compare with Palm/HP webOS's visual craft, and
where is ours less than perfectly polished. This is **not** the formal
`the-handheld-gets-a-design-and-ux-review` change (active, owned by a separate
worktree, with its own rubric and `docs/research/handheld-ux/review-round-2/`
artifacts) and does not duplicate its scope or task IDs. It also does not
replace [`docs/design/handheld-shell/visual-gap-audit.md`](handheld-shell/visual-gap-audit.md)
(24 September, same day) — it corrects one of that audit's framings (below),
adds webOS-specific reference points with citations, and adds several
code-grounded findings that audit did not cover. A coordinator folding this
into the formal review round should treat it as raw input for
`references-and-gap.md` and `findings.md`, not a finished replacement.

No board or `/dev/ttyACM0` access was used. Every finding below is grounded in
either a committed capture under `docs/evidence/` (with its date and source
commit checked against `git log` and `git merge-base`) or the current
`origin/master` source tree read-only. No source file was edited to produce
this review.

## 0. A correction: which deck chrome is "ours" right now

Several evidence directories show **three different generations** of the live
card deck's title/status chrome, and conflating them changes the review's
priorities:

1. **Oldest** — a permanent top tab bar (`Apps / Windows / Keyboard / System`)
   plus `Previous / Next / Back / Close` buttons. Visible in
   `docs/evidence/launcher-gestures/edge-states/*.png` and
   `docs/evidence/card-shell/board-first-trial/*.png`. This is exactly the
   permanent Back/Home/pagination chrome the user has already rejected; it
   survives only as inert legacy code, never the default.
2. **Middle** — `"Cards"` title, `"Tap to return. Swipe up to close."`
   subtitle, and a `"Selected: …"`-prefixed card label, with
   `Previous / Next / Close` buttons. This is the **rollback session**
   (`SWAY_K230_CARD_TOUCH_FIRST` unset/`0`), defined in
   `nix/card-shell/adapter.c:773-834` (`rebuild_chrome`, else-branch) and
   `nix/card-shell-policy/card-shell-policy.c:692-707` (`cs_message_text`,
   whose strings still say "Use Windows or Back" — leftover text for a bar
   that mode doesn't draw, but is at least never shown outside the rollback
   path). It appears in `docs/evidence/coherent-shell/real-theme-paired-qemu/*`,
   `docs/evidence/coherent-shell/themed-installed/deck.png` and
   `docs/evidence/omarchy-themes/board-switching/*.png`.
3. **Current default** — `"Home"` title, a status cue only when relevant, and
   `"Swipe up for apps"`, with no buttons at all. This is
   `nix/card-shell/adapter.c:786-808` (`rebuild_chrome`, `touch_first()`
   branch). `nix/shell.nix:830-863` sets
   `SWAY_K230_CARD_TOUCH_FIRST = "1"` unconditionally whenever
   `cfg.coherentShell` is enabled — i.e. this **is** the shipped path, not an
   opt-in extra. Confirmed reachable in
   `docs/evidence/omarchy-themes/community-board-fixed/community.png` (source
   `3c502a37`, an ancestor of current `origin/master` `a68014de`), where the
   deck's top strip peeking above the drawer reads `"Home"`, not `"Cards"`.

Generation 2 predates generation 3 by a handful of commits the same day
(`git merge-base --is-ancestor` confirms `f4952fc2` "Quiet touch-first deck
chrome and card labels" — which introduced generation 3 — is an ancestor of
`3c502a37`, while `board-switching`'s source `df2c34b1` and
`real-theme-paired-qemu`'s source predate `f4952fc2`). **Practical effect:**
`visual-gap-audit.md`'s P0 finding #1 ("oversized generic `Cards` title,
procedural subtitle, `Selected: shell@…` line") was written against
generation 2 evidence. That specific title/subtitle text is already gone from
the shipped default. The underlying problem — an unbounded raw client window
title used as the card's only identity — is **not** fixed, just relabeled; see
finding P0-1 below, re-scoped to the actual current code path.

Recommendation for evidence hygiene (P2, process not code): recapture the deck
under an explicitly touch-first build before relying on any deck screenshot in
future polish reviews, and consider whether generations 1–2 should be pruned
once the physical acceptance gates for generation 3 (openspec tasks 5.1–5.3 of
`the-handheld-presents-a-coherent-shell`) land, per AGENTS.md's "close
deliberately" guidance.

## 1. What ours actually looks like today

Evidence below is all dated 24 September 2026 (today) and each source commit
was checked with `git merge-base --is-ancestor <source> a68014de` against the
current `origin/master` head; captures whose source is **not** an ancestor of
master are marked so and treated as historical/branch-local, not "current."

| Surface | Best current capture | Source commit | On master? |
| --- | --- | --- | --- |
| Deck (touch-first, peeking above drawer) | `docs/evidence/omarchy-themes/community-board-fixed/community.png` | `3c502a37` | yes |
| Drawer (icon grid, real board, dark) | same capture | `3c502a37` | yes |
| Drawer (icon grid, synthetic, dark/light) | `docs/evidence/omarchy-themes/board-switching/{dark,light}.png` | `df2c34b1` | yes (predates the "Home" quieting, deck strip is stale — drawer itself is current) |
| Settings / Themes / Theme preview / Shade (host, dark+Latte) | `docs/evidence/coherent-shell/rust-visual-themes-host/{dark,latte}/*.png` | `f9978fe6` | not checked as ancestor of `a68014de` (divergent branch state); Rust chrome code for these routes is unconditional (no `touch_first` gate) so the *screens themselves* are representative even if the exact commit isn't on master |
| Theme preview with a real decoded still | `docs/evidence/omarchy-themes/portrait-preview-host/preview.png`, `docs/evidence/omarchy-themes/theme-preview-host/catppuccin-preview.png` | host fixture | code path confirmed live in `render.rs:405-520` |
| Wi-Fi list / detail / password entry | `docs/evidence/wifi-settings/paired-qemu/*.png` | paired QEMU, same day | representative (`nix/rust-shell-client/src/wifi_ui.rs`/`render.rs` `paint_wifi`, unconditional) |
| Notification shade with many items, scrolled | `docs/evidence/coherent-shell/notification-history-motion-qemu/{initial,scroll-stable}.png` | `0a414434` | representative |
| App icons in the drawer | `docs/evidence/coherent-shell/rust-icons-host.png` | host fixture | representative (SVG-based decode, see §2) |
| On-screen keyboard | `docs/evidence/keyboard-gestures/{native-qemu,supervised-installed}/*.png` | same day | representative |

## 2. Where ours is not yet polished

Findings are ordered P0 (obviously broken or ugly) → P1 (noticeably
unpolished) → P2 (refinement). Each names the screen/capture, the webOS
reference point, the concrete fix, and the code location.

### P0-1 — Card header shows the raw client window title, not the app's name

**Screen:** live card / expanded app header, all themes.
**Capture:** `docs/evidence/coherent-shell/themed-installed/deck.png` (shows
`"Selected: shell@nixos: ~"` — generation-2 chrome, but the underlying title
source is identical in the current generation-3 path, minus the `"Selected: "`
prefix).
**Code:** `nix/card-shell/adapter.c:364-376` (`card_display_title`) maps only
three hardcoded `app_id` strings to friendly names —
`k230-terminal`→`"Terminal"`, `k230-monitor`→`"Monitor"`, `nnn`→`"Files"` — and
falls through to the client's own `title` (e.g. a shell prompt like
`shell@nixos: ~`, which changes as the user types) for every other app. That
raw string is then squeezed into a fixed-width, ellipsized label at
`adapter.c:709-716` (`label_update`, height 44/font 24 in the current compact
mode).
**webOS reference:** a card's header always showed the app's *name* paired
with its icon (from the app's manifest), never the live content of the window
underneath — a terminal card read "Terminal," not whatever the shell prompt
currently said.
**Fix:** resolve the card header the same way the drawer already resolves
`.desktop` entries (task 1.4 of `the-handheld-presents-a-coherent-shell`) —
i.e. `app_id → .desktop Name/Icon` — instead of a 3-entry `strcmp` allowlist,
and put a small icon glyph next to the name in the header (matching the
drawer's icon+label pattern), so an app whose `app_id` isn't one of the three
special-cased strings doesn't silently regress to raw window-title text. This
is inside the existing open scope of tasks 1.4/4.2; call it out explicitly
when picked up.

### P0-2 — Secondary panels fill the full screen height regardless of content, leaving large dead voids

**Screens:** Settings, Themes list, Theme preview, Wi-Fi (list/detail/error),
Notifications shade.
**Captures:** `docs/evidence/coherent-shell/rust-visual-themes-host/dark/settings.png`
(content ends ~35% down, remaining ~65% flat `#1e1e2e`-ish fill),
`.../dark/themes.png` (two rows of content, ~90% of the panel empty),
`docs/evidence/omarchy-themes/theme-preview-host/catppuccin-preview.png` (one
row of content below the preview image, ~55% empty),
`docs/evidence/wifi-settings/paired-qemu/wifi-list-dark.png` (four rows, ~55%
empty), `docs/evidence/coherent-shell/notification-history-motion-qemu/scroll-stable.png`
(even scrolled mid-way through 12 real rows, the area below the shade's own
65%-height cap is a flat, undifferentiated dark fill all the way to the
bottom edge, not a dimmed peek of anything).
**Code:** `nix/rust-shell-client/src/render.rs:1061-1070`:
```rust
let panel_y = if route == Route::Drawer { h * 0.19 } else { 0.0 };
let panel_h = if route == Route::Shade { h * 0.65 } else { h - panel_y };
```
Every non-Shade route (`Drawer`, `Settings`) always fills the *entire*
remaining height with the panel background, no matter how short its content
list is; `Shade` is capped at a fixed 65% regardless of content too. There is
no "size to content, cap at a maximum, show the deck behind for the rest"
behavior anywhere in this function.
**webOS reference:** webOS's Dashboard/notification area and the app-menu
overlays were always sized to their content, floating over the (dimmed) card
stack — never a full-bleed sheet of empty color. The archived HP webOS
developer notification guide describes brief banners followed by a
content-sized dashboard, not a full-screen panel.
**Fix:** compute `panel_h` from actual content extent (row count × row height
+ chrome), clamped to a sane minimum and maximum, and use the freed space to
show the deck/wallpaper behind, dimmed, consistent with what the `Shade`
route already gestures at with its 65% constant. This single function change
improves every secondary screen in the shell simultaneously — it is the
highest-leverage fix in this review.

### P0-3 — Wi-Fi failed-password state buries the error and reuses the connect keyboard's dead space

**Screen:** Wi-Fi password entry after a rejected password.
**Capture:** `docs/evidence/wifi-settings/paired-qemu/wifi-auth-error-dark.png`.
**Observation:** `"Password was not accepted. Check it and try again."` sits
in small red text wedged between the numeric row and the `Cancel`/`Connect`
buttons, while ~330px of vertical space between the password field and the
keyboard (visible in the sibling `wifi-masked-dark.png`, same layout) stays
empty. This is the same root cause as P0-2 (panel/keyboard region not sized to
its actual content) but worth calling out separately because it's the one
place an *error* gets the same "buried in dead space" treatment as a merely
empty list — a failed action deserves more visual weight, not the same
treatment as nothing-to-show.
**Code:** `nix/rust-shell-client/src/render.rs:682-1034` (`paint_wifi`);
search for the error-message `text(...)` call near the connect button.
**Fix:** once P0-2's panel-sizing fix lands, give the error message its own
elevated treatment (icon + border-accented banner directly under the field it
refers to) rather than a single line of colored text lost in a large blank
keyboard-adjacent region.

### P0-4 — Settings capability-row spacing is hand-typed and visibly uneven

**Screens:** Settings, every theme, every capture that reaches this screen
with real content.
**Captures:** `docs/evidence/coherent-shell/rust-visual-themes-host/dark/settings.png`,
`.../latte/settings.png` (placeholder "Unavailable" rows), and
`docs/evidence/wifi-settings/paired-qemu/wifi-settings-dark.png` (same
layout, populated Wi-Fi/Brightness/Keyboard/Motion rows) — three independent
captures, two themes, two content states, same visible defect.
**Code:** `nix/rust-shell-client/src/render.rs`, `Route::Settings` branch
(~lines 1497–1503) positions the four capability cards at literal
`y = 162.0, 326.0, 452.0, 590.0` for a fixed 110px card height. That produces
gaps of 54px after the first card, 16px after the second, and 28px after the
third — three different gap values in one four-item list, visible in every
capture regardless of theme or which rows have content. This is independent
of P0-2's panel-height problem: even once the panel is sized to content,
these four `y` values stay wrong relative to each other.
**webOS reference:** the O'Reilly Palm webOS developer text describes
dashboard/list chrome as fixed-height, content-sized strips (§3) — the
implication for any list-of-cards UI in the same visual language is a single
consistent row rhythm, not per-row hand-tuned offsets.
**Fix:** replace the four literal constants with a computed series — card
height (110) + one fixed gap (e.g. 16) ⇒ `y = 162.0, 288.0, 414.0, 540.0` —
and update the two positions computed relative to the old constants in the
same block: the Brightness `−`/`+` control text (currently `w - 162.0,
366.0`, tied to the old y=326) and the "Power" heading/Reboot/Power-off cards
(currently `722.0/750.0/828.0`, tied to the old y=590 end). Cleanest fix is a
shared `row(index)` helper feeding all of these instead of five independent
literals.
**Evidence class:** pure arithmetic, verifiable by direct source read; no
board access needed to confirm the bug or the fix.

### P1-1 — Two renderers, two unrelated font declarations, no shared source of truth

**Screens:** every screen — the deck (C) sits directly adjacent to the
drawer/shade/settings (Rust) in the same composited frame.
**Capture:** `docs/evidence/omarchy-themes/community-board-fixed/community.png`
shows the deck's `"Home"` title immediately above the drawer's `"All apps"`
heading in one screenshot.
**Code:** `nix/rust-shell-client/src/render.rs:171,194` hardcodes the literal
family `"DejaVu Sans"` for every Rust-drawn label, in exactly two weights
(`pango::Weight::Normal` / `Bold`, `text()`/`heading()` at lines 183-189).
`nix/card-shell/render.c:112` requests the generic Pango alias `"sans"` for
every C-drawn label (deck title, status, button captions) — this is not
guaranteed to resolve to the same family/metrics as the Rust side; it depends
on fontconfig's default sans mapping on the target image, which neither file
pins. Compare with the project's own design-study target,
`site/src/styles/handheld-design.css`, which specifies a deliberate
three-family system: "IBM Plex Sans Condensed" for display headings, "IBM
Plex Mono" for section labels/timestamps/gesture hints, "IBM Plex Serif" for
body copy.
**webOS reference:** webOS used one named system font consistently from the
status bar through the launcher, card labels and Settings — "Prelude" from
2.x onward (an evolution from the earlier Cronos/slab-style 1.x face) — so
type never looked like "two different apps" even though webOS itself was
built from many independent Mojo "scenes."
**Fix:** define one explicit font family as a shared constant (or read from
the same theme-token pipeline that already carries colors between C and
Rust), use it in both `render.rs` and `render.c`, and add a third weight tier
(a "medium"/"semibold" for section-eyebrow labels like `"YOUR DEVICE"` /
`"Device controls"`) so headings, section labels and body read as one
designed hierarchy instead of two hand-rolled ones that happen to coexist.

### P1-2 — Gesture-hint text has three different typographic treatments for the same job

**Screens:** Drawer footer, Shade subheading, Deck footer.
**Code / exact strings:**
- `nix/rust-shell-client/src/render.rs:1232-1240` — `"SWIPE DOWN TO RETURN TO CARDS"`, all-caps, small tracked "kicker" style, centered.
- `nix/rust-shell-client/src/render.rs:1246-1252` — `"Swipe up above the list to close"`, sentence case, left-aligned body style.
- `nix/card-shell/adapter.c:802-807` — `"Swipe up for apps"`, sentence case, different margin/vertical-rhythm logic (computed from `cfg->height - top_reserved - bottom_reserved - 58`, unrelated to the Rust side's fixed offsets).
**webOS reference:** webOS's gesture area itself was the affordance (a
persistent physical/capacitive strip with its own visual "wave" cue); textual
coaching, where it appeared at all, was confined to first-run tips, not
permanent on-screen chrome repeated on every visit.
**Fix:** converge on one hint style (recommend sentence case, muted color,
one consistent size, one consistent bottom margin formula) across all three
call sites; longer term, consider showing each hint only until its gesture has
been performed once (a small persisted flag), which also better matches both
the webOS precedent and the user's stated rejection of permanent chrome.

### P1-3 — Theme preview's palette/image treatment is visually thin relative to its own supporting content

**Screens:** Theme preview.
**Captures:** `docs/evidence/omarchy-themes/theme-preview-host/catppuccin-preview.png`
(good — real Totoro still renders correctly) vs.
`docs/evidence/omarchy-themes/portrait-preview-host/preview.png` (a themed
fixture with no decodable still falls back to a plain two-color split
rectangle captioned "Screen crop / Full-height preview" with no indication
that the split colors are a placeholder rather intentional imagery).
**Code:** `nix/rust-shell-client/src/render.rs:405-520` (`ThemePage::Preview`
branch) — the `preview_image` `Option` correctly renders a real decoded still
when present (this works; earlier suspicion from `visual-gap-audit.md` that
the code "shows no image" was a host-fixture limitation, not a code gap —
worth stating positively). When there is no image, the code paints a plain
filled rounded rect with no visual cue that this is a fallback/error state
rather than a themed background.
**Fix:** give the no-image fallback a distinct visual treatment (diagonal
hatch, a small "no preview available" glyph) so it cannot be mistaken for an
intentional two-color wallpaper. P2 if the true no-image case is rare in
practice; kept at P1 here because "video unavailable" themes (visible in the
same screen, e.g. Fixture Night) hit this path in ordinary use, not just in
degraded fixtures.

### P1-4 — Notification shade's "preview" tile duplicates the history row directly beneath it

**Screens:** Shade, both a single-notification state and a many-notification
state.
**Captures:** `docs/evidence/coherent-shell/rust-visual-themes-host/dark/shade.png`
(one fixture notification: the preview tile and the first history row show
the identical source/summary text, "System / Connection needs attention",
back to back) and `docs/evidence/coherent-shell/notification-history-motion-qemu/initial.png`
(12 notifications: the preview tile instead reads "No active preview"
immediately above a fully populated history list — adding no information the
list below doesn't already show).
**Code:** `nix/rust-shell-client/src/render.rs`, `Route::Shade` branch, the
preview `service_card` (~lines 1265–1310) versus the history loop starting at
`NOTIFICATION_TOP` a few lines later (~1355 onward). Also in the same block:
the notification-count text is built as `format!("{count} notifications")`
(~line 1257) with no singular form, so a single notification literally reads
"1 notifications".
**webOS reference:** a webOS **banner** (a temporary, ephemeral
below-the-app alert) and a **dashboard** (the persistent, content-sized
history/action panel) were deliberately two different objects with two
different lifetimes — a banner disappeared once acknowledged or superseded by
its dashboard entry; it never sat permanently stacked directly on top of that
same dashboard entry repeating the same text (§3, notifications).
**Fix:** either drop the preview tile whenever the shade is already showing
History (reserve it for a genuinely different, ongoing/ephemeral state not
yet in history), or suppress it specifically once its event is the top
history row so the two never say the same thing at once; separately, fix the
count string's singular case.
**Evidence class:** host render + QEMU capture, both direct reads of current
code; no board access needed.

### P1-5 — The live-content translucency fix landed for the Drawer only, not Shade or Settings

**Screens:** none yet observed with this defect on Shade/Settings — this is a
latent-risk finding, not a reproduced one.
**Reference capture for the underlying failure mode:** `docs/evidence/coherent-shell/real-theme-paired-qemu/latte-drawer.png`
(paired QEMU, source `14a2bdc6`, predates the fix below) shows exactly this
class of bug on the Drawer: the community Latte theme's authored
`launcher.background` alpha (0.95) let the ghost text `Selected: Card one:
accep…` show through the drawer's lower panel.
**Code:** `nix/rust-shell-client/src/render.rs` (~lines 1086–1097). The
shared `panel_brush` lookup (`theme_brush(theme, section, "background")`,
line 1086) is used by `Route::Drawer`, `Route::Shade` and `Route::Settings`
alike (`section` is `"launcher"`/`"notifications"`/`"controls"` respectively,
lines 1080–1084), but the opaque pre-fill that prevents ghosting
(`if route == Route::Drawer { ... }`, lines 1091–1097, landed same day as the
Drawer fix) guards **only** `Route::Drawer`. Any theme that authors
`notifications.background` or `controls`/`menu.background` with alpha below
1.0 would reproduce the identical ghosting on the shade or Settings panel;
nothing in the currently committed evidence set rules this out, since no
captured theme so far sets that token below 1.0 on those two sections.
**webOS reference:** HP's Dashboard and Settings-equivalent surfaces used
consistently opaque system chrome regardless of which app or theme was
underneath (§3, notifications/status bar).
**Fix:** move the opaque pre-fill out of the `route == Route::Drawer` guard
so it covers `Route::Drawer | Route::Shade | Route::Settings` alike, ahead of
the shared `panel_brush` fill that follows it.
**Evidence class:** source-code inference from the same commit/file that
fixed the Drawer case; needs a community theme with `alpha < 1.0` on
`notifications`/`menu` background tried on the board (or in QEMU) to become
a reproduced-and-fixed bug rather than a preventive one.

### P2-1 — Corner-radius drift between the "panel" family and the preview image frame

**Code:** `nix/rust-shell-client/src/render.rs:207-299` establishes card/tile
radius `16.0` (`service_card`, line 239) with its border stroke correctly
inset to `15.25` (concentric with a 1.5px stroke). The palette swatches use a
smaller, appropriately-scaled `12.0`/`11.25` for a 66×66 chip (line 434/437),
and the phone-bezel frame in the theme preview intentionally uses a tighter
`6.0` (line 494) — these two are deliberate, proportional choices, not bugs.
The one true drift: the **preview image panel itself** uses `15.0`
(lines 470, 483) where every other panel-scale element uses `16.0` — a 1px
inconsistency with no apparent reason. Converge it to `16.0`.

### P2-2 — Icon rendering is not actually a problem, correcting a plausible worry

Checked because the task brief called out "icon sizing and blurriness" as a
common polish issue to look for: `nix/rust-shell-client/src/icon.rs` resolves
icons through the installed icon theme's `index.theme` metadata (`score()`,
lines 96-113) and decodes SVGs through librsvg at the exact requested size
with a proper Cairo `scale()` (lines 224-273), so icons stay vector-crisp at
whatever size they're painted. `docs/evidence/coherent-shell/rust-icons-host.png`
confirms this visually — the Terminal/Monitor/Video icons are sharp, not
blurred or pixelated. **No fix needed here**; recorded so a future reviewer
doesn't re-flag it without checking.

## 3. webOS reference points used above

Primary design-intent source already in this repository:
[Palm Pre User Guide](https://support.bell.ca/_web/guides/User-Guides/Mobile/PalmOne/Palm-EN/palm_pre_userguide_en%28en%29.pdf)
(pp. 19–20, 23–26, 32–33 for card/launcher/scroll/notification behavior, per
`docs/design/handheld-shell/motion-research.md`) and the archived
[HP webOS developer notification guide](https://www.banneret.nl/webos/documentation/all/dev-guide/mojo/dashboards-notifications.html).
The rest of this section is new research for this review, done directly
against the web (not against Palm imagery reproduced here — no screenshot is
copied into this repository; every claim below cites its source instead).
Coverage is Palm/HP webOS 1.x–3.x on the Pre, Pixi, Veer and TouchPad, plus
LuneOS where it preserves the same interaction model. Numeric values are only
stated where a source gives them; everything else is described qualitatively
and marked as such.

**Card view.** webOS's defining metaphor was a literal "deck of cards" for
multitasking: each running app renders as a live, still-updating rectangular
thumbnail ("card") that can be rifled through left/right, tapped to maximize,
or flicked upward off the top of the screen to close/kill the app — mimicking
handling a physical deck of cards
([PCWorld](https://www.pcworld.com/article/532853/palm_pre_webos.html),
[Engadget Palm Pre review](https://www.engadget.com/2009-06-03-palm-pre-review-part-1-hardware-webos-user-interface.html)).
Cards stayed live/updating while minimized, not frozen snapshots
([PCWorld](https://www.pcworld.com/article/532853/palm_pre_webos.html)). A
small round center button in the gesture area toggled between the current
full-screen app and card view; pushing a card up but releasing before it left
the screen produced a multi-card overview rather than closing it
([PCWorld](https://www.pcworld.com/article/532853/palm_pre_webos.html)).
Reviewer John Gruber, writing in 2017 with the benefit of hindsight, singled
out the cards' rounded-rectangle geometry and gesture model as design that
"proved ahead of its time," later echoed in iOS's own app-switcher
([Daring Fireball](https://daringfireball.net/linked/2017/12/27/webos-gestures)).
No source found here gives an exact corner-radius, shadow, gutter or
scale-on-release value in pixels; those specifics are **not documented** in
the sources reviewed and should not be treated as known constants — only the
qualitative behavior (live content, rounded cards, spacing between them,
flick-to-close) is sourced.

**Launcher and quick-launch bar.** The Launcher was webOS's equivalent of a
home screen, holding every installed app in an icon grid; it opened via the
dock's dedicated arrow icon, the gesture-area center button in card view, or
(with advanced gestures enabled) a swipe up from the bottom
([weboshelp.net glossary](https://www.weboshelp.net/webos-mojo-development-resources/glossary/208-launcher);
webOS 3.0/TouchPad specifics:
[TechSpot](https://www.techspot.com/review/425-hp-touchpad/page2.html)). On
phones, a fixed **Quick Launch** dock held five icons (commonly
dialer/contacts/email/calendar plus the Launcher icon itself) always visible
at the bottom of the screen regardless of which app or view was active
([Bigbeaks blog](https://blog.bigbeaks.com/2011/01/08/hppalm-pre-and-webos-review-user-interface-launcher-and-multitasking/)).
On the TouchPad (webOS 3.0), the Launcher organized apps into four
categorized pages — Apps, Downloads, Favorites, Settings
([TechSpot](https://www.techspot.com/review/425-hp-touchpad/page2.html)).

**Gesture area.** Early webOS phones (Pre, Pixi) had a dedicated
touch-sensitive **gesture area** below the display glass, physically distinct
from the screen, extended down so on-screen content itself didn't have to be
covered by a gesture's starting touch
([PhoneArena](https://www.phonearena.com/reviews/Palm-Pre-Review_id2192); via
search). It replaced hardware nav buttons entirely and handled entering card
view, going back and going forward
([PhoneArena](https://www.phonearena.com/reviews/Palm-Pre-Review_id2192)). The
signature **"wave"** gesture was an upward swipe starting in the gesture area
and continuing onto the screen: done slowly it summoned the Quick Launch
dock/taskbar, which visually "stuck to your thumb" and rippled like an actual
wave as it followed the finger — an explicit physical metaphor for a system
with no dedicated hardware buttons
([PCWorld](https://www.pcworld.com/article/532853/palm_pre_webos.html)).

**Notifications: dashboards and banners.** webOS distinguished two
notification forms. A **banner** appeared briefly below the current app
(with an icon, short message and sound), then, after a few seconds, was
replaced by a **dashboard** — a small, content-sized, persistent panel
reachable for deferred action, "constrained windows that span the full
screen width and about 10% of the screen height in portrait mode; on the
Palm Pre, that's 320 pixels wide and 48 pixels high"
([O'Reilly, *Palm webOS*, ch. 10](https://www.oreilly.com/library/view/palm-webos/9780596802097/ch10s02.html),
via search index — the book republishes Palm's own Mojo developer-guide
text). Dashboards could also host ambient/background-app content without
requiring a full card. The key structural point sourced here: **the
dashboard was always sized to its content** (a fixed ~10%-height strip), never
a full-screen sheet — it never grew to fill unused vertical space just
because nothing more had arrived.

**Status bar.** The always-visible top status bar carried network/carrier
name, a digital clock, signal and battery indicators
([GSMArena Palm Pre review](https://www.gsmarena.com/palm_pre-review-429p3.php)).
Tapping it opened a **semitransparent menu** for Wi-Fi, Bluetooth and
Airplane/Flight Mode toggles plus date/battery detail, without leaving the
current app or card — i.e. system-level quick controls lived one tap away
from the persistent bar rather than as separate always-visible chrome
([GSMArena](https://www.gsmarena.com/palm_pre-review-429p3.php); the later
Palm Pre 2 kept the same tap-to-expand pattern per
[TechRadar](https://www.techradar.com/reviews/phones/mobile-phones/palm-pre-2-912976/review/3)).

**Typography.** webOS's system typeface across 2.x/3.x devices (including the
HP TouchPad) was **Prelude**, a custom sans-serif commissioned from Font
Bureau co-founder David Berlow specifically for webOS: "an original sans
serif design of simple, generous letterforms which provide a clear,
comfortable, and inviting experience for navigation and readability," released
as a family of six weights, with publication designer Roger Black consulting
alongside Matias Duarte and Peter Skillman on the typography program; a
companion print/marketing family, Apres, was developed alongside it
([Palm Infocenter, "Font Bureau Developed Custom Typefaces for WebOS"](http://www.palminfocenter.com/news/9833/font-bureau-developed-custom-typefaces-for-webos/)).
The same source and an XDA forum thread confirm Prelude was shared across
phone webOS and the TouchPad, i.e. **one named system font family used
everywhere**, not a per-surface choice
([XDA: "Is the same Prelude font used on both webOS smartphones and the
touchpad tablet?"](https://xdaforums.com/t/is-the-same-prelude-font-used-on-both-webos-smartphones-and-the-touchpad-tablet.1676912/)).
No source reviewed here gives Prelude's exact point sizes/weights per UI role
(title vs. body vs. card label) — that mapping is **not documented** in the
sources found and is not asserted as a numeric target.

**Iconography.** Reviewers described webOS's overall visual craft, icons
included, as elegant and cohesive: "detailed application icons tied together
in an elegant way," comparable in polish to the iPhone of the same era
([TahawulTech reprint of the PCWorld piece](https://www.tahawultech.com/news/networking/a-closer-look-at-the-palm-pre-and-webos-2/)).
No source reviewed here gives a documented corner-radius or grid-size
specification for webOS app icons; period screenshots (not reproduced here)
show a rounded-square glyph treatment consistent with the general
skeuomorphic/glossy icon style common across 2009–2012 mobile platforms, but
that specific stylistic label is this reviewer's own characterization of
widely available screenshots, not a sourced Palm design-guideline claim, and
is flagged as such.

**Motion.** Sourced motion facts are limited to the *choreography*, not
frame-level physics: cards could be dragged and held under the finger, thrown
upward to close, and swiped left/right to switch, all described consistently
across
[PCWorld](https://www.pcworld.com/article/532853/palm_pre_webos.html),
[SlashGear](https://www.slashgear.com/cardswitcher-2-0-brings-webos-multitasking-to-ios-27220224/)
and the [Daring Fireball retrospective](https://daringfireball.net/linked/2017/12/27/webos-gestures).
No easing curve, duration in milliseconds, or velocity/deceleration constant
for the throw-to-close or app-open/close zoom transition was found in any
source consulted for this review; this project's own
[`docs/design/handheld-shell/motion-research.md`](handheld-shell/motion-research.md)
independently reached the same conclusion after reading the Palm Pre User
Guide directly ("The sources provide interaction and spatial behavior, not
measured durations, velocity constants, spring curves"). This review does not
contradict that: **no numeric motion target exists in the historical record
available to either document**, and none should be invented.

**"Just Type" and later evolution (webOS 3.x / TouchPad).** HP's TouchPad
generalized the phone launcher into "Just Type": a persistent search field
across the top of the home screen doubling as a universal launcher, search
(local + web/Maps/Wikipedia/Twitter/App Catalog) and quick-action box (e.g.
turning typed text directly into a note, message or calendar entry) —
extending Palm's original minimalist, content-first philosophy from "one card
at a time" to "one text box for every intent"
([PCWorld TouchPad piece](https://www.pcworld.com/article/494759/up_close_with_hps_touchpad_and_webos.html)
and search-aggregated TouchPad review material). The TouchPad's **Exhibition**
mode — an ambient full-screen clock/agenda/photo display activated
automatically when docked on the Touchstone charger — was called out by
reviewers as "one of the finer bits of good design on the TouchPad," notable
for being simple and full-screen rather than cluttered
(search-aggregated TouchPad review material, uncredited single source not
independently re-verified — treat as representative-opinion, not fact).

**Overall design philosophy.** webOS's UI was led by Matias Duarte (later
Director of Android UX at Google), and multiple period reviews describe the
whole system as prioritizing live, real content over decorative chrome — a
consistent typeface and icon language "tied together in an elegant way," a
single persistent multitasking metaphor (the card deck) instead of separate
home/recents/app-switcher concepts, and system controls (status bar menu,
gesture area) that stayed out of the way until invoked
([PCWorld](https://www.pcworld.com/article/532853/palm_pre_webos.html);
[Wikipedia, WebOS](https://en.wikipedia.org/wiki/WebOS)). This review's
findings below are checked against that philosophy — content-sized chrome,
one consistent type/icon system, and no permanent decorative controls — not
against a claim to literally reproduce any webOS screen.

**LuneOS.** The open-source webOS continuation (webOS-ports.org, rebuilt on
Qt/QML rather than the original Mojo/Enyo stack) preserved the same gesture
vocabulary rather than reinventing it: a left swipe from the gesture-area
light goes back (or returns to card view from a full-screen app), a full
swipe across the gesture area switches apps, swipe-up returns to card view,
and — notably for the "card stacks" question this review's brief asked
about — LuneOS's own feature list documents cards that "can be touched to
move individually and stacked into groups" plus dedicated "Card Stacking,"
"Card Zoom Gestures" and "Tap-to-Maximize Edge Cards" behaviors, i.e. same-app
windows could be visually grouped into one stack rather than shown as
separate full-width cards
([LuneOS feature description via search index of webOS-ports/Preware
catalog material](https://preware.pivotce.com/package/org.webosinternals.patches.browser-gesture-click-open-in-new-card);
general project description via
[Wikipedia, LuneOS](https://en.wikipedia.org/wiki/LuneOS)). This shell has no
equivalent of card stacking for multiple windows of the same app — out of
scope for this review (no evidence any installed app opens multiple windows
today) but worth a note for whoever picks up card-view work next.

## 4. Evidence gates — what needs real glass vs. what's already decidable

| Finding | Decidable from host/QEMU captures + code today | Needs board/glass observation |
| --- | --- | --- |
| P0-1 card header identity | yes — code path and captures both show it | confirming legibility/contrast of the fix at arm's length |
| P0-2 dead panel space | yes — code (`panel_h`) and every listed capture agree | confirming the "dimmed deck peek" replacement doesn't look worse under real ambient light |
| P0-3 Wi-Fi error placement | yes | touch-target/legibility of the revised banner |
| P0-4 Settings row spacing | yes — pure arithmetic, both the bug and the fix | none to confirm the bug; a post-fix capture is good practice, not load-bearing |
| P1-1 font consistency | yes — both source files inspected directly | whether fontconfig's `"sans"` alias actually diverges from `"DejaVu Sans"` on the installed image (host-only inspection can settle this without the board, but wasn't done in this pass) |
| P1-2 gesture-hint styling | yes | whether removing permanent hints after first-use is discoverable without them, per task 5.3's real-finger discovery gate |
| P1-3 preview fallback | yes | none beyond normal visual review |
| P1-4 shade preview/history redundancy | yes — both captures and code agree | none beyond normal visual review of the corrected layout |
| P1-5 translucency fix not generalized | yes as a preventive code read | needs a theme with `alpha < 1.0` on `notifications`/`menu` background tried on board or QEMU to become a reproduced bug |
| P2-1 radius drift | yes (single source-line comparison) | none |
| P2-2 icon rendering | yes, already resolved | none |
| §0 chrome-generation correction | yes | none — this is an evidence-reading correction, not a claim needing new capture |

None of the above claims a physical/optical/real-finger pass; per AGENTS.md,
any of these fixes still needs its own named evidence class (native build,
QEMU, injected event, camera, or real-glass) recorded against the task that
implements it, and none is checked complete by this document alone.
