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

### Requirement: A warm Apply shows the new appearance ahead of the durable commit

<!-- Grounding: user decision (2026-09-25 coordinator message): "The user
     has explicitly approved the optimistic theme apply." Justification:
     board evidence (docs/evidence/omarchy-themes/instant-theme-swap/
     board-chooser-2026-09-25.md) showed tap-to-commit at 397 ms even after
     removing the redundant re-prepare, still short of the user's original
     ~100 ms target ("theme swaps should be instant"), with the remaining
     cost inside the durable two-phase commit's own pointer-swap,
     preference, and app-sync work -- none of which the receivers'
     already-prepared, already-validated resources need to wait on merely
     to be drawn. Proof: nix/rust-shell-client/src/main.rs
     (`should_apply_optimistically`, `optimistic_apply_due`,
     `show_theme_optimistically`), nix/card-shell/appearance.c (the `show`
     phase), and their own tests. -->

When an Apply tap's target generation is already the Rust receiver's own
`prepare`d snapshot, the chooser SHALL render that appearance -- the
wallpaper, and every other Rust-shell surface driven by it -- on the very
next frame, without waiting for the durable two-phase commit (still
dispatched, unchanged, and left to settle to completion asynchronously).
This SHALL NOT alter the two-phase protocol's own acknowledgement contract
in any way: a receiver's `prepared`/`active` bookkeeping, and the "ack only
after a real, flushed frame" rule each receiver's `commit`/`rollback`
handling already applies, remain exactly as before this requirement: the
optimistic render is a side effect additional to that protocol, never a
substitute for its own eventual, authoritative commit or rollback. A
generation that is not already prepared SHALL continue to show the
pre-existing busy/pending state on Apply and SHALL NOT be prepared early
merely to make it eligible for this requirement. When the compositor can be
reached directly, the same already-prepared candidate MAY also be shown
there immediately, on the same advisory, side-effect-only basis (never
altering its own two-phase bookkeeping either); this is a best-effort
optimization, not a correctness requirement in its own right, since the
durable commit's own real `commit`/`rollback` message to the compositor
settles its display correctly regardless of whether this arrives.

#### Scenario: An already-prepared Apply shows on the next frame

- **WHEN** a person taps Apply for a theme the chooser has already prepared
  (by browsing to it, by prepare-ahead of a carousel neighbour, or by a
  previous identical Apply) and the wallpaper surface is ready for a new
  frame
- **THEN** the new appearance is rendered and flushed before the durable
  commit's own reply arrives, and the tap-to-shown latency is logged

#### Scenario: The durable commit later succeeds

- **WHEN** an Apply was shown optimistically and the durable two-phase
  commit subsequently acknowledges successfully
- **THEN** the receiver's own `active` snapshot and every other durable
  record (the active pointer, preferences, app appearance) settle to match
  exactly what is already on screen, with no further visible change

#### Scenario: The durable commit later fails

- **WHEN** an Apply was shown optimistically and the durable two-phase
  commit subsequently fails for any reason
- **THEN** the visible appearance is rolled back to the previous
  generation and the chooser shows a clear, specific error; at no point
  after the transaction settles does the screen show a theme that is not
  the durably active one

#### Scenario: A cold, unprepared theme is never shown optimistically

- **WHEN** an Apply targets a generation the chooser's receiver has not
  already prepared
- **THEN** the chooser shows its pre-existing busy/pending state and waits
  for the durable commit, exactly as before this requirement, with no
  early or speculative preparation triggered merely to qualify

#### Scenario: A rapid second Apply is not confused by the first

- **WHEN** a person applies one already-prepared theme, and before or
  shortly after that transaction settles applies a second, different
  already-prepared theme
- **THEN** each Apply's own optimistic check and shown appearance are
  scoped to that Apply's own request, and the second Apply is never
  suppressed or corrupted by bookkeeping left over from the first

#### Scenario: Rendering ahead of Apply never shows anything before it is confirmed

- **WHEN** a candidate theme's appearance is rendered ahead of time, while
  it is only being previewed
- **THEN** that rendering never becomes visible on any surface, and never
  alters what any ordinary (non-Apply) redraw shows, until an Apply tap
  actually requests it

#### Scenario: A render made ahead of Apply is discarded, not reused, if anything it depended on changed

- **WHEN** a theme's appearance was rendered ahead of an Apply tap, and
  before that tap the surface's geometry changed, the chooser navigated to
  a different page, or other on-screen content it captured changed
- **THEN** Apply falls back to rendering fresh rather than showing that
  stale render, with no incorrect or outdated content ever reaching the
  screen
