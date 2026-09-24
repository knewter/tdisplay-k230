# Launcher appearance receiver source checkpoint

Observed 2026-09-23. With `k230.shell.themeReceiverTrial = true`, the launcher
has a same-UID, mode-0600 Unix receiver under its existing private `/run/shell`
runtime directory and the command enters the image. The normal configuration
keeps this option off. The receiver accepts a
bounded versioned prepare/commit/rollback request, parses only generated
palette fields from a bounded `report.json`, and changes its current
background, text, muted, tile, selected and accent colors. Error text selects
a contrasting light or dark color. Commit returns an
acknowledgement after the launcher submits and flushes a themed Wayland
buffer; a pending page transition is settled first. Invalid generation IDs,
missing palette data, foreign peers and absent configuration do not produce
successful commit acknowledgements. A restarted receiver loads the previous
generation supplied by the coordinator before switching. The installed
default palette remains when the trial option is off.

```text
python3 tests/test_omarchy_theme_activation.py
  PASS: 7 host tests, including a public-name command which fails closed
  without a receiver and leaves the active pointer absent.
python3 tests/test_omarchy_theme_transaction.py
  PASS: 10 host transport tests.
python3 tests/test_shell_appearance_receiver.py
  PASS: 3 native host receiver socket tests: prepare/commit/rollback,
  pre-prepare rejection, restart restoration, socket mode 0600, and synthetic
  light/dark foreground-to-background/tile/selected/error contrast >= 4.5.
nix build .#touch-launcher --max-jobs 1 --cores 4 --no-link --print-out-paths
  PASS: /nix/store/bix6yarxjgf4zbkv1gsjpb49kh2289gr-k230-touch-launcher
nix build .#handheld-theme-command --max-jobs 1 --cores 4 --no-link --print-out-paths
  PASS: /nix/store/ipfhs2l5km4vxj0iqaf8jzx8myc41ckc-handheld-theme-command-0.1
  Closure: 338,249,992 bytes, dominated by target Python; package is opt-in.
```

This receiver currently styles the installed launcher only, using a subset of
the generated palette. It does not consume full `shell.toml` fields or bind
cards, Settings, notifications, keyboard, wallpaper or applications. The host
fixture has no Wayland compositor or panel, so it proves protocol behavior
but not frame presentation, touch readability or physical rollback. OpenSpec
tasks 2.1/2.2 and the surface tasks remain open pending package/default source
integration, richer token consumption and device evidence.
