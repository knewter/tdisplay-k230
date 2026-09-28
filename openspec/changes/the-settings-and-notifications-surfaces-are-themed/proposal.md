## Why

A person who picks a theme sees it on the shell, the app drawer, cards, the
keyboard and installed apps (Foot), but Settings and notifications stay in
their hardcoded default colors, and there is still no themed chooser surface
of their own. `the-shell-loads-omarchy-themes`'s own delta spec already
promises this ("the corresponding shell, drawer, card, Settings, notification,
keyboard and app appearance adapters retain their intended distinctions"), and
its task 3.3 named the gap explicitly: "Do not tick this while consumers are
only mockups." `nix/handheld-settings.nix` and `nix/handheld-notifications.nix`
are each under 10 lines today — thin command wrappers, not themed UI clients —
so this is real, separable scope, not a rounding error on an otherwise-finished
change.

This is a scope split under `AGENTS.md`'s "Close OpenSpec changes
deliberately": `the-shell-loads-omarchy-themes` is otherwise close to done
(coordinator, activation, backgrounds, keyboard and app-appearance adapters
are implemented and host-tested; what remains there is mostly reserved-board
proof of work already landed). Carrying the Settings/notifications/chooser
gap forward as its own task bullet would either block that change's board
gates on UI work that does not exist yet, or tempt someone into ticking 3.3
against mockups. Splitting it here keeps both pieces honest.

## What Changes

- Give Settings and notifications real themed surfaces: read the active
  generation's `appearance.json` the same way the shell, drawer and card
  renderers already do, and repaint on the same commit/rollback signal
  `theme_transaction.py`'s `--rust-socket`/`--deck-socket` fanout already
  sends. No new palette format, no new activation path, no new build slot.
- Report their coverage in the existing compatibility view
  (`applied`/`adapted`/`unavailable`/`unknown`) instead of silently
  inheriting shell defaults.
- Add the `--surface system` flag `the-shell-loads-omarchy-themes`'s own
  task 3.3 named but never implemented, verifying Settings/notifications
  render with the active palette and that an explicitly absent surface is
  reported, not silently skipped.
- Extend the theme chooser's own presentation (task group 4 of the parent
  change) to these surfaces only insofar as their own screens need a
  background/foreground pass; this proposal does not add a second chooser
  UI.

**Non-goals:** building Settings or notifications from scratch as feature
surfaces (they exist today as minimal command wrappers; giving them a real
window/card presence, if that is wanted at all, is `the-shell-manages-apps-
as-cards`'s or a sibling change's concern, not this one's) — this proposal
only makes whatever surface they do have consume the active theme; adding a
new palette capability beyond what `runtime/shell-themes` already defines;
touching the keyboard or Foot adapters, which are already themed
(`tools/keyboard_appearance.py`, `tools/app_appearance.py`).

## Capabilities

### New Capabilities

None. This targets the same `runtime/shell-themes` capability
`the-shell-loads-omarchy-themes` already proposed. Neither change has
archived, so `openspec/specs/runtime/shell-themes/` does not exist yet;
this change's own delta therefore also uses `ADDED Requirements`, scoped to
exactly the Settings/notification surfaces this proposal implements, rather
than restating the parent's broader requirement. Whichever of the two
changes archives first fixes the base spec; the other then syncs against it
normally. This is the scope split `AGENTS.md` requires: it lets
`the-shell-loads-omarchy-themes` close its own task 3.3 as satisfied by
drawer/card/keyboard/app coverage plus this named successor, instead of
leaving one Settings/notifications bullet open indefinitely.

## Impact

`nix/handheld-settings.nix`, `nix/handheld-notifications.nix` (or their
replacement, if giving them a real appearance receiver means they stop being
one-file wrappers), `tools/theme_transaction.py`'s receiver fanout (adding
two more optional endpoints, following the existing `--rust-socket`/
`--deck-socket` pattern rather than a new one), and
`tests/test_handheld_theme_rendering.py --surface system`. Host-provable:
reading a generation's `appearance.json` and repainting from it needs no
board. Whether the result actually reads correctly on the panel, in both a
dark and a light theme, still needs the reserved board — this proposal does
not claim that gate closed by construction.
