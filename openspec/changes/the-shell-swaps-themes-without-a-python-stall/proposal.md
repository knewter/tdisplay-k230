## Why

Choosing a theme freezes the handheld for 2.8-3.5 s on the board
(`docs/evidence/omarchy-themes/background-decode-cache-qemu/README.md`),
during which touch and animation stall and the person sees no feedback
until the swap either completes or is rejected. About 1.2 s of that is paid
twice per Apply (`preview` then `activate`), and it is pure Python
interpreter start-up and import cost, not theme work: a bare `k230-theme
--help` takes 1259 ms against 71 ms for `runuser` alone, and
`PYTHONPROFILEIMPORTTIME` attributes most of that to importing
`theme_activate`/`dataclasses`/`inspect`. The user's stated target is a
swap visible within about one frame (roughly 100 ms) of the Apply tap, with
touch and animation never stalling.

## What Changes

- Add a persistent `theme-helper.service` (`tools/theme_helperd.py`) that
  imports `tools/theme_catalog.py`'s dependency chain once and serves every
  later `list`/`preview`/`activate` request over a private Unix socket by
  calling that same module's `build_parser()`/`handle()` -- the identical
  code a fresh CLI invocation already ran, reviewed and evidenced, so this
  changes *when* the import cost is paid, never the two-phase
  prepare/commit/rollback protocol itself.
- Replace `k230-theme`'s wrapped entry point with `tools/theme_client.py`,
  an argv-compatible front end that talks to that socket without importing
  `theme_catalog` (and so not its own heavy dependents) unless it actually
  falls back -- board evidence blamed that import chain, not bare
  interpreter start-up, for most of the 1.2 s, so a client that eagerly
  imported it regardless of the daemon would not have removed the cost it
  exists to remove.
- The client falls back to the unmodified, pre-existing in-process path
  (never a second subprocess) whenever the daemon socket is missing,
  refused, or slow to answer, so a board that has not yet picked this up,
  or whose daemon crashed and is mid-restart, still switches themes
  exactly as it does today -- only without the speed-up.
- Add `tools/theme-swap-jank.py` (a root, board-side capture tool) and
  `tools/analyze-theme-swap-jank.py` (a host-side report) so tap-to-visible
  latency and per-frame gaps become a measured, reproducible number instead
  of a felt impression, for this change and for the remaining work it does
  not do (below).

## What This Does Not Do (explicit remainder, not a silent gap)

Removing the interpreter-start-up tax was the first, cleanly separable,
host-and-QEMU-provable piece of the instant-swap target. Three more pieces
have since landed in this same change:

- **In-memory buffer swap on commit** (task 3.1b, done). The Rust
  chooser's `BackgroundCache` (`background_decode.rs`) is now a small
  bounded LRU rather than a single slot, so browsing a second candidate no
  longer evicts a first one's decode before its own commit lands. The
  compositor (`nix/card-shell/appearance.c`/`adapter.c`) gained a matching
  advisory `prepare` hook that pre-builds the deck's gradient
  (`card_brush_scene`) for the *candidate* generation, adopted at commit
  instead of repainted -- with the same "missing/stale falls back to the
  old inline path, never breaks correctness" posture `background.cache`
  itself already had.
- **Prepare-ahead on carousel centering** (task 3.2, done). `theme_ui.rs`'s
  `ThemeView::poll_prepare_ahead`, wired from `main.rs`'s existing per-tick
  carousel-settle loop, warms a theme once it has been the carousel's
  centred item, at rest, for a short debounce -- reusing the existing
  `preview` action/reply (already calling `prepare_only()`) with no new
  protocol, and never surfacing that reply to the chooser's own navigation
  state.
- **Deferred keyboard recolour** (task 3.3a, done).
  `keyboard_appearance.sync_and_restart` (the `wvkbd` restart) now runs on
  a background thread from `theme_catalog.py`'s `activate` handling, so
  `theme-helper.service`'s reply to the chooser no longer waits on it.
- **Skip a redundant re-prepare on an already-warm Apply** (task 6.3,
  done). `theme_transaction.activate_generation()` now remembers, per
  receiver, which generation it last successfully prepared, and skips
  sending a second `prepare` to a receiver already holding the exact
  generation being committed -- retrying with a real prepare, transparently,
  if a stale assumption turns out wrong, so correctness never depends on
  the memory being right.
