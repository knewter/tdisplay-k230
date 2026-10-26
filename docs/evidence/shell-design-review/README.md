# Shell design review: board captures of the fixes, 2026-10-26

Change: `openspec/changes/the-shell-and-its-apps-look-finished` (task 9.1).

**Evidence class: native `grim` captures with injected touch.** Each image is
the compositor's own output at 1232x568 (landscape, `transform 270`). The
operator did not touch the glass during these runs. These captures are not the
operator's on-glass check (task 9.2).

## Method

- Board: the landscape HDMI configuration
  (`.#nixosConfigurations.k230-mainline-drm-shell-landscape-hdmi`). Each build
  was test-activated with `switch-to-configuration test`, then
  `systemctl restart shell`. The boot default was not changed.
- Driver: `ui.py.txt` runs on the board as root. It creates a uinput
  touchscreen whose axis ranges match the real panel (`/dev/input/event1`),
  injects taps and swipes, opens surfaces with `k230-shell-rust --surface`,
  and captures with `grim` as the `shell` user. `run.sh.txt` runs it over SSH
  under `/tmp/k230-board.lock` and fetches the PNGs.
- Apps were opened by tapping their drawer tiles, which also proves that each
  entry launches. Each capture was taken 9–12 s after the tap. `apps` printed
  the mapped app ids, and `killapps` closed the app afterwards.

| Directory | System store path (prefix) | Source commit |
| --- | --- | --- |
| `build-9rbjw6vl/` | `9rbjw6vl…-nixos-system` | `e7b3e11b` |
| `build-9kam3kq9/` | `9kam3kq9…-nixos-system` | `68c5a505` |
| `build-1r8zfd5s/` | `1r8zfd5s…-nixos-system` | `3ec31882` |

## Not committed

These captures were taken and checked but are kept out of the repository
because they show private or incidental data:

- btop and Monitor (htop) show process lists with command lines.
- The Weather app and the Home Weather widget show a location.
- The Terminal shows a shell prompt.

What they showed:

- btop opened its full monitor, with no "Terminal size too small" error.
- The Weather app showed a large temperature, conditions, five forecast slots
  and a Refresh button.
- The Home Weather widget's temperature sat clear of its glyph.

## Findings, before → after

| Review finding | Result on the board | Capture |
| --- | --- | --- |
| The drawer left a 32 px band at the top | The sheet starts at the top edge | `build-9kam3kq9/r2-drawer.png` |
| Help differed from the search field | In Catppuccin Latte, Help is the same themed control as the search field | `build-9kam3kq9/r2-drawer.png` |
| Tile labels were bold | Medium weight | `build-9kam3kq9/r2-drawer.png` |
| Six games shared one icon; so did Clock and Timer | Every drawer entry has a distinct icon | `build-9kam3kq9/r2-drawer.png` |
| Two Files entries | One "Files" (Nautilus); Portfolio is hidden | `build-9kam3kq9/r2-drawer.png` |
| Viewnior never opened | Its window maps (app id `viewnior`) on a retry. The first pass, run straight after the Video session, mapped nothing; this was not investigated further | `build-9rbjw6vl/app-viewnior2.png` |
| btop: "Terminal size too small" | Full monitor (see *Not committed*) | — |
| Clock, Timer and Weather were bare text | Large type. Timer has Start, −1 min, +1 min and Reset controls | `build-9rbjw6vl/app-clock.png`, `app-timer.png` |
| Terminal apps all titled "Terminal" | App ids `k230-2048`, `k230-btop`, `k230-clock`, `k230-timer`, `k230-weather`, `k230-nethack`; the cards are titled with each app's name | `build-9kam3kq9/r2-ov1.png`, `r2-ov2.png` |
| Overview cards showed a letter | The Clock and 2048 cards show their icons. This needed the compositor's `scalable/` lookup (`68c5a505`); on `9rbjw6vl` only the Terminal card had its icon | `build-9kam3kq9/r2-ov1.png`, `r2-ov2.png` |
| Footer cue only went Home in the middle third | A tap at x=150, y=560 on the bottom band, outside every card, went Home | `build-9rbjw6vl/ov-2-after-side-tap.png` |
| GTK3 apps unthemed | Fifteen, Net, Same Game, Sixteen and Galculator use the Latte palette and touch-sized controls | `build-9rbjw6vl/app-*.png` |
| Nautilus showed minimise and maximise | Close only. On `9rbjw6vl` the dconf keyfile's `button-layout` was not honoured (`files-buttons-before-gtk4-ini.png`); a generated `~/.config/gtk-4.0/settings.ini` with `gtk-decoration-layout=:close` fixed it | `build-9kam3kq9/files-buttons-zoom.png` |
| Shade: "0 notifications" beside the empty state | No count line; "No new notifications" is centred in the list column | `build-9kam3kq9/r2-shade.png` |
| Shade battery "100% - Full" | "100% · Full" | `build-9kam3kq9/r2-shade.png` |
| Keyboard tile said "Toggle keyboard" | "Show or hide". The C status fast path (`nix/settings-status.c`) also had to change | `build-9kam3kq9/r2-shade.png`, `r2-settings.png` |
| Settings: raw "link-up", "Session preference", an audio suffix, a whole row for two links | "Connected", "Reduce motion · Fewer animations", "Built-in Audio Stereo ›", and Vision › and Themes › in the title row | `build-9kam3kq9/r2-settings.png` |
| Scrolled Settings cut card text under the header | A divider and a fade at the body top | `build-9rbjw6vl/04-settings-scrolled.png` |
| Dock packed to the left | Four icons centred in the tray | `build-9kam3kq9/r2-home1.png` |
| Battery – Details showed zero readings | "Full · On charger"; no zero current, power or cycle rows | `build-9kam3kq9/r2-home1.png` |
| The background chooser cut a fragment at the output edge | Both carousel columns fade from the centred card's edge to the column edge | `build-1r8zfd5s/r3-themes.png` |

## Limits

- **Background chooser.** The neighbouring background beside the centred one
  is a light pixel-art wallpaper. Its slice still shows as blue glyphs without
  a visible frame. It now fades towards the edge instead of being cut at it,
  but it can still read as a fragment. This is left for the operator's glass
  check.
- **Input line.** "USB power · limit 3.25 A · 2.05 A …" is still truncated in
  Battery – Details.
- **Video.** It opens the same terminal session as before the change; it was
  not among the findings.
- **btop rows.** btop at 14 pt opened without its size error. btop shows that
  error below 80x24, so the window has at least 24 rows; the exact count was
  not measured.
- **Weather and Timer input.** The Weather and Timer apps' tap targets were
  exercised only through a pty on the host (`tests/test_term_apps.py`), not by
  touch on the glass.
