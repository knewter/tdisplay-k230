# UX / IA review of the K230 shell against webOS and Firefox OS (2026-10-26)

**Evidence labels**
- **[code]**: I read the source and cite the line.
- **[spec]**: an accepted requirement in `openspec/specs/`.
- **[capture]**: I looked at a committed native capture or host render.
- **[infer]**: reasoning only, with the cheapest board check named.
- **[mem]**: my recollection of webOS / Firefox OS.

**Constraints the closures respect**
- One online CPU, Pixman only, no GPU. Drawer scroll renders in about 39 ms (~8 fps) and OSK frames take 38-77 ms (commits `9dba3161`, `f4c9522a`), so proposals are static or cheap to paint.
- Speaker and Bluetooth are parked, and I found no haptic motor, so feedback is visual plus the base's key backlight.

**Prior reviews.** `docs/design/shell-ux-critique.md`, `webos-polish-review.md` and `docs/research/handheld-ux/webos-comparison.md` predate the landscape, gesture-only shell. They explicitly excluded dock, notifications, stacks and global search, so I do not repeat their polish findings.

## 1. Current IA map (landscape 1232x568)

```
TOP pull down -> SHADE (notifs + brightness/volume/keyboard tile)   [redesign in flight: the-shade-leads-with-time-and-quick-tiles]
                   '-> "Settings >" -> SETTINGS: Wi-Fi>, Cellular>*, Location>*, Vision>, Themes> (carousel),
                      Brightness, Volume, Keyboard, Reduce motion, Key backlight, Reboot…/Power off… (confirm)
APP (maximised Sway window, no chrome)
  | bottom-edge swipe UP
OVERVIEW (live cards; 1 big card + slivers; throw card UP = close; tap card = open)
  | swipe UP from footer
HOME (pinned pages + widgets + dock; hold = rearrange)
  | NEW swipe UP
DRAWER (search + grid; hold tile = app menu; drag to Home) -> Help
Also: OSK (two-finger up from bottom, handle down to hide), power sheet (hold power key),
      banner (non-focus), launch splash, app menu (window list + desktop actions)
```

- **Touch gestures** ([spec] `shell/spec.md` ~312-340). Each upward hop is a separate gesture, and the same contact never continues to the next level.
  - Horizontal or curved gesture in the bottom band: switch to the adjacent app.
  - Throw a card up: close it.
  - Side-edge inward: dismiss shell contexts only, never sends Back to apps.
  - Power key: short press toggles the display, hold opens the power sheet.
  - HDMI trackpad mode only: four-finger pinch opens overview.
- **Base keys** [code] `nix/shell.nix:925-934`. The unbound `LILYGO+Left`/`Right` below are my suggested chords, not existing bindings.
  - LILYGO opens the drawer.
  - LILYGO+Tab opens overview.
  - Fn+LILYGO takes a screenshot.
  - Esc is shell back only when no app has focus.
  - Typing hides the OSK.
  - Nothing else is bound.
- **Notification plumbing** [code]. It is a private Unix-socket broker, `tools/notification_center.py`.
  - The only trusted source is the shell (`nix/shell.nix:460-464`).
  - Emitters I found are the shell, the modem client and the base-battery policy (`nix/keyboard-base/battery_policy.py`).
- **Drawer apps** [capture `shell-design-review/build-9kam3kq9/r2-drawer.png`]: 2048, btop++, Clock, Fifteen, Files, Galculator, Monitor, Net, NetHack, Omawrite, Same Game, Sixteen, Terminal, Timer, Video, Viewnior, Weather, Zathura. There is no browser, mail, calendar, contacts or messages app.

## 2. What already works well

- A chrome-free gesture ladder gives apps the full 568 px of height.
- The live-card overview has throw-to-close with a recoverable close, and cards carry real icons and names.
- Finger-tracking quick-switch from the bottom band covers the Firefox OS edge-swipe use case without using the side edges.
- Banners never take focus and have privacy defaults. Swipe-to-dismiss and history exist.
- The per-app menu lists windows and desktop actions.
- Also in place: launch splash, power sheet with named confirmation, reduce-motion, text scale and high contrast, themes applied across shell, terminal and GTK apps, and OSK hide-on-key-press.

## 3. Ranked gaps

