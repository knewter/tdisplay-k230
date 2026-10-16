# Side-edge Back on the board by injected pointer, 2026-10-16

Evidence class: **injected events** on HDMI (a uinput mouse through
`/tmp/bp.py`, i.e. `tools/board-pointer.py`) with `grim` captures and the
compositor's own `K230_CARD_SHELL side-back target=N` log lines. This is not
real touch, so the "feels right from a real finger" judgement that task 1.3
asks for is still open.

- System: `/nix/store/m1c3jq413s8acils9y6jrpdk02xq5lmz-nixos-system-nixos-26.11.20260919.20b1ddd`,
  live-deployed from `integ-1016` at `f082393a`, which includes this change's
  `ec1bf497`. It landed rebased as `3a912936`.
- Output: HDMI-A-1 at 1280x720.

The mouse button path enters the same `input_down` recognizer as touch
(`card_shell_pointer_button` → `input_down(CARD_POINTER_ID, …)`).

| Case | Injected swipe (px) | Log | Result |
| --- | --- | --- | --- |
| Shade open, left edge, inward | (10,360)→(160,364), 300 ms | `side-back target=2` | Shade closed (`1-shade-open…`, `2-after-left-side-back…`) |
| Shade open, right edge, inward | (1275,520)→(1120,522) | `side-back target=2` | Shade closed |
| Plain Home, left edge, inward | (10,300)→(160,305) | none | Home unchanged |
| Shade open, 30 px inward | (10,520)→(40,520) | none | Shade stays open |
| Shade open, right edge, outward | (1240,520)→(1279,520) | none | Shade stays open |
| Shade open, top-left corner, inward | (10,10)→(160,14) | none | Shade stays open (top band belongs to the Shade) |
| Fullscreen terminal (no shell context) | (10,300)→(160,305) | none | Terminal unchanged; no stray keystroke at the prompt |

## Not covered: keyboard target

With wvkbd shown, the injected mouse swipe was not claimed. The touch reached
the Shade under it: a left-edge swipe at y=300 dragged the Shade's volume
slider to zero, and it was dragged back to its earlier position afterwards
(`3-keyboard-shown-swipe-not-claimed…`). The same happens to the existing
top-edge Shade pull from Home while the keyboard is shown. So this predates
side Back: with the keyboard visible, `input_down` returns before the
touch-first edge block for the pointer path. The cause was not isolated; the
two failures were tracked to `input_down` returning false, and wvkbd maps two
layer surfaces, not an xdg popup.

The keyboard step of the dismiss order (`target=3`) therefore has host-fixture
proof only. It needs a real touch on the panel, or a pointer-path fix, before
task 1.3 can close.

## Keyboard target after the popup fix (2026-10-16, panel)

Evidence class: **injected events** on the panel (DSI-1, 1232x568
landscape, HDMI unplugged): a uinput mouse through `/tmp/bp.py`
(`tools/board-pointer.py`), `grim` captures, and the compositor's
`K230_CARD_SHELL side-back target=N` lines. This is not real touch.

The cause of the failure above was wvkbd 0.20's key-preview `xdg_popup`.
wvkbd keeps it mapped while the keyboard is shown, so the card shell
treated it as an open menu and skipped every touch-first edge. Commit
`b3c44dd0` (rebased from `630fa3f2`) ignores a popup that lies inside the
keyboard's own rectangle extended upward by its height.

- System: `/nix/store/6mmvyyasczi0xsgw9hx2bhx6vrlycr07-nixos-system-nixos-26.11.20260919.20b1ddd`.
  It was built from integration branch `integ-cma-popup` at `84b8b993`,
  which contains this fix, the 64 MiB CMA change and the vision redesign.
  It was installed and soft-rebooted at 15:41.
- The keyboard was shown with `SIGUSR2` to the supervised wvkbd.

| Step | Injected swipe (px) | Log | Result | Capture |
| --- | --- | --- | --- | --- |
| Keyboard shown on Home | — | — | Keyboard up | `4-panel-keyboard-shown-1232x568.png` |
| Top-edge pull | (400,2)→(400,300), 400 ms | — | Shade opened over the keyboard | `5-panel-keyboard-top-pull-opens-shade-1232x568.png` |
| Left edge, inward | (3,200)→(160,204), 300 ms | `side-back target=2` | Shade closed, keyboard still shown | `6-panel-side-back-closes-shade-keyboard-stays-1232x568.png` |
| Left edge, inward again | (3,200)→(160,204), 300 ms | `side-back target=3` | Keyboard dismissed | `7-panel-side-back-dismisses-keyboard-1232x568.png` |
| Settings opened (Shade, then "Settings") | (400,2)→(400,300); tap (402,40) | — | Settings (at the board's saved vision step) | `8-panel-settings-1232x568.png` |
| Left edge, inward | (3,300)→(160,304), 300 ms | `side-back target=2` | Settings closed to Home | `9-panel-settings-side-back-1232x568.png` |

So the dismiss order (sheet, then keyboard) holds on the board for the
pointer path. Injected pointer swipes from the bottom edge and the dock did
not open the drawer, so the drawer case is not covered here. Real-finger
feel stays open.

## Long-press menu before the drawer (2026-10-16 23:18Z)

Source: branch `side-back-sheet`. The adapter's overlay step now sends
`back`; the Rust client closes an open long-press app menu and otherwise
hides like `hide`. The board ran
`/nix/store/5vj9z6z0ims1svg437qncsv7y2p5hw2z-nixos-system-…`, built from
integration commit `e71dabce`. That is this change plus the clock restyle
commit, with no other source. It was deployed live with
`switch-to-configuration test`.

Method: on the landscape panel, a uinput mouse through `/tmp/bp.py`
(`tools/board-pointer.py`), with native `grim` captures. The drawer was opened
with the shell socket's `drawer` route.

Evidence class: injected pointer input. There was no finger on the glass.

| Step | Injected input (px) | Log | Result | Capture |
| --- | --- | --- | --- | --- |
| Drawer open | socket `drawer` | — | Drawer | `10-panel-drawer-open-1232x568.png` |
| Long-press "Clock" | `hold 616 190 900; up` | `app-menu-open`, `app-menu-ready rows=3` | App menu (Open, New Window, Add to Home) | `11-panel-long-press-menu-1232x568.png` |
| Left edge, inward | (3,300)→(160,304), 300 ms | `side-back target=2`, then `app-menu-dismiss` | Menu closed; the drawer is still open | `12-panel-side-back-closes-menu-drawer-stays-1232x568.png` |
| Left edge, inward again | (3,300)→(160,304), 300 ms | `side-back target=2` | Drawer closed to Home | `13-panel-side-back-closes-drawer-1232x568.png` |

While the menu is open the drawer is not drawn behind it (capture 11). That
is the existing menu presentation and was not changed here.

The compositor still reports `target=2` (overlay) for the menu, because the
menu is on the same `k230-shell-drawer` layer. The Rust client makes the
menu-first decision. `sheet_open()` in the adapter stays false by design (see
its comment).
