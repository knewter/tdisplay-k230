# Panel landscape on the keyboard case — 2026-10-13

Board: the second T-Display-K230, on a non-persistent trial
(`switch-to-configuration test`) of the landscape system built from
`.#kernelMainlineDrmShellLandscapeBootFiles`. A reboot returns it to the
installed portrait image. Kernel 7.3.0-rc5. Sway output `DSI-1`,
`mode 568x1232 transform 270`, logical size 1232x568.

Each file below is labelled with its evidence class. Classes are not
interchangeable: a host render is not a board capture, an injected touch
is not a finger, and a native capture is not what the glass looks like.

## Host renders (`host/`)

`cargo run --release --example render_responsive_evidence -- <dir>` in
`nix/rust-shell-client`, which now also renders Shade, Power and Help and
adds 1232x568. Before the layout fixes the landscape Home had one icon row,
the Shade ended above its notification list, and Help shrank to half size.
After them, every portrait and HDMI render (568x1232, 768x1024, 1080x1920,
1920x1080; Home, Drawer, Settings, Shade, Power, Help, wallpaper) is
byte-identical to the same harness built from `0804c0aa`; only
`home`, `shade` and `help` at 1232x568 differ.

## Native board captures (`board/`)

`grim` on the board at native resolution, 2026-10-13 between 08:17 and
08:40 CDT.

| File | How the surface was reached |
| --- | --- |
| `home.png` | Home after the startup terminal was moved to the scratchpad. The 4x2 clock widget fits the two-row landscape page. |
| `drawer-cli.png`, `shade-cli.png`, `settings-cli.png` | `k230-shell-rust --surface drawer|shade|settings`. `k230-shell-rust` RSS stayed 102-111 MB across them. |
| `keyboard-search-injected.png` | Injected tap on the drawer's search field, then an injected tap on the 240 px landscape keyboard's `w`. |
| `drawer-bottom-swipe-injected.png` | Injected bottom-edge swipe on Home, after the card shell fix. |
| `overview-bottom-swipe-injected.png` | Injected bottom-edge swipe from the open drawer: the card overview with its shrunk landscape card. |
| `shade-top-pull-injected.png` | Injected top-edge pull-down. |

Injected touches come from `tools/inject-tap.sh` on an `evemu-device` clone
of the real controller, converted from landscape logical `(x, y)` to panel
`(px, py) = (y, 1232 - x)`. They prove routing from libinput onward, not
the glass.

## Camera (`camera-2026-10-13T0852.jpg`)

One C920 frame from the bench camera at the device's top edge, rotated 180°
to the typist's view. The panel is landscape above the keyboard, with the
drawer upright from the keyboard side. It shows orientation only, not touch.

## Operator, real glass

- Before the card-shell fix: "gestures to open the app drawer in the current
  layout don't seem to work. nor settings drawer".
- After it: "my gestures work on the home screen now but i can't swipe up to
  show the cards now either right now". `touch-range.md` gives the cause.
- After a live calibration matrix that matches the device-tree correction
  there: "it works now".

## Defects found and fixed here

1. `k230-shell-rust` was OOM-killed (anon-rss 694 MB) right after
   `home-configure 1232x568`. A 2-row widget never fitted the one-row
   landscape page, so `HomeLayout::place_first_fit` added empty pages
   forever. Reproduced on the host by `place_first_fit_terminates_when_a_widget_is_taller_than_a_page`.
2. The card shell never started in landscape. `cs_default_config(1232, 568)`
   gave an 80%-tall card that `valid_config` rejects. `ensure_ui` then failed
   ("card shell requires one Pixman output"), so the bottom-edge drawer
   swipe, the shade pull-down and the overview were all dead.
3. The touch controller's X range is 0..1079, not 0..1023; see
   `touch-range.md`.

## Installed on the second board — 2026-10-13 09:40 CDT

Bundle `.#kernelMainlineDrmShellLandscapeBootFiles` at `839cba2d`
(`48v1rj39…-k230-coherent-shell-boot-files`, system `06biwlw7…`). It
differs from the installed portrait boot partition only in
`k230-tdisplay.dtb` (sha256 `98beefab…`, `touchscreen-size-x` 0x438) and
`bootargs.txt` (sha256 `722b85e4…`, `init=` the landscape system). `Image`
and `initrd.uimg` are byte-identical. Both files were copied as `.new`,
hash-checked, and renamed into place. The previous pair is kept as
`*.portrait-20261013` on `/boot` and in
`/var/lib/k230/boot-backup-20261013-portrait/` with the previous profile
link. The profile was then set to the landscape system, followed by `sync`
and an ordinary `systemctl reboot` with no U-Boot input.

