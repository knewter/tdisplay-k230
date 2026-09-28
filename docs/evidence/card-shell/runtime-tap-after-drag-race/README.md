# `tests/card_shell_runtime.py` pre-existing flake: tap-after-drag race

Evidence class: **host-only** (QEMU-injected input under
`qemu-riscv64-static`, real cross-built Sway; no board, no physical touch).
This fixes a test-harness bug found while closing out
`the-card-shell-has-no-video-special-case`'s task 4.2, not a compositor
behavior change.

## What was reported

Task 4.2 recorded that `tests/card_shell_runtime.py`'s
`wait_for(lambda:focused()=='k230.card.two')` assertion (after a full
horizontal deck drag followed by an immediate tap) was already failing
against the pre-change baseline (commit `59e0eb78`), unrelated to that
change's own diff.

## Root cause

Confirmed by reproducing directly (`python3 tests/card_shell_runtime.py
--sway <sway> --client <client> --rgb565`, no board):

1. `cs_up` (`nix/card-shell-policy/card-shell-policy.c`) resolves a
   released horizontal drag by updating `p->selected` to the new card
   **synchronously**, but deliberately does **not** re-center that card:
   `scroll_from_dx` is chosen so the newly selected card's on-screen
   position stays *continuous* with wherever the drag left it, then eases
   to center under its own momentum over up to `config.reduced_motion==
   false`'s 760ms bound (`cs_up`'s own comment: "the settled card's
   on-screen x must not jump at the instant of release").
2. `cs_down` (same file) hit-tests a fresh touch against the *current,
   still-animating* geometry: on a coast, it calls `cs_tick(p, time_ms)`
   using the real wall-clock time of the IPC call before hit-testing.
3. The test fired `command('down 2 284 450'); command('up 2')` (a tap at
   the panel's horizontal center) **immediately** after `command('up 1')`
   ended the drag, with no wait for the coast. Depending on scheduler
   timing (worse under shared-host load), the tap could land while the
   just-selected card was still off-center, so it either missed or hit a
   different card than the one `cs_up` had already selected.

This is real, intentional product physics (`cs_up`'s continuity design),
not a compositor bug, and reproducing it does not require the video
special-case removal — it was present at commit `59e0eb78` already.

A second, independent flake was found while reproducing this one: the
`during-drag.png` capture at `x==184` in the same drag loop
(`subprocess.run(['grim', ...])` immediately after an IPC `motion` command)
could run before the compositor's next scheduled frame had actually been
composited, especially under the heavily loaded shared host this session
ran on (`uptime` showed ~18-19 load average across 32 cores while
reproducing this). `docs/evidence/brightness-slider/README.md` already
documents the same class of host-load sensitivity for a different QEMU
harness.

## Fix

`tests/card_shell_runtime.py`:

- After the drag-release (`command('up 1')`), wait `0.9s` (past the
  policy's documented 760ms worst-case coast) before the confirmatory tap,
  so the tap lands on the settled, centered card instead of racing the
  coast animation.
- The `during-drag.png` capture at `x==184` now polls
  (`wait_for(during_drag_moved)`) instead of asserting a single
  immediately-taken screenshot, mirroring this file's own `wait_for`
  convention used elsewhere in the same script.

Neither change touches compositor source (`nix/card-shell*`); both are
confined to test synchronization in `tests/card_shell_runtime.py`.

## Verification

Narrow proof command (from `tests/`, matching the task's own required
invocation):

```
python3 -m unittest test_card_shell_scaled_cache_runtime -v
```

Result: **PASS**, both the `SWAY_K230_CARD_SCALED_CACHE=0` and `=1` runs
(`off` and `on`), reusing the cached `.#card-shell` build
(`/nix/store/j57c5im42d3rq5gxdar2ikmh22717zvc-k230-card-shell`, unwrapped
Sway `/nix/store/0a2f857nc1rz65gnjdfn46h32zsyxm18-sway-unwrapped-
riscv64-unknown-linux-gnu-1.12`) and the native
`card-composition-probe-client`
(`/nix/store/yjb89ap4bq5vb29szdzkr5sv9lpw1sz6-card-composition-probe-
client-0.1`). Also reproduced clean twice more by invoking
`tests/card_shell_runtime.py` directly with the same binaries and
`--rgb565` (no unittest wrapper).

Unaffected suites confirmed unchanged by inspection: `--two-axis` and
`--touch-first` both `return` before reaching the edited code path, so
`test_card_shell_two_axis_runtime.py`, `test_card_shell_touch_first_
runtime.py` and `test_card_shell_home_bleed.py` (which drives
`--home-layer-client` through the two-axis path) exercise different lines
entirely. Both of those suites were observed independently flaking on
this same shared, loaded host during this session (different assertions,
earlier in their own paths) — that is the same pre-existing host-load
class documented in `docs/evidence/brightness-slider/README.md`, not a
regression from this diff, and is out of this task's scope.

## Limits

QEMU-injected-input proof only; no board, no real finger, no panel. This
fix makes the existing host regression deterministic again; it makes no
claim about physical drag/tap timing.
