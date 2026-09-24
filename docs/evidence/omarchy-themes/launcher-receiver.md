# Launcher appearance receiver source checkpoint

Observed 2026-09-23. The launcher now has a same-UID, mode-0600 Unix receiver
under its existing private `/run/shell` runtime directory. It accepts a
bounded versioned prepare/commit/rollback request, parses only generated
palette fields from a bounded `report.json`, and changes its current
background, text, muted, tile, selected and accent colors. Commit returns an
acknowledgement after the launcher submits and flushes a themed Wayland
buffer; a pending page transition is settled first. Invalid generation IDs,
missing palette data, foreign peers and absent configuration do not produce
successful commit acknowledgements. The installed default palette remains
when no theme command is used.

```text
python3 tests/test_omarchy_theme_activation.py
  PASS: 7 host tests, including a public-name command which fails closed
  without a receiver and leaves the active pointer absent.
python3 tests/test_omarchy_theme_transaction.py
  PASS: 10 host transport tests.
python3 tests/test_shell_appearance_receiver.py
  PASS: 1 native host receiver socket test: prepare, commit, rollback.
```

This receiver currently styles the installed launcher only, using a subset of
the generated palette. It does not consume full `shell.toml` fields or bind
cards, Settings, notifications, keyboard, wallpaper or applications. The host
fixture has no Wayland compositor or panel, so it proves protocol behavior
but not frame presentation, touch readability or physical rollback. OpenSpec
tasks 2.1/2.2 and the surface tasks remain open pending package/default source
integration, richer token consumption and device evidence.