After boot (serial log kept privately, plus SSH): 7.3.0-rc5; profile, booted
and current system all `06biwlw7…`; the device tree reports
`touchscreen-size-x` 1080; no calibration matrix and no trace drop-in;
`shell`, `shell-ui` and `theme-helper` active; `running` with no failed
units; `k230-shell-rust` RSS 105 MB. `board/installed-home.png` is the
native capture.

This is not the coherent-shell install tool. The board already ran this
repository's own SD image, so only two boot files changed. Rollback: restore
the two `*.portrait-20261013` files and the saved profile link, then reboot.
From U-Boot, use `ums 0 mmc 1` and do the same from the host.

## Reinstalled with the rotate-once renderer — 2026-10-13 ~10:40 CDT

`rotation-performance.md` explains the drawer jank and its fix. The landscape
profile now runs the patched wlroots with `WLR_PIXMAN_OUTPUT_TURN=1`. The
same two-file install as above put bundle `gb7wd950…` (system `xr7d1339…`)
in place. Only the `init=` path in the DTB's `chosen/bootargs` and in
`bootargs.txt` changed; `Image` and `initrd.uimg` are identical. After an
ordinary reboot: booted, current and profile system `xr7d1339…`;
`touchscreen-size-x` 1080; `WLR_PIXMAN_OUTPUT_TURN=1` in sway's environment;
no `/run` drop-ins; services active; `running`. Native capture:
`board/installed-home-output-turn.png`. The operator: "ok yeah it's plenty
fast now".

## Not established here

The 1080 width on the first board, the remaining real-glass checks
(task 8.6) and HDMI (task 8.7).

## Host renders of the remaining 8.3 surfaces (2026-10-14)

`host/` also holds 1232x568 host renders of the Wi-Fi pages, the theme
chooser, the open-folder overlay and the shade with several notifications
(`wifi-*`, `theme-chooser`, `folder-*`, `shade-*-notifications`), written by

    cargo run --offline --example render_landscape_surfaces -- <out-dir>

in `nix/rust-shell-client`, with fixture data from `evidence_render`
(long and short notification text, a critical row, rows with and without a
tap action, one long network name, no theme thumbnails). `host/shade-1232x568.png`
was regenerated for the new shade layout. These are host renders: they prove
the paint and its hit rectangles, not the board's glass. The same example
also writes 568x1232 renders; those are not committed, but are byte-identical
to the base's (`6aa0795d`). Native captures of these surfaces follow.

## Native captures on the installed image (2026-10-14 04:57–05:00 UTC)

System `9lp7f072…` (this branch plus the charger commit), booted, rotate-once
renderer. Each file is a native `grim` at 1232x568, taken as user `shell`.
Surfaces were opened with `k230-shell-rust --surface <name>` unless the name
says `injected` (an `evemu-event` tap written to the touchscreen's event node;
a software proxy, not a finger).

| File | Surface | How opened |
| --- | --- | --- |
| `board/installed-terminal-app.png` | foot terminal, focused app | already open |
| `board/installed-drawer.png` | Drawer | CLI |
| `board/installed-settings.png` | Settings, three columns | CLI |
| `board/installed-power.png` | power sheet | CLI |
| `board/installed-help.png` | Help, two columns | CLI |
| `board/installed-shade-notifications.png` | shade with four notifications from `k230-notifications emit` | CLI |
| `board/installed-wifi-injected.png` | Settings → Wi-Fi, two columns | injected tap on the Wi-Fi row |
| `board/installed-wifi-network-injected.png` | saved-network page | injected tap on the network row |
| `board/installed-theme-chooser-injected.png` | Settings → Themes, chooser and backgrounds side by side | injected tap on `Themes ›`, captured 12 s later once thumbnails loaded |

The two Wi-Fi captures had the connected network's name painted over
(`[name removed]`) before commit; everything else is as captured.

Reviewed: nothing overlaps or leaves the output; every control named in task
8.3 is on screen. The theme chooser shows a spinner over the first card for
the first seconds while backgrounds load; the earlier 2 s capture shows it and
was not kept. Home itself is `board/installed-home.png` and
`board/installed-home-output-turn.png` above.

Still owed for task 8.5: the folder overlay and on-screen keyboard as native
captures on the installed image, and a camera frame from the keyboard side
(the bench webcam currently sits at glass level and cannot read the panel).
