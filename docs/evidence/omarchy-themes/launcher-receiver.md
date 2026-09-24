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
python3 tests/test_launcher_navigation.py
  PASS: 3 existing launcher navigation tests with appearance.c linked.
nix build .#touch-launcher --max-jobs 1 --cores 4 --no-link --print-out-paths
  PASS: /nix/store/g8w8w38v6g2rfb162fvbbkkj208b2hb4-k230-touch-launcher
nix build .#handheld-theme-command --max-jobs 1 --cores 4 --no-link --print-out-paths
  PASS: /nix/store/8hg86rs0yfxsc0a7lcbnbyh3d18i6wcx-handheld-theme-command-0.1
  Closure: 338,250,352 bytes, dominated by target Python; package is opt-in.
nix eval --json .#nixosConfigurations.k230.config.k230.shell.themeReceiverTrial
  PASS: false in normal configuration.
nix eval --impure --json --expr 'let f = builtins.getFlake (toString ./.); c = f.nixosConfigurations.k230.extendModules { modules = [ { k230.shell.themeReceiverTrial = true; } ]; }; in { enabled = c.config.k230.shell.themeReceiverTrial; installed = builtins.any (p: (p.pname or "") == "handheld-theme-command") c.config.environment.systemPackages; }'
  PASS: {"enabled":true,"installed":true} in an opt-in evaluation; no image built.
```

This receiver currently styles the installed launcher only, using a subset of
the generated palette. It does not consume full `shell.toml` fields or bind
cards, Settings, notifications, keyboard, wallpaper or applications. The host
fixture has no Wayland compositor or panel, so it proves protocol behavior
but not frame presentation, touch readability or physical rollback. OpenSpec
tasks 2.1/2.2 and the surface tasks remain open pending package/default source
integration, richer token consumption and device evidence.
