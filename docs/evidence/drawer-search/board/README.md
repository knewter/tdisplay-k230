# Drawer search: board evidence

Build `f73q3409…` (commit `c5b75097`) on 2026-10-28, test-activated with
`switch-to-configuration test` and `systemctl restart shell`. Evidence
class: injected board. Keys came from `/var/tmp/ui.py`'s uinput keyboard,
and taps were uinput touch. `surface drawer-keys` runs the exec of the
base's LILYGO binding, because that binding is scoped to the base's device
and cannot match the uinput keyboard. Captures are native `grim`.

## 3.1 LILYGO, query, Enter, with the terminal in front

Before each run the terminal (`k230-terminal`) was focused. The key log is
the `ui.py` action string itself: `surface drawer-keys; key w i f i; key
ENTER`, then the same with `a b o u t` and `t i`.

- `wifi-typed.png`: one row, "Wi-Fi · Settings". After Enter the Wi-Fi page
  opened. `wifi-opened-title.png` is cropped to the page title, because the
  rest of that page shows network names.
- `about-typed.png`: "About · Settings". `about-opened.png` shows the About
  page. The on-screen keyboard was raised over it after Enter. This is noted
  as a defect and not investigated.
- `ti-typed.png`: Timer (App) first, then Date & time, Location and Reduce
  motion (Settings). After Enter, `get_tree` showed `k230-timer` focused and
  `ti-opened.png` shows it.
- `term-before.png` and `term-after.png`: the terminal held a clean prompt
  before and after all three runs, so none of the typed keys reached it.

## 3.2 Query typed on the on-screen keyboard

`shell-idle` was stopped for this run, because a 30 s idle dim opened the
exhibition clock mid-test twice. A tap on the search field (560, 46) raised
the on-screen keyboard (`osk-raised.png`; the marker read `show`). Taps on
its `t` and `e` keys typed the query.

- Rows that fit above the keyboard at 100 %: one full result row and the
  top part of a second (`osk-t.png`, `osk-te.png`). The second is cut at the
  keyboard's edge, and the list scrolls.
- Frame time (`drawer-frame-osk.txt`, the shell's always-on, rate-limited
  `K230_DRAWER_FRAME` line): 143.22 ms for the first frame after the `t`
  keystroke and 39.76 ms for the `e` frame. This is the drawer's own render
  cost, not the end-to-end latency to the panel. Only rate-limited frames are
  logged.