| # | Gap | Impact | Effort | New HW / service |
|---|---|---|---|---|
| 1 | Base keyboard launch path incomplete (typing after LILYGO, Enter) | High | S | none |
| 2 | No "Just Type": search is app-name substring only | High | M | none |
| 3 | App notifications and timers cannot alert | High | M | service (D-Bus adaptor, timer daemon) |
| 4 | No idle dim, screen-off or lock (AMOLED, battery) | High | S for dim/off, L for lock | none |
| 5 | Base keys can't switch, cycle or close apps | Med-High | S-M | none |
| 6 | GTK chrome ~44 px vs the shell's ~99 px touch floor | Med-High | M | none |
| 7 | No time/battery/Wi-Fi glance inside apps | Med | M | none |
| 8 | Three swipes to launch from an app; overview has no launch entry | Med | S-M | none |
| 9 | OSK never raised by a focused text field | Med | M | none |
| 10 | Settings IA thin (no About, date/time, sleep) | Med | S | none |
| 11 | Help stale; gestures undiscoverable | Low-Med | S | none |
| 12 | Quick controls beyond the shade redesign | Low-Med | S-M | none |
| 13 | Charging "Exhibition" clock | Low | M (after 4) | none |
| 14 | Open-with chooser | Low | M | none |

**Gap 1. Typing after LILYGO does not reach the drawer search, and Enter does not launch.**
- **Reference.** webOS Just Type and the Firefox OS Rocketbar [mem] both took typing immediately.
- **Spec.** `shell/spec.md:1254-1268` says "LILYGO, type, Enter -> app launches".
- **Code.**
  - The search gains focus only from a tap (`main.rs:5699-5701`).
  - `DrawerSearch::key_event` returns false when unfocused (`service_ui.rs:143`).
  - The drawer layer requests `Exclusive` keyboard only while the search is active (`main.rs:3637-3646`).
  - Enter calls `unfocus()` (`service_ui.rs:146`) and never launches.
  - So the scenario has no code path that I found.
- **Infer.** Keystrokes probably go to the app behind the drawer. Check on the board: press LILYGO, then type `ti` with Terminal running.
- **Closure.**
  - Focus the search without raising the OSK when the drawer is opened by the key.
  - Highlight the first match; Enter launches it; arrows or Tab move the highlight.
  - Esc clears the query first and closes the drawer on the second press.
  - Location: `main.rs` (`handle_drawer_key`, `sync_drawer_search`), `service_ui.rs`, `render.rs`.

**Gap 2. No Just Type.**
- **Reference.** webOS searched apps, contacts, quick actions and web providers. Firefox OS searched apps and the web through Rocketbar and Everything.me [mem].
- **Today.** `filter_app_indices` (`service_ui.rs:198`) is a case-insensitive substring match on app name, and only inside the drawer.
- **Capture.** `panel-landscape/board/installed-keyboard-injected.png` (older build) shows the OSK leaving about 1.5 grid rows of the 568 px, so a grid is the wrong results container.
- **Closure.**
  1. Type-to-search from Home and Overview. Rank prefix, then word-start, then substring, with a frecency boost.
  2. Show a compact 3-5 row results list instead of the grid.
  3. Add result sources: running windows, Settings destinations and actions, an inline calculator, "timer 5", "weather", and files by name from a `$HOME` index.
  4. Add web search only if a browser ever ships.
- Location: a new `search.rs` in `rust-shell-client`, replacing `filter_app_indices`.

**Gap 3. Notifications and timers.**
- **Reference.** webOS had a dashboard with ongoing items; Firefox OS had a tray plus an attention screen [mem].
- **Today.**
  - I found no `org.freedesktop.Notifications` server in `nix/` or `tools/`; only a research note mentions it, and there is no portal (`nix/shell.nix:534`).
  - The Timer is a TUI in foot that only writes the terminal bell `\a` (`nix/term-apps/k230_term_apps.py:690-693`).
  - With no speaker or haptic, expiry in the background is silent.
- **Infer.** Throwing the Timer card away likely kills the countdown. Check: start 60 s, close the card, see whether anything remains.
- **Closure.**
  1. A D-Bus Notifications adaptor into the broker. It maps desktop-entry hints to trusted identity, icon and label, and keeps the privacy defaults.
  2. A `k230-timerd` that outlives the card, shows an ongoing notification, and on expiry raises an important banner that persists until dismissed. An optional base key-backlight pulse is the only non-visual cue.
- Location: `tools/notification_center.py`, `k230_term_apps.py`, `nix/shell.nix`.

