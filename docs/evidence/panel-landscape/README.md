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

## Not established here

The installed (non-trial) landscape image, the new device tree's 1080 width
on either board, and HDMI (task 8.7).
