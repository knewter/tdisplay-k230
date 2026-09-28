## Context

`the-shell-loads-omarchy-themes` built the whole activation path: a
compatible `omarchy-theme-set NAME` coordinator (`tools/theme_activate.py`,
`tools/omarchy-theme-set`), a two-phase prepare/commit/rollback transaction
(`tools/theme_transaction.py`) that fans a generation's `appearance.json`
out to named receivers over `--rust-socket`/`--deck-socket`, a keyboard
adapter (`tools/keyboard_appearance.py`) and an app (Foot) adapter
(`tools/app_appearance.py`). The Rust shell (`nix/rust-shell-client`) and the
Sway deck (`nix/card-shell/appearance.c`) both already consume that fan-out
for the shell, drawer and card chrome. That machinery is generic — it does
not know or care how many receivers there are.

Settings (`nix/handheld-settings.nix`) and notifications
(`nix/handheld-notifications.nix`) are not receivers at all today; each file
is under 10 lines, a thin wrapper around a command. They have no appearance
state to update and nothing subscribes to a generation's commit.

## Goals / Non-Goals

- Goal: Settings and notifications read the active generation's resolved
  colors the same way the shell already does, and repaint (or re-render,
  depending on what "Settings"/"notifications" turn out to mean once looked
  at directly) on the existing commit/rollback signal.
- Goal: an absent-surface report stays honest — if a given Settings/
  notification element has no themeable equivalent, the compatibility view
  says so by name, per the parent change's own "Compatibility and physical
  completion are explicit" requirement.
- Non-goal: redesigning Settings or notifications as richer app surfaces.
  If they deserve a bigger UI, that is a separate, product-shaped decision
  for a different change; this one only makes whatever exists consume the
  active theme.
- Non-goal: a second theme chooser. The existing carousel
  (`nix/rust-shell-client/src/theme_ui.rs`) stays the only place a person
  picks a theme or background.

## Decisions

- Reuse `theme_transaction.py`'s existing named-endpoint fan-out
  (`--rust-socket`, `--deck-socket`) rather than inventing a third transport.
  Whatever Settings/notifications turn out to be (a third Wayland client, a
  library the Rust shell links, or a mode of one of the existing binaries)
  gets its own optional `--endpoint` pair following that same convention, so
  `activate_generation()`'s all-or-nothing prepare/commit/rollback contract
  keeps covering it for free.
- Do not invent new palette roles. `theme_tokens.py`'s existing
  `sections["controls"]`/`sections["notifications"]` (already present in the
  compiled appearance payload — see
  `tests/test_handheld_theme_rendering.py::test_real_helper_output_becomes_
  bounded_native_payload`, which already asserts a `notifications` section
  exists) are the palette this proposal wires up, not a new one.
- First task group is investigation, not implementation: `nix/handheld-
  settings.nix`/`nix/handheld-notifications.nix` have not been read closely
  as part of this audit, and "give them a themed appearance" cannot be
  scoped precisely until it is clear what they currently render (if
  anything) versus merely invoke.

## Risks / Trade-offs

- Settings/notifications may turn out to be pure command wrappers with no
  rendered surface at all yet (plausible, given their current file size),
  in which case this proposal's real content is "add the surface, then
  theme it" — larger than "theme an existing surface." Task group 1 below
  exists specifically to find that out before committing to an implementation
  shape.
- Reviewed captures (dark and light) are a board gate like everything else
  in this project's theme work; this proposal inherits that constraint
  rather than working around it.

## Migration Plan

None — additive. No existing generation, receiver, or palette shape changes.

## Open Questions

- Does "Settings" already exist as a distinct app/surface anywhere in this
  repo, or is `nix/handheld-settings.nix` the entire thing today? Task 1.1
  answers this before any wiring is attempted.