- **Optimistic Apply** (task 6, done; see this change's own spec delta's
  new requirement). Board evidence after the above still showed 397 ms
  from tap to commit -- short of the user's original ~100 ms target. The
  user explicitly approved showing an already-prepared generation
  immediately, ahead of the durable commit, rather than continuing to trim
  the durable path's own remaining cost (a pointer swap, preference
  write, and app-sync round trip that cannot itself be skipped without
  risking correctness). This does not touch the two-phase protocol's own
  acknowledgement contract -- see the next paragraph, revised from an
  earlier version of this proposal that read as ruling this out
  permanently, which is no longer accurate now that the user has approved
  it.

**On the two-phase transaction's acknowledgement contract specifically**:
no requirement or code path in this change ever alters what a receiver's
own `prepare`/`commit`/`rollback` exchange requires to succeed, or the
"ack only after a real, flushed frame" rule each receiver's own handling
already applied before this change. Optimistic Apply adds a rendering side
effect *alongside* that protocol -- gated strictly on a receiver's own,
already-prepared state, never substituting for or shortening the real
exchange -- so every activation still goes through the exact same
prepare/commit/rollback acknowledgement sequence as before; only when the
chooser's own *display* reflects a generation the receiver already holds
prepared has changed, not when that generation becomes durably active.

Left open, and not claimed complete here:

- **Deferred Foot recolour** (task 3.3b). Foot's OSC/config-file recolour
  is folded into `activate_generation()`'s own `app_sync` call inside
  `theme_transaction.py`, whose return value is part of that function's
  existing, tested, synchronous contract; deferring it needs either
  restructuring that contract or a second, separate deferred call, left
  for a follow-up rather than risked here.
- **Two-phase transaction ordering and acknowledgement contract.** Still
  unchanged, including by Optimistic Apply above: no requirement or code
  path here reorders prepare/commit/rollback or alters what a receiver's
  own exchange requires to ack. What did change (with the user's explicit
  approval) is *when the chooser's own display* reflects an already-
  prepared generation, which is now allowed to run ahead of, rather than
  strictly after, that generation's own durable commit -- see this
  proposal's "Optimistic Apply" paragraph above and this change's spec
  delta for the exact, narrow scope of that difference.
- **Compositor fanout wiring.** This change's Optimistic Apply work adds a
  best-effort "show" message the chooser may send directly to the
  compositor's own appearance socket, but does not wire the two-phase
  transaction's own `--rust-socket`/`--deck-socket` fanout into
  `nix/shell.nix`'s `theme-helper.service` -- that remains whatever other,
  separate work is landing it (see `impl/card-appearance-endpoint` in this
  repository's own worktree list). Until that fanout is wired, the
  compositor side of this requirement is present and tested in isolation
  but has nothing live to receive it from in production.
- **The board number** (tasks 2.3/3.4). Every board measurement this
  change's own tasks call for still needs the reserved board; this
  change's throttled-QEMU captures are directional estimates in the
  meantime (see `docs/evidence/omarchy-themes/theme-swap-jank/`).

A successor change should pick up 3.3b; this one now covers the buffer-swap
and prepare-ahead pieces end to end, still without the board's own number.

## Capabilities

### Modified Capabilities

- `runtime/shell-themes`: adds a swap-latency requirement (this capability
  itself has not yet been archived from `the-shell-loads-omarchy-themes`,
  so the delta here is `ADDED`, not `MODIFIED`, per
  `.skills/k230-spec-change/SKILL.md`'s archive-time check).

## Impact

`tools/theme_catalog.py` (refactored, behavior-preserving split into
`build_parser()`/`handle()`), two new tools
(`tools/theme_helperd.py`/`tools/theme_client.py`), one new systemd unit
(`nix/shell.nix`'s `theme-helper.service`), and
`nix/handheld-theme-command.nix`'s wrapper target. Host-testable end to
end (`tests/test_theme_helper_daemon.py`, `python3 -X importtime` proof
that the fast path avoids the heavy import chain). The absolute board
number (this change's actual contribution to the 2.8-3.5 s budget) needs
the reserved board; QEMU-under-`qemu-riscv64-static` and host timings in
this change's evidence are directional, not the K230's real number, because
neither reproduces the K230's in-order core.
