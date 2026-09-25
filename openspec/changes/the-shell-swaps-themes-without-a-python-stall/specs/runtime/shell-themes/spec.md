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

### Requirement: Commit adopts an already-prepared candidate instead of redoing its work

<!-- Grounding: nix/rust-shell-client/src/background_decode.rs (BackgroundCache,
     a bounded in-memory LRU) and nix/card-shell/appearance.c/adapter.c
     (the `prepare` callback and `appearance_canvas_refresh`'s adopt path),
     both read; tests/background_decode_module.rs and
     tests/test_card_shell_appearance.py for this requirement's own proof. -->

Each of the two appearance receivers (the Rust chooser/wallpaper client and
the Sway/card-shell compositor) SHALL retain, in memory, the decoded
wallpaper or built gradient for at least the most recently prepared
candidate generations (bounded, not unbounded), so that a `commit` for any
of those candidates adopts the already-prepared result -- a buffer/pointer
swap plus redraw -- rather than re-decoding a wallpaper or repainting a
gradient. A candidate that was never prepared, or whose prepared state was
evicted or does not match the commit's own generation/geometry, SHALL fall
back to the pre-existing inline decode/paint; this requirement never
changes what is rendered, only whether that work is repeated.

#### Scenario: A previously prepared candidate is committed

- **WHEN** a generation was prepared (directly, or via the chooser's
  browse-ahead warm-up) and nothing since has evicted its retained state
- **THEN** the matching `commit` adopts that retained wallpaper/gradient
  without a fresh decode or Cairo paint

#### Scenario: Browsing a second candidate does not evict the first

- **WHEN** a person previews candidate A, then candidate B, while A has not
  yet been committed
- **THEN** a later `commit` for A is still a guaranteed in-memory hit,
  bounded to a small recent-candidate history rather than a single slot

#### Scenario: An unprepared or superseded candidate still commits correctly

- **WHEN** `commit` arrives for a generation that was never prepared, or
  whose prepared geometry/brush no longer matches
- **THEN** the receiver falls back to its existing inline decode/paint and
  the commit still succeeds

### Requirement: The chooser warms a candidate ahead of a likely Apply

<!-- Grounding: nix/rust-shell-client/src/theme_ui.rs (poll_prepare_ahead/
     prepare_ahead_submitted/prepare_ahead_reply) and main.rs's per-tick
     carousel-settle hook, both read; theme_ui.rs's own unit tests for this
     requirement's proof. -->

While the Themes list page is open and its carousel is at rest (no drag,
coast, or settle animation in progress) on one theme for a short, bounded
dwell time, the chooser SHALL issue a best-effort warm-up request for that
theme, bounded to a small number of requests in flight at once, without
navigating the chooser or otherwise becoming visible to the person browsing.
A theme passed through while the carousel is still moving, or superseded by
a different centred theme before its own dwell time elapses, SHALL NOT
itself cause a warm-up request.

#### Scenario: Dwelling on a theme warms it

- **WHEN** a theme stays the carousel's centred item, at rest, for the
  chooser's debounce interval
- **THEN** a warm-up request for that theme is issued, and its reply never
  changes the chooser's displayed page, list, or preview state

#### Scenario: A fast flick warms nothing per slice

- **WHEN** the carousel is dragged or coasting across several themes
  without settling
- **THEN** no warm-up request is issued for any theme only passed through

#### Scenario: The already-active theme is never warmed

- **WHEN** the carousel settles on the theme that is already active
- **THEN** no warm-up request is issued, since there is nothing to prepare