**Gap 4. No idle dim, off or lock.**
- **Reference.** webOS had a screen-off timer, a lock screen with notifications, and Exhibition mode [mem]. Firefox OS had a lock screen with notifications [mem].
- **Today.**
  - A search of `nix/`, `tools/` and `openspec/specs/` found no `swayidle`, `swaylock` or idle/auto-dim path.
  - The only idle timer is the base backlight's 30 s.
  - logind ignores the power key (`nix/shell.nix:1646-1648`), and the display is blanked only by the physical key (`system/power` spec).
  - The compositor supports session lock (`nix/card-shell/README.md`) but nothing uses it.
- **Why it matters.** The panel is AMOLED with a static dock and clock (burn-in), on a battery.
- **Closure.**
  - Dim to about 25% after 30 s and turn the display off after 60 s, via `ext-idle-notify-v1` from the Rust shell or `swayidle` first.
  - Wake on touch, any key or the power key.
  - Inhibit while video is visible (`video_visibility.rs`) or Timer is foreground.
  - Settings gets one row for the dim and off steps.
  - A PIN lock is L; I would defer it for a single-owner device.
- **Check.** Leave the board idle for five minutes and read `swaymsg -t get_outputs`.

**Gap 5. Base keys cannot operate overview.**
- **Today.** Only `Mod4+Tab` and LILYGO are bound (`nix/shell.nix:925-934`). The compositor already implements `card_shell previous|next|close|activate|back|home` (`nix/card-shell/adapter.c:4044-4075`) but nothing binds them. The `shell.nix:918-921` comment explains why unmodified keys must not be bound.
- **Closure.** Bind `Mod4` chords.
  - `LILYGO+Left`/`Right`: switch app, via a new composite `card_shell switch prev|next`.
  - Repeated `LILYGO+Tab`: cycle, and releasing LILYGO activates.
  - `LILYGO+Backspace` or `W`: close the selected card.
  - `LILYGO+H`: Home.

**Gap 6. GTK chrome is below the shell's touch floor.**
- **Floor.** The shell's own floor is ~99 px (`notification-center` spec).
- **Code.** `nix/handheld-theme-default/gtk-3.0/gtk.css:29` makes menubar items 24 px min-height plus 20 px padding, about 44 px. Buttons are `min-height: 44px` (line 37).
- **Captures.** `build-9rbjw6vl/app-net.png` shows a menubar about 44 px high. `r2-files.png` shows Files header buttons about 30 px, with close as the only window control.
- **Calculation.** By my calculation the panel is about 331 ppi, so 44 px is about 3.4 mm.
- **Closure.** CSS-only raise of menubar, menu and button hit areas to 72-99 px, then recheck. For the games, consider hiding the menubar behind one large "Menu" button. Add `gtk-4.0` CSS for Nautilus header buttons and sidebar rows.

**Gap 7. No glance at time, battery or Wi-Fi inside an app.** This is outside the shade redesign.
- **Reference.** webOS and Firefox OS both had an always-on status bar [mem].
- **Today.** `shell/spec.md` forbids permanent controls. The shade proposal itself says "the device has no status bar", and it adds time only inside the shade.
- **Closure.**
  - A glance pill overlay (beside `notification_banner.rs`), top-right, "14:32 · 82% · Wi-Fi", shown for 2.5 s when a top-edge touch begins but has not yet committed the shade, and on charger plug or unplug.
  - Event banners for Wi-Fi lost or regained and main-cell battery warnings. [infer] I found battery warnings only for the base cell; check the main cell.
  - No permanent strip.

**Gap 8. Three swipes to launch from an app; overview has no launch entry.**
- **Reference.** webOS had a gesture-area tap to the launcher, and in card view a "+" and Just Type (exact version unsure) [mem]. Firefox OS had one Home press and the Rocketbar [mem].
- **Today.** The separate-gesture rule is deliberate ([spec] `home-screen` gesture topology), and overview offers only "Home · tap or swipe up" (`r2-ov1.png`).
- **Closure.** Keep the rule, but add a trailing "+" card and a "Search apps" chip in the empty right of the Overview header. Both open the drawer search directly, so app to launch becomes up plus one tap.
- Location: `nix/card-shell/render.c` and `route.c`. `card_shell_launch_surface` already exists.

**Gap 9. A focused text field never raises the OSK.**
- **Reference.** Firefox OS raised it on field focus [mem].
- **Today.** wvkbd is summoned only by gesture. I found no text-input or input-method use in `nix/`.
- **Closure.** The shell acts as an `input-method-v2` listener that calls the existing `keyboard_signal_path` show/hide. Suppress it for about 10 s after the last physical key press. First verify that Sway delivers text-input state for foot and GTK on this build.

