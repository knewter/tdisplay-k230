# The overview opens All apps: board evidence

Change: `the-overview-opens-all-apps`. Evidence class: board, injected touch
and keys through `/var/tmp/ui.py` (copy at `docs/evidence/base-keys/ui.py.txt`),
native `grim` captures. Not a glass interaction.

## Failing runs, kept for the record

- Build `dhmp8mdi…` (master `8b4f7d73`), 2026-10-27 ~03:33Z:
  `overview-title-row.png` (cropped to the title row, without the terminal card) shows the label. A tap at (1140, 40) logged
  `home selected` and Home appeared, but no drawer.
- Build `prk64sjw…` (drawer request deferred to the settle's end): the same.
  Logging added in the next build showed the cause: the edge-band path
  tested the hit after `edge_reset()` had zeroed the tap point.

## Passing run

Build `/nix/store/vzizj58rrns7nnhdw55zjlzjadav4vv8-nixos-system-nixos-26.11.20260919.20b1ddd`
(commit `49052b4d`), test-activated and `shell` restarted, 2026-10-27 03:44Z:

    tap 300 505        # Terminal from the Home dock
    key LEFTMETA+TAB   # overview
    tap 1140 40        # All apps ›

Compositor log:

    K230_CARD_SHELL edge backdrop tap x=1141 y=40 apps=1
    K230_CARD_SHELL overview apps: settling Home
    K230_CARD_SHELL home selected cards=1
    K230_CARD_SHELL overview apps: drawer requested

`after-tap-drawer.png` is the drawer open over Home 2.5 s after the tap.
