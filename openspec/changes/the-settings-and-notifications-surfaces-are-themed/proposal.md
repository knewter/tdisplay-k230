## Why

Settings and the notification shade already render in the Rust shell, but the
remaining theme proposal still describes the data helpers as separate UI clients
and their compatibility reports do not name the roles actually painted. That
makes theme coverage and unsupported states difficult to verify or close.

## What Changes

- Verify Settings and the notification shade consume the active generation in
  the existing Rust renderer, including startup, commit and rollback. Fix any
  missing consumed colors; preserve the current border-light visual design.
- Report every controls/notifications token as applied, adapted, unavailable
  or unknown. Ordinary borders and absent hover/focus states must not be
  advertised as painted merely because tokens were compiled.
- Provide the named `tests/test_handheld_theme_rendering.py --surface system`
  check: generated payload/report checks plus actual Rust renderer pixel checks,
  with no missing-renderer skip.
- Build the affected components and coherent system closure, then capture
  dark/light Settings and notification scenes and same-surface rollback on the
  reserved physical board.

**Non-goals:** redesigning Settings or notifications, another theme chooser,
new palette roles, separate fake appearance endpoints, kernel or boot changes.

## Capabilities

### Modified Capabilities

- `runtime/shell-themes`: adds the distinct Settings/notification coverage
  requirement through an ADDED delta. This capability already exists; the
  parent theme change remains open for its separate outstanding proof.

## Impact

Userspace only: `tools/theme_tokens.py`, `tools/theme_activate.py`,
`tools/theme_catalog.py`, Rust rendering/compatibility parsing, host tests and
committed board evidence. `nix/handheld-settings.nix` invokes a JSON/action
helper and `nix/handheld-notifications.nix` invokes notification data/actions;
neither paints a Wayland surface. Settings and Shade share the existing Rust
appearance receiver, so the two-phase Rust/deck transaction already covers
both atomically. Host tests do not certify the physical panel.
