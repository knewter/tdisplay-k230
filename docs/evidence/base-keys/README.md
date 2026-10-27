# The base keys launch apps and drive the overview: evidence

Change: `openspec/changes/the-base-keys-launch-apps-and-drive-the-overview/`.

## Host (tasks 1.1, 1.2)

- `cargo test --offline` in `nix/rust-shell-client`: all targets ok,
  including `a_key_focused_search_launches_on_enter_and_clears_then_closes_on_esc`
  and the route-socket test's `drawer-keys` case.
- The system build `xk69fsf7238xkgsh5808y40xf282i4la` compiled the patched
  Sway with `overview_key_mode`.

## Board, injected keys (tasks 2.1, 2.2)

Board 2026-10-27, test-activated `xk69fsf7238xkgsh5808y40xf282i4la` (commit
`98a154e2`), shell restarted at 03:15Z. `ui.py.txt` here is the driver: it
adds a second uinput device, "K230 injected keyboard", for the `key` action.
That device is not the base, so the base-only LILYGO release binding does not
match it; the driver runs that binding's exec, `k230-shell-rust --surface
drawer-keys`, instead. LILYGO+Tab has no device filter and was injected as a
real chord. No person touched the board.

| UTC | Action | Observed |
|---|---|---|
| 03:15:51 | `surface drawer-keys` | Drawer open, search focused, on-screen keyboard down (`board/keys-drawer-open.png`). |
| 03:15:53 | keys `t` `i` | Search reads "ti"; Timer is the one match, outlined (`board/keys-drawer-ti.png`). |
| 03:15:55 | Enter | Timer launched (`board/keys-after-enter.png`); `apps` listed `k230-terminal`, `k230-timer`. |
| 03:16:18 | LILYGO+Tab | Overview with Timer chosen (`board/keys-overview.png`). |
| 03:16:47 | LILYGO+Tab, Left, Enter | Terminal chosen, then in front. Its prompt line was empty: no `ti`, arrow or Enter had reached it. |
| 03:17:0x | keys `echo ok`, Left, Right | Typed into the terminal; the arrows moved its cursor. `get_binding_state`: `default`. |
| 03:17:29 | LILYGO+Tab, Right, Backspace | Timer's card closed ("App closed"); `apps`: `k230-terminal` only; mode `overview` while the deck stayed up. |
| 03:17:3x | Esc | Mode `default`. |
| 03:17:4x | LILYGO+Tab, then a tap on the card | Mode `overview`, then `default` after the touch exit. |
| 03:17:5x | Bottom-edge swipe into the overview, then Esc | Mode `overview` when entered by touch, `default` after Esc. |

Terminal frames are not committed. The terminal line was cleared with
Backspace afterwards.

Remaining: the operator on the real base (task 2.3), including the LILYGO
release binding on the base's own device.
