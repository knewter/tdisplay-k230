# On-screen keyboard colours: host checkpoint

Observed 2026-09-24 from integration base `69e23b3f`, on branch
`impl/keyboard-theme`. This closes task 3.3's keyboard slice only (see
`tasks.md`'s `3.3.k`); Settings, notifications and the touch chooser
integration under 3.3 remain open and are not claimed here.

## What wvkbd actually accepts

`wvkbd-mobintl --help` (pinned nixpkgs `20b1ddd1aa5ace70c9468305030aa4f9ef79671b`,
package `wvkbd-0.20`) confirmed the exact flag set used: `--bg`, `--fg`,
`--fg-sp`, `--press`, `--press-sp`, `--text`, `--text-sp` (each
`rrggbb[aa]`), plus `--hidden` ("Start hidden (send SIGUSR2 to show)"). There
is no live-recolor IPC; colours are read only at process start.

## Source

`tools/keyboard_appearance.py`. Its input is an already-acknowledged theme
generation's bounded `report.json` palette (the same file
`app_appearance.py` reads). It writes only
`keyboard-appearance/generations/ID/{wvkbd.args,coverage.json}` under private
theme state, and publishes a separate `keyboard-appearance/active` pointer
for the supervised launcher — mirroring `app_appearance.py`'s own
generation-cache and activation-lock conventions (it reuses
`app_appearance.activation_lock` and `theme_transaction._pointer`, wrapped
under this module's own `KeyboardAppearanceError` so callers need not import
`app_appearance`'s exception type). `sync()` rejects a foreign pointer or
foreign generation directory and reports whether the resolved colours
actually changed, so a restart is never triggered for a no-op resync.

## Colour mapping

Seven flags map onto the same palette roles the card/grip appearance
contract (`nix/card-shell/adapter.c`) already uses, so the keyboard reads as
the same surface family:

| flag | palette key |
| --- | --- |
| `--bg` | `background` |
| `--fg` | `dark_background` |
| `--fg-sp` | `darker_background` |
| `--press` | `selection` |
| `--press-sp` | `lighter_background` |
| `--text` | `foreground` |
| `--text-sp` | `bright_foreground` |

All seven keys are present in every `report.json` produced by the pinned
upstream resolver (`omarchy-theme-color --all`), including the packaged
Catppuccin default and the media-free recovery generation, which this
checkpoint confirmed have identical palettes.

## Restart, without a race

wvkbd cannot be recolored live, so a theme change restarts the process.
`keyboard_appearance.restart()` never manages the process directly: it sends
a same-uid `SIGTERM` to `wvkbd-mobintl`, exactly the existing
`k230-keyboard-gesture-signal` show/hide convention (same-uid
`pkill -USR1/-USR2`). It only does this when
`$XDG_RUNTIME_DIR/k230-keyboard-supervised` exists — a sentinel the
supervised launcher (`k230-supervised-keyboard` in `nix/shell.nix`) writes
right after it finds the session's Wayland socket, on every start. Without
that sentinel (the non-coherent-shell legacy `swayConfig`-exec'd keyboard,
which nothing resupervises), `restart()` reports
`{"restarted": false, "reason": "not-supervised"}` instead of killing a
keyboard that would then stay dead. systemd's `shell-keyboard` unit already
carries `Restart = "always"; RestartSec = 3;`, so the relaunch is bounded.

Shown/hidden state survives the restart without any post-restart signal
replay: `k230-keyboard-gesture-signal` now also persists
`$XDG_RUNTIME_DIR/k230-keyboard-visible` (`show`/`hide`) whenever the
compositor's gesture policy calls it, and the launcher reads that marker at
its *next* start to decide whether to pass `--hidden` at all — sidestepping
any assumption about when a freshly started wvkbd is ready to receive a
signal.

## Wiring into activation

`theme_activate.py`'s `--activate` path and `theme_catalog.py`'s `activate`
action each call `keyboard_appearance.sync_and_restart(...)` immediately
after the existing `activate_generation(...)` call, passing
`expected_generation` so a superseding activation is reported rather than
recoloring to a stale generation. This is deliberately *not* wired inside
`theme_transaction.activate_generation()` itself: that function's return
shape and call graph are exercised by dozens of existing assertions across
several actively-edited test files (`test_omarchy_theme_transaction.py`,
`test_paired_theme_endpoints_runtime.py`, `test_real_theme_paired_runtime.py`),
and changing its default behavior for every caller was a larger, riskier
blast radius than this task needed. Both CLI entry points now report
`keyboard_appearance` in their JSON output, independent of `app_appearance`'s
own status, so a keyboard-colour failure never revisits an already-
acknowledged shell generation (same non-blocking convention as
`app_appearance.sync`).

## Packaged default

`nix/handheld-theme-default/wvkbd.args` is a pinned static file (same pattern
as `terminal-foot.ini`/`monitor-foot.ini`), generated and checked by
`tools/generate_default_keyboard.py` (`--check` mode). `default.nix` installs
it into both the bundled Catppuccin and the media-free recovery generation
directories; both currently have identical palettes, so the same file is
correct for both, exactly like the existing Foot configs. The supervised
launcher falls back to this file when no theme has ever been activated
(fresh home) or the active pointer/file is missing or malformed (checked by
counting exactly 14 lines).

## Commands run and results

```text
python3 tests/test_handheld_keyboard_theme.py -v   PASS 15 host tests
python3 tests/test_handheld_app_themes.py           PASS 9 host tests
python3 tests/test_handheld_theme_rendering.py       PASS 3 host tests
python3 tests/test_handheld_theme_default.py         PASS 3 host tests
python3 tests/test_omarchy_theme_activation.py       PASS 9 host tests
python3 tests/test_omarchy_theme_transaction.py      PASS 18 host tests
python3 tests/test_theme_catalog.py                  PASS 9 host tests
python3 tests/test_theme_preferences.py              PASS 9 host tests
python3 tests/test_omarchy_theme_resolution.py       PASS 4 host tests
python3 tests/test_omarchy_theme_sources.py          PASS 5 host tests
python3 tests/test_omarchy_theme_tools.py            PASS 2 host tests
python3 tools/generate_default_keyboard.py --check   PASS (no drift)
nix eval .#nixosConfigurations.k230.config.system.build.toplevel.drvPath
  -> /nix/store/8k3hyx5x9l086bpy0h7qiq7qisz50bll-nixos-system-nixos-26.11.20260919.20b1ddd.drv
nix build --no-link --max-jobs 1 --cores 4 .#handheld-theme-default .#handheld-theme-command
  -> built; both generation dirs contain wvkbd.args; k230-theme/omarchy-theme-set
     wrappers carry --pkill <cross procps>/bin/pkill
python3 tests/test_handheld_theme_bundle.py --package <built handheld-theme-default>
  -> PASS (includes the new wvkbd.args identity check)
openspec validate the-shell-loads-omarchy-themes --strict   valid
openspec validate --all --strict                             31 passed, 0 failed
```

`bash -n` was also run against both edited/added `nix/shell.nix` script
bodies (`k230-keyboard-gesture-signal`, `k230-supervised-keyboard`) with
their Nix string interpolations placeholder-substituted, since neither
script is separately exposed as a buildable flake attribute; this proves
syntax only, not runtime behavior.

## What remains unproven

No board, QEMU, or real-glass evidence exists for this change: whether the
restart is visually imperceptible or causes a frame of default-colour
flash, whether focus is actually preserved through the restart, whether the
shown/hidden marker round-trips correctly against the compositor's own
`shell.keyboard.progress` state machine on real touch gestures, and whether
`RestartSec = 3` is an acceptable perceived delay are all `<!-- UNVERIFIED
-->` and need the reserved board. Settings/notifications/chooser keyboard
surfacing (the rest of task 3.3) and the `--surface system` test-flag
machinery are separately unimplemented.
