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

Removing the interpreter-start-up tax is the single largest, cleanly
separable, host-and-QEMU-provable piece of the instant-swap target; it is
not the whole target. Left open, and not claimed complete here:

- **In-memory buffer swap on commit.** The wallpaper's decoded/cached pixels
  are not yet held in memory for a previewed-but-not-yet-applied theme;
  commit still triggers `BackgroundCache::render`'s normal cache-hit or
  decode path in the Rust event loop, not a pure pointer/buffer swap.
- **Prepare-ahead on carousel centering.** Preparing a generation (and its
  `background.cache`) when a theme becomes the centred chooser item, before
  Apply, is chooser UI territory (`theme_carousel.rs`/`theme_ui.rs`),
  explicitly out of this change's owned paths (see coordination note in the
  task that produced this change).
- **Deferred keyboard/foot recolour.** `keyboard_appearance.sync_and_restart`
  (a `wvkbd` process restart) and Foot's OSC recolour still run
  synchronously inside `activate`'s response, before `activated: true` is
  reported; making the visible swap not wait on them is a follow-up.
- **Two-phase transaction reordering.** No requirement or code path here
  changes prepare/commit/rollback's ordering or its acknowledgement
  contract; every activation observed in this change's tests goes through
  the exact existing protocol.

A successor change should pick up the remainder; this one is deliberately
kept to the piece it can prove end to end without touching either the
chooser UI or the Rust commit path.

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
