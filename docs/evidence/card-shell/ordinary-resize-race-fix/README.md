# Ordinary-app resize race: root cause and fix

Follows on from `docs/evidence/card-shell/app-switch-swipe-frame-capture/README.md`
("Finding 2: one 'ordinary' floating window's percentage resize can stick at
its pre-resize size"), which reproduced but did not root-cause the bug. This
directory records the root cause, the fix, and before/after evidence, all
under headless QEMU with injected input — no board or panel proof.

Base revision `fa1f54e6` (branch `fix/ordinary-resize-race`, worktree
`../k230-ordinary-resize`).

## Root cause

Sway's own `handle_commit` (`sway/desktop/xdg_shell.c`) treats the client's
surface geometry on **any** commit as an authoritative client-initiated
resize: for a floating container it calls `view_update_size()`, which copies
`view->geometry` straight into the container's pending size, no matter what
the compositor wants that container's size to be.

On the very first commit that maps a view, `view->geometry` is whatever the
client's implicit xdg-surface geometry happened to be **before** it has
reacted to any compositor-driven configure — its own natural, pre-resize
size. That same commit is also the one in which `card_shell ordinary,
floating enable, resize set 100 ppt 100 ppt, move position 0 0` (the board's
`for_window` rule, run from `view_map()`) already resized the container to
the output's full usable area. `handle_commit`'s `view_update_size()` call
runs immediately after that, on the same commit, and stomps the container's
`pending` size straight back down to the client's stale natural size.

A card that is the one currently shown recovers immediately: `wlr_scene`
keeps sending it frame-done callbacks, its client redraws at the real
(correct) size on the next callback, and that later commit's `view->geometry`
now matches, so `view_update_size()` no longer disagrees with the compositor.
A card that is **not** currently shown never receives another frame-done
(`wlr_scene_output` only sends frame-done to surfaces it actually
composites), so it never redraws, never commits again, and stays wrongly
sized until it is finally shown and its client repaints under a different
geometry — which is exactly the "stays at the synthetic client's
pre-configure default" symptom the earlier finding observed, and matches the
reported dark-band/frame-mismatch behaviour during an app switch on the
board.

This is a generic Sway/wlroots race, not a bug in `nix/card-shell/adapter.c`'s
own card geometry, plate, or gesture code, and not specific to the synthetic
probe client — any client that does not immediately redraw at its new size
(because it is currently hidden behind another card) hits it.

Confirmed with targeted `sway_log` instrumentation added temporarily to a
local build (not committed): a `DIAG_VIEW_UPDATE_SIZE` trace showed the
non-visible window's container pending size flip from `568x1232` (correct,
just set by `resize set 100 ppt`) to `480x720` (the client's natural size)
inside `view_update_size`, with no further correcting call for that window
for the rest of the run — while the visible window's container recovered a
commit or two later via its own real repaint.

Deterministic repro: `/tmp` diagnostic harness (`diag-single.py`, not
committed — a stripped-down variant of `tools/repro-app-switch-swipe.py`
that just maps N apps and reads `get_tree` after a settle) against the
pre-fix build:

* 1 ordinary app, 8 trials: 0/8 ever stuck.
* 2 ordinary apps, 10 trials: 10/10 had exactly one window stuck at
  `480x720` (which one varied across runs, consistent with a race rather
  than an ordering rule).
* 3 ordinary apps: also reproduces (not exhaustively counted).

## Fix

`nix/card-shell/adapter.c` and `nix/patches/sway-k230-card-shell.patch`: the
compositor now re-asserts ordinary-maximized geometry after **every** commit
of a mapped view, not only once at map time and on usable-area changes.

* New `card_shell_commit(struct sway_view *view)` (declared in
  `nix/card-shell/card-shell.h`, implemented in `nix/card-shell/adapter.c`)
  calls the existing `ordinary_resize()` unconditionally for the commit's
  view; `ordinary_resize()` already no-ops when the container isn't a
  floating ordinary-maximized one, or when its geometry already matches the
  output's usable area, so this is cheap on every other commit.
* The patch calls `card_shell_commit(view)` from `handle_commit` in
  `sway/desktop/xdg_shell.c`, **after** the existing `new_size`/
  `view_update_size()` block (not before, unlike the pre-existing
  `card_shell_observe(view)` call, which runs before that block and is a
  one-shot registration hook, so it cannot by itself catch this race). Any
  clobber `view_update_size()` just made to a marked ordinary container's
  pending size is corrected within the same commit, before the next frame
  renders — regardless of whether the client ever redraws at the right size
  again. `card_shell_observe()` now calls `card_shell_commit()` too, instead
  of duplicating the same `ordinary_resize()` + `transaction_commit_dirty()`
  pair.
* Keyboard-drag behaviour is unchanged: `ordinary_sync_usable()` /
  `card_shell_usable_area_changed()` still own re-arranging every
  ordinary-maximized card (and the backdrop) when the output's usable area
  itself changes (e.g. `wvkbd` mapping/unmapping); the new per-commit hook
  only adds a second, independent path back to the same target geometry and
  never touches the backdrop.

## After: same deterministic repro, fixed build

* 1 ordinary app, 6 trials: 0/6 stuck (unchanged from before the fix).
* 2 ordinary apps, 12 trials: 0/12 stuck (was 10/10 before the fix).
* 3 ordinary apps, 6 trials: 0/6 stuck.

`tests/test_card_shell_usable_area_runtime.py` (the pre-existing two-marked-
ordinary-apps-plus-real-`wvkbd` regression test) is flaky on **both** builds
on this loaded host at an unrelated checkpoint (`workspace height == 812`,
i.e. wvkbd's own exclusive-zone timing under `qemu-riscv64-static`, nothing
to do with this fix) — 2/5 timeouts on both the pre-fix and post-fix builds
there. Its actual geometry assertions (`ordinary` rect values at each stage)
passed every time they were reached, on both builds before the keyboard, and
on the post-fix build after it. On the pre-fix build, when the run got far
enough, the *specific* assertion this fix addresses (`hidden = wait_for(...
all ordinary boxes == 568x1232 ...)`, the final check after the keyboard
hides again) also timed out once (see console output in the change's
handoff), consistent with this bug.

## Frame strips

`tools/repro-app-switch-swipe.py`'s bottom-edge swipe between two ordinary
apps, one frame per injected touch step, `frame-009-*` being midway through
the swipe (`x=280`) where the earlier finding's stuck window showed dark
top/bottom margins:

| | before (pre-fix, `10ah65ss79cf82p9ayrlpiisqm9cxl0x-sway-unwrapped-…`) | after (fixed, `lnjpkscmg65x0gq6dmhmghhnxxrcz9wr-sway-unwrapped-…`) |
| --- | --- | --- |
| baseline (one app focused) | `before-frame-000-baseline.png` | `after-frame-000-baseline.png` |
| mid-swipe (`x=280`) | `before-frame-009-motion-x280.png` | `after-frame-009-motion-x280.png` |
| settled after release | `before-frame-025-settle.png` | `after-frame-025-settle.png` |

The "before" mid-swipe and settle frames show `k230.card.one` (blue) stuck at
its natural `480x720` in the corner, with `k230.card.two` (purple) — which
should be entirely offscreen or entirely onscreen depending on swipe
progress — filling the rest of the panel through the gap; the settle frame
still shows the split after the gesture completes, i.e. exactly the reported
"odd frame-to-frame changes" / residual dark-band defect. The "after" frames
show both apps at full `568x1232` throughout, with a clean single-app
transition and no residual split at settle.

All frames are QEMU/headless-injected-touch evidence; none of this is a
board or panel observation.

## Regression coverage

`tests/test_card_shell_ordinary_resize_race.py` adds a repeat-launch check
(new probe app mapped and unmapped, alongside one already-shown app, 12
times) asserting every ordinary app ends at the output's full usable size,
plus a bottom-edge app-switch-swipe frame check (reusing
`tools/repro-app-switch-swipe.py`'s own capture logic) asserting every
captured frame after the first shows both windows' visible regions
accounted for at full output size (no residual split).
