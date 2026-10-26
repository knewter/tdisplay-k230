## Context

On 2026-10-26 a design review captured every shell surface and drawer app on
the board with grim. The captures are not committed: they show the device
and its settings. Code locations were mapped before this design:

- the drawer's 32 px inset is `navigation::panel_top`;
- Settings clips its body with a hard rectangle at `settings_body_top`;
- sway runs without `XDG_DATA_DIRS`, so `desktop_identity` in `adapter.c`
  reads `/run/current-system/sw/share`. That has foot's own `foot.desktop`,
  not the shell's override carrying `StartupWMClass=k230-terminal`;
- viewnior's nixpkgs wrapper sets `GDK_BACKEND=x11` by default, and the
  image has no Xwayland;
- the sgt-puzzles icons are skipped when cross-compiling.

## Goals / Non-Goals

- **Goal:** every review finding fixed in the image, with a fresh home
  getting the result.
- **Non-goal:** redesigning layouts or gestures beyond what each finding
  needs.

## Decisions

- **Viewnior:** a desktop-entry override runs it with `GDK_BACKEND=wayland`.
  The nixpkgs comment says zoomed panning misbehaves under Wayland; an
  image viewer that opens is better than one that cannot. Not Xwayland,
  which the image rejects for cost.
- **btop:** its own desktop entry launches `k230-foot` with a
  `--override font=…:size=14` so the panel gives at least 24 rows. The
  terminal's size 15 stays for everything else.
- **Terminal apps get app ids.** `k230-foot` accepts `--app-id`, and each
  terminal app's desktop entry passes its own id and sets the matching
  `StartupWMClass`. Cards then resolve that entry's name and icon.
- **Clock, Timer and Weather:** one Python script, `k230-term-apps`, with
  three modes. Python is already in the closure (the keyboard base daemon).
  - Each mode draws centred block-glyph digits in the terminal and follows
    the terminal's theme colours.
  - Timer enables SGR mouse reporting so taps on "Start/Pause", "+1 min",
    "−1 min" and "Reset" work on glass.
  - Weather reads the Home widget's cached wttr.in `j1` JSON
    (`~/.cache/k230-shell/weather.json`) and fetches it when missing or
    older than 30 minutes, so the app and the widget agree.
- **Icons:** the puzzle icons are taken from the build platform's
  sgt-puzzles (PNG, architecture-independent), installed in a small hicolor
  package. 2048, NetHack, Clock and Timer get our own flat SVGs in one
  style.
- **One Files entry:** Nautilus, named "Files". Portfolio keeps its package
  and launcher but its entry is `NoDisplay=true`.
- **GTK3 theming:**
  - `k230-app-appearance` writes `gtk-3.0/settings.ini` and `gtk-3.0/gtk.css`
    into each generation, built from the theme palette.
  - The generation is linked from `~/.config/gtk-3.0` when it is applied.
  - The CSS sets window, view and button colours, the accent, a 13 pt font
    and 44 px minimum control heights.
  - The GTK4 keyfile gains `button-layout=':close'`; GTK3 gets
    `gtk-decoration-layout=:close`.
- **Settings scrolling:** the body is still clipped at `settings_body_top`.
  A hairline divider is drawn there and a 20 px gradient from the page
  background, so nothing is cut against bare background.
- **Overview tap:** a plain tap in the bottom band that hits no card is a
  backdrop tap (Home), as the Shade and Back bands already are.
- **Dock centring moves the items once.** A display-only offset would make
  the icons jump when a drag starts and needs a second slot mapping for
  hit tests and drop targets. Instead a dock packed against its start with
  two or more free slots is rotated so the free slots split between both
  ends: when a layout is seeded, and once for a saved layout (a
  `dock_centred` flag, absent in older files). After that the person's own
  arrangement stands; a dock with a gap inside its run is left alone.

## Risks / Trade-offs

- `~/.config/gtk-3.0` may already hold someone's own settings. The adapter
  replaces only files it wrote before, which are marked by a header comment,
  and otherwise leaves them alone.
- Viewnior panning while zoomed may misbehave on Wayland.
- Hiding Portfolio narrows the file-manager evaluation to one candidate in
  the drawer.
