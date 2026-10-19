# The rest of the shell's text on the type roles

Change: `openspec/changes/the-rest-of-the-shell-text-takes-the-type-roles`.
Evidence class: host renders unless a section says otherwise.

- `host-home-widgets-steps.png`: `render_accessibility_scale_evidence`
  (`<step>-home-small-<size>.png`) over catppuccin generations, flattened
  onto a teal backdrop and cropped. Left column: 1232x568 at 100% (top) and
  200% (bottom). Right: 568x1232 at 100% and 200%. Battery and Weather
  2x2 cards, a folder and apps with stock names (tasks 1.1, 1.2).
- `host-banner-1232x568.png`, `host-banner-568x1232.png`: the top 140 px of
  `render_notification_banner_evidence`'s trusted-source banner at 100%
  (task 2.1).
- `host-help-steps.png`: `<step>-help-568x1232.png` from
  `render_accessibility_scale_evidence` at 100%, 125%, 150% and 200%,
  side by side at half size (task 2.2). At 200% the rest scrolls.
- `host-help-wide.png`: from top, 1232x568 at 125% and 200% (catppuccin
  generations), then `render_responsive_evidence`'s `help-1232x568.png`
  (100%) and `help-1920x1080.png` scaled to 1232 wide.
- `host-wifi-{100,200}-568x1232.png`: `<step>-wifi-*-568x1232.png` at
  100% and 200%, half size, left to right: the list, a password entry with
  the 440 px keyboard raised and a rejection, a saved network, connecting,
  and the forget confirmation (task 2.2).
- `host-wifi-{100,200}-1232x568.png`: the same five pages on the landscape
  panel (240 px keyboard on the entry page), two per row, half size.
  Limits: SSIDs and the single-line status messages still end in "…" when
  too long; at 200% with the keyboard raised the Entry page pans its
  header and network card off the top, by design.
- `host-themes-steps-568x1232.png`: `<step>-themes-568x1232.png` at 100%,
  125%, 150% and 200%, half size: the portrait chooser with seven fixture
  themes. Thumbnails are not decoded in this renderer, so cards show their
  loading spinners; the text and card sizes are the evidence.
- `host-themes-1232x568.png`: the landscape chooser at 100% (top) and 200%,
  half size. With seven themes the grid's cards would be about 94 px wide,
  too narrow for role-size names, so the panel shows the carousels;
  monitors keep the grid (unit test).
- `host-menu-splash-{568x1232,1232x568}.png`: the app actions (recovery)
  menu with three rows, then the "That window has closed" recovery splash,
  each at 100% and 200%, half size (`<step>-menu-*`, `<step>-splash-*`).

Limits: no board captures yet (task 3.1). The volume HUD's expanded rows
are covered by unit tests only; they need streams playing on the board.

## Board (2026-10-19 UTC)

Native `grim` captures on DSI-1 (1232x568), retro-82 with the vinyl
wallpaper, 100%, reached with `tools/board-pointer.py` swipes.

- `board-panel-100-home.png`: Home page 1 from the a23e199a closure; the
  "Video" label is in the 26 px Caption role.
- `board-panel-100-home-weather.png`: Home page 2 from the e11757ee closure
  (`/nix/store/am78j36v3kx1zvqmgbixv2qi0qqzwafz-nixos-system-…`); the
  Weather card's location, high/low and forecast in the Caption role. The
  e11757ee fix exists because the a23e199a closure showed "12…" for
  "12am" in this card.
