## 1. Drawer

- [x] 1.1 Start the drawer sheet at the top edge, with no top corner radius there, and keep the handle, search and Help positions relative to it. Draw Help as the search field's themed control at its height, with its label centred. Draw tile labels at a medium weight. Proof: `cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml --lib` and a landscape render from `examples/render_landscape_surfaces.rs`.

## 2. Apps

- [x] 2.1 Override Viewnior's desktop entry to run with `GDK_BACKEND=wayland`.
- [x] 2.2 Give btop its own desktop entry: `k230-foot` with a font size that gives at least 24 rows in landscape.
- [x] 2.3 Let `k230-foot` take `--app-id`; give each terminal-launched app (2048, NetHack, btop, Clock, Timer, Weather) its own id and matching `StartupWMClass`.
- [x] 2.4 Write `k230-term-apps` (clock, timer, weather) and point the Clock, Timer and Weather entries at it. Proof: `python3 -m unittest tests.test_term_apps`.
- [x] 2.5 Install distinct icons: sgt-puzzles' own icons from the build platform; new SVGs for 2048, NetHack, Clock and Timer.
- [x] 2.6 Name Nautilus "Files" and hide Portfolio's entry (`NoDisplay=true`).
- [x] 2.7 Build the landscape system. Proof: `nix build .#nixosConfigurations.k230-mainline-drm-shell-landscape-hdmi.config.system.build.toplevel`.

## 3. GTK theming

- [x] 3.1 Generate `gtk-3.0/settings.ini` and `gtk-3.0/gtk.css` per theme generation in `tools/app_appearance.py`, and link them into `~/.config/gtk-3.0` without replacing files the adapter did not write. Add `button-layout=':close'` to the GTK4 keyfile and regenerate the packaged defaults. Proof: `python3 -m unittest` on the appearance tests.

## 4. Shade

- [x] 4.1 Draw the count line only above zero; centre the empty state in the list column; format battery as "<percent>% · <state>"; give the keyboard tile an action description. Proof: `cargo test` as 1.1 and a landscape shade render.

## 5. Settings

- [x] 5.1 Move Vision and Themes into the title row. Draw a divider and a fade at the scrolled body's top edge. Show Wi-Fi as "Connected"/"Not connected" and Motion as "Reduce motion". Drop the audio subtitle's suffix. Proof: `cargo test` and `python3 -m unittest` for `tools/device_settings.py`'s tests, plus landscape renders.

## 6. Themes

- [x] 6.1 Fade carousel items at their column edges. Proof: a landscape theme-chooser render.

## 7. Home

- [x] 7.1 Centre a packed dock once (seed and existing layouts). Omit zero readings in Battery – Details while the battery is idle, and add "On charger". Keep Weather's temperature clear of its glyph. Proof: `cargo test` and widget renders from `examples/render_battery_details_evidence.rs` and `render_widget_evidence.rs`.

## 8. Overview

- [x] 8.1 Start sway with the launcher's `XDG_DATA_DIRS` so desktop-entry names and icons resolve. Treat a plain tap on the overview's bottom band outside every card as a backdrop tap (Home). Proof: the landscape system build.

## 9. Board (hardware-only)

- [x] 9.1 Test-activate the build and capture every surface and app with grim (injected touch). Each finding from the review must be absent; record the captures' check results in `docs/evidence/shell-design-review/`. Captures that show private data are not committed.
- [ ] 9.2 The operator looks over the shell and apps on glass and confirms the result. Physical proof: a timestamped operator report tied to the installed build.
- [ ] 9.3 Promote the build from master to the boot default and verify an ordinary boot.
