## ADDED Requirements

### Requirement: A theme swap does not pay Python start-up on the hot path

<!-- Grounding: docs/evidence/omarchy-themes/background-decode-cache-qemu/README.md
     (board PYTHONPROFILEIMPORTTIME breakdown) for the cost being removed;
     docs/evidence/omarchy-themes/theme-swap-jank/README.md and
     tests/test_theme_helper_daemon.py for this requirement's own proof. -->

When the persistent theme helper (`theme-helper.service`) is running, a
`k230-theme preview` or `k230-theme activate` invocation SHALL NOT import
the theme-activation module chain (`theme_activate`, `theme_transaction`,
`theme_preferences`, `keyboard_appearance`) in its own process; that
invocation SHALL instead delegate the request to the already-warm helper
process over a private, owner-only Unix socket and print exactly the
answer that helper computed. The invocation SHALL fall back to the
unmodified, pre-existing in-process behavior, with no difference in
accepted flags, output shape, or exit codes, whenever the helper socket is
absent, refuses the connection, or does not answer within a bounded
timeout.

#### Scenario: The helper is running

- **WHEN** `theme-helper.service` is active and a person's chooser calls
  `k230-theme preview <id>` then `k230-theme activate <id>
  --expected-generation <g>`
- **THEN** both calls are served by the existing helper process and never
  start a second Python interpreter's worth of theme-activation imports

#### Scenario: The helper is not running

- **WHEN** `theme-helper.service` is stopped, crashed, or mid-restart
- **THEN** `k230-theme preview`/`k230-theme activate` still complete
  correctly, using the same two-phase prepare/commit/rollback protocol and
  producing the same result shape as before this requirement existed

#### Scenario: A malformed or unexpected request reaches the helper

- **WHEN** the helper receives a request it cannot parse or act on
- **THEN** it reports that one request as a failure and continues serving
  every later request without needing a restart