**Gap 10. Settings IA is thin.**
- **Today.** Settings holds Wi-Fi, Brightness, Volume, Keyboard, Reduce motion, Key backlight, Power, Vision and Themes ([capture] `r2-settings.png`). Time zone is a build-time constant (`nix/k230.nix:23`). It is entered from the shade (`service_ui.rs:1278`).
- **Closure.**
  - Add an About page (system store path prefix, source rev, kernel, uptime, IP, storage). This serves the recurring "which build is installed" question.
  - Add Date & time with a time-zone list and NTP state.
  - Add the sleep row from Gap 4.
  - Make Settings a search result.

**Gap 11. Help is stale.**
- **Today.** `help.rs:21-33` lists five items. It omits quick-switch, throw-to-close, long-press menus, side-edge dismissal and base shortcuts. Inside apps nothing hints at gestures.
- **Closure.**
  - A two-column Help (touch and keys).
  - A one-time two-step tour on first boot.
  - A bottom handle shown for about 2 s in the splash fade.

**Gap 12. Quick controls beyond the shade redesign** (brief; the shade is being redesigned separately). The proposal already adds Wi-Fi, Keyboard, Location and Cellular tiles. Candidates not in it:
- a Radios-off master toggle;
- Do Not Disturb, which suppresses banners but keeps history (the broker has priorities but no mute mode);
- Stay-awake once Gap 4 exists.

**Gap 13. Charging Exhibition clock.** After Gap 4, run the Clock app dimmed on black while charging and idle, drifting a few pixels per minute against burn-in, with a notification-count dot and wake on touch or key.

**Gap 14. Open-with chooser.** MIME defaults exist only for text and markdown (`nix/shell.nix:1234-1238`). Add a one-line chooser sheet only when a type has two handlers. This is low priority.

## 4. Do not copy

- **Always-on status bar.** It costs about 5% of a 568 px landscape screen. Use the glance pill instead.
- **Cross-app back gesture and side-edge app switching.** The shell deliberately does not synthesize Back, and side edges collide with GTK sidebars and the shell's own dismissal.
- **Card stacks and grouping.** Typical use is 3-8 single-window apps, and the app-menu window list is enough.
- **Synergy, accounts, Everything.me collections, marketplace suggestions, cloud-ranked search.** There is no account or store, and the modem firmware has no data (`CONFIG_SM_PPP=n`).
- **Rocketbar as browser, and web search providers.** There is no browser.
- **Per-API permission prompts.** Apps are local Nix packages. The global Location toggle is the right granularity.
- **Rotation lock.** Orientation is a build-time choice tied to the keyboard case.
- **Vertical homescreen.** It would show about 1.5 rows at 568 px.
- **Lock screen built around calls, attention screen, camera shortcut.** There is no voice path or camera surface, and SMS is receive-and-notify only.
- **Touch-to-share and photo-slideshow Exhibition.**
- **A general intent platform.** Use `.desktop` files and `xdg-open`.

## 5. Unverified

- Nothing in this report was tested on the board. The two checks most worth doing are LILYGO-then-type (Gap 1) and a timer expiring after its card is closed (Gap 3).
- The webOS and Firefox OS details are from memory. I am least sure of:
  - which webOS release added the card-view "+" and where Just Type sat;
  - which release put a brightness slider in the system menu;
  - whether Firefox OS edge gestures shipped in a stable release (I recall 2.2 development);
  - Haida's status (I recall a 2.5/3.0 re-architecture that never reached a stable consumer release).
- Landscape overview shows about one card at 68% width plus two slivers ([capture] `r2-ov1.png`, `r2-ov2.png`). That is webOS-like, so I did not list it as a gap. The older `card-shell` spec text still says "2-3 cards".
- The worktree had uncommitted edits to `main.rs`, `modem_ui.rs` and `render.rs` from another agent. I treated committed behaviour as authoritative.

Relevant paths, all under `.claude/worktrees/bg31`:
- `openspec/specs/runtime/shell/spec.md`
- `openspec/changes/archive/2026-10-29-the-shade-leads-with-time-and-quick-tiles/proposal.md`
- `nix/rust-shell-client/src/service_ui.rs`
- `nix/rust-shell-client/src/main.rs`
- `nix/rust-shell-client/src/help.rs`
- `nix/shell.nix`
- `nix/card-shell/adapter.c`
- `nix/term-apps/k230_term_apps.py`
- `nix/handheld-theme-default/gtk-3.0/gtk.css`
- `docs/evidence/shell-design-review/`
