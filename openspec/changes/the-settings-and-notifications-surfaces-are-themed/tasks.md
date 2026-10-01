Surface ownership reconciled 2026-10-01 after reading the helpers and actual
Rust renderer. This supersedes the assumed extra-endpoint plan without dropping
startup, commit/rollback, role coverage, full-build or physical proof.

## 1. Find out what Settings and notifications actually are

- [x] 1.1 Read `nix/handheld-settings.nix` and `nix/handheld-notifications.nix`
  end to end. Record, in this change's own `design.md` (updating its "Open
  Questions" section rather than guessing here), whether each is a rendered
  surface at all today, or purely a command wrapper with nothing to repaint.
  If either has no rendered surface, say so before task 2 assumes one.
- [x] 1.2 Identify the exact palette fields a themed Settings/notifications
  surface would consume, cross-checking against `theme_tokens.py`'s existing
  `sections["controls"]`/`sections["notifications"]` output (already
  asserted present by `tests/test_handheld_theme_rendering.py::
  test_real_helper_output_becomes_bounded_native_payload`) so this task adds
  no new palette role.

Proof: 1.1/1.2 are a reading exercise; record findings in `design.md`, not a
command.

## 2. Wire the appearance fan-out

- [ ] 2.1 Prove that the existing Rust/deck prepare/commit/rollback transaction
  covers Settings and Shade through their shared Rust scene owner; no separate
  endpoint exists for either JSON/action helper. Run the existing two-receiver
  failure/rollback suite and actual renderer generation/rollback regression.
  Verify `python3 -m unittest tests.test_omarchy_theme_transaction` and
  `cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml`.
- [ ] 2.2 Make the Settings/notifications surface(s) read a generation's
  `appearance.json` on startup and on the existing commit/rollback signal,
  the same way the Rust shell and Sway deck already do. If task 1 found no
  rendered surface at all for one of them, this task's own scope is limited
  to giving it the minimal surface needed to be themed, not a redesign.

Proof: `python3 -m unittest tests.test_omarchy_theme_transaction` and the
relevant client's own unit tests (host).

## 3. Report coverage honestly and prove it on the host

- [ ] 3.1 Add the `--surface system` flag to
  `tests/test_handheld_theme_rendering.py` that `the-shell-loads-omarchy-
  themes`'s own task 3.3 named but never implemented. It SHALL assert every
  Settings/notifications role this change claims and fail (not skip) on one
  left unthemed.
- [ ] 3.2 Confirm the compatibility report (`applied`/`adapted`/
  `unavailable`/`unknown`) names each Settings/notifications role by name;
  add a host regression for a role with no themeable equivalent reporting
  `unavailable` rather than being silently omitted.

Proof: `python3 tests/test_handheld_theme_rendering.py --surface system`
and the added compatibility-report regression, both host-only.

## 4. Prove it on the actual handheld

- [ ] 4.1 Build the affected outputs individually, then the full
  `nixosConfigurations.k230-coherent-shell` toplevel; record the exact
  closure and source identities. Needs no board.
- [ ] 4.2 On the reserved board, activate a built-in dark theme and a
  built-in light theme in turn; open Settings and trigger a notification
  for each. Capture native `grim` screenshots showing each surface's colors
  match the active generation, and that a rollback restores the previous
  generation's colors on the same surface. Commit the captures and the
  exact commands under `docs/evidence/omarchy-themes/settings-notifications-
  themed/`.

Proof for 4.1: the named `nix build`/toplevel evaluation. Proof for 4.2: the
committed native captures and exact board commands; a host test does not
establish this by itself.
