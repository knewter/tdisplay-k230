# Two-axis card entry, synthetic native QEMU

On 2026-09-24, `tests/test_card_shell_two_axis_runtime.py` ran the actual
cross-built Sway card shell under headless QEMU with two public synthetic
Wayland clients (`k230.card.one` blue and `k230.card.two` purple). Sway's
test-only native Wayland touch handler injected one contact through the real
compositor input and scene paths. No physical board or touch panel was used.

Source `532115c23074fdc390e21efd1417d43b7aedc294`; exact build:

```text
nix build .#card-shell --max-jobs 1 --cores 4 --no-link --print-out-paths --show-trace
/nix/store/516x3gx841c565f5p3ql0jgqwxs02g3i-k230-card-shell
```

Its unwrapped compositor was
`/nix/store/ixamm5fj89083y41g55x8p46wfsgbllf-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`.
The immutable client was
`/nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client`.

```sh
CARD_SHELL_SWAY=/nix/store/ixamm5fj89083y41g55x8p46wfsgbllf-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  python3 tests/test_card_shell_two_axis_runtime.py
# PASS two-axis app entry: native QEMU pixels, hold/reversal, quick opposite,
# privacy and exit; no physical touch
# Ran 1 test ... OK
```

The full screenshots were reviewed. On a 100 px upward drag, the blue client
mask's lower edge moved from y=1086 to y=976 (110 px; proportional scaling
changes the visible edge slightly). At the same vertical position, a 134 px
leftward drag moved its right edge from x=504 to x=370, exactly 134 px. A 1 px
horizontal bend did not alter vertical bounds; a stationary hold retained the
same bounds. Reversal moved the blue mask back before release. The fixture
also checked the purple target was visibly raised after release, the opposite
bottom gesture returned to blue, the private target exposed only a neutral
card before its safe focus restore, and a target that exited during drag was
not substituted with another app.

The adjacent PNGs are selected unedited headless captures of synthetic apps.
Host policy tests separately prove the projected source point follows both
finger coordinates exactly before release, bounded edges and release
thresholds, snapshotted order, keyboard/app-region exclusion, reduced motion,
second-contact cancellation, and disappearing source/target behavior.

This does not prove real-glass reachability, touch ownership against actual
applications or the keyboard, finger alignment, animation smoothness, or
latency. Those physical gates remain **UNVERIFIED**.

## 2026-09-28: vertical-shrink regression, bisection, root cause, and fix

The 2026-09-24 evidence above is source `532115c2`. On 2026-09-28 the
coordinator reopened task 4.8 after rebuilding `.#card-shell` fresh from the
current worktree and rerunning the fixture: it **failed**

```text
AssertionError: ((0, 0, 566, 1230), (16, 0, 552, 1128))
```

at `tests/card_shell_runtime.py:252` (`assert vb[1]>origin[1] and
vb[3]<origin[3]`) -- the live view's top edge stayed at the output's own top
(`vb[1]==0==origin[1]`) instead of moving down as the finger dragged 100px
upward, i.e. the two-axis entry gesture stopped shrinking the view
vertically. Reproduced identically on branch `fix/two-axis-entry-regression`
(base `88ccca15`):

```sh
nix build .#card-shell --max-jobs 1 --cores 6 --no-link --print-out-paths
# /nix/store/j57c5im42d3rq5gxdar2ikmh22717zvc-k230-card-shell
CARD_SHELL_SWAY=/nix/store/0a2f857nc1rz65gnjdfn46h32zsyxm18-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  python3 tests/test_card_shell_two_axis_runtime.py
# AssertionError: ((0, 0, 566, 1230), (16, 0, 552, 1128))
```

**Bisection.** `git bisect` between `532115c2` (2026-09-24 pass) and `HEAD`
does not apply directly: `532115c2` is the tip of `impl/card-two-axis-entry`
and is not an ancestor of `HEAD` (it was rebased/merged in as `b8bfe26c`,
byte-identical to `532115c2` on every file this test touches -- confirmed
with `git diff 532115c2 b8bfe26c -- nix/card-shell/ nix/card-shell-policy/
tests/card_shell_runtime.py tests/test_card_shell_two_axis_runtime.py
tests/card_shell_test_support.py`, zero output). Bisecting `b8bfe26c..HEAD`
with `git bisect run` (a script rebuilding `.#card-shell` and rerunning
`tests/test_card_shell_two_axis_runtime.py` at each step, `CARD_SHELL_CLIENT`
resolved with `nix build --impure --expr ...` rather than `nix eval`, which
only evaluates and does not realize the derivation) converged on a
docs-only commit as "first bad" -- an artifact of a merge-heavy history, not
the true culprit. Only four commits between the run's last confirmed-good
step (`dcc0692b`) and `HEAD` touch `nix/card-shell/` or
`nix/card-shell-policy/`:

```text
1bc355c3 card-shell: Android-recents-sized, rounded overview cards
9cb0fabe Clip live cards to rounded compositor geometry over wallpaper
ef7f7d1e Respect rounded transparency when pausing wallpaper playback
f39cb7eb fix: swipe from Overview to Home and then the app drawer
```

Testing each directly (rebuild + rerun the fixture at each commit) found
`dcc0692b` passes cleanly and `1bc355c3` -- the oldest of the four -- already
reproduces the exact `line 252` assertion; `9cb0fabe`, `ef7f7d1e`, and
`f39cb7eb` reproduce it too (inherited, since none of them touch
`nix/card-shell-policy/`). **Culprit: `1bc355c3` ("card-shell:
Android-recents-sized, rounded overview cards"), the-overview-shows-
large-rounded-cards.**

**Root cause.** `1bc355c3` grew the overview's own card slot from 50%/60% of
the panel to 80%/80% (`cs_default_config`'s `card_width`/`card_height`,
`nix/card-shell-policy/card-shell-policy.c`), per that change's design.md
decision 1. Decision 6 of the same design explicitly keeps
`entry_card_width`/`entry_card_height` (`cs_entry_target_rect`, the direct-
switch entry gesture's own anchor/travel reference) untouched and
independent. Before this change the two were nearly equal by coincidence
(card_height ~739px vs entry_card_height ~740px); after it they diverge by
~224px (card_height ~986px vs entry_card_height ~762px, on this fixture's
568x1232 output).

`cs_entry_visual_rect` renders the entering card by blending its position
and size toward the OVERVIEW's own `cs_card_rect`, then patching `r.y` with
a single fixed linear term (`entry_anchor_shift_y`, computed once in
`cs_entry_set_geometry`) sized to keep one point -- the touch's anchor
fraction down the source rect -- exactly under the finger despite blending
toward a differently-sized/positioned rect than the one anchor/travel were
computed against. That correction's magnitude scales with
`anchor*(entry_card_height-card_height)`: for this bottom-edge gesture the
anchor is close to 1 (the touch lands near the bottom of the panel), so once
`card_height` grew ~224px past `entry_card_height`, the correction became
large enough to push the entering card's computed top edge to a negative
y (off the top of the output) for most of the drag -- correct for the one
point it was solving for, but visually indistinguishable from "the view
isn't shrinking," which is exactly what task 4.8 reopened on. The
mathematics behind this (verified against the actual pre/post-fix pixel
measurements below) is recorded in the commit that fixes it.

**Fix** (`nix/card-shell-policy/card-shell-policy.c`,
`cs_entry_visual_rect`/`cs_entry_set_geometry`; `nix/card-shell-policy/
card-shell-policy.h`): rather than blending unconditionally toward
`cs_card_rect` and patching the anchor with a fixed linear correction,
`r.y`/`r.height` now blend directly between `cs_entry_target_rect` (while
the gesture is actively held, `entry_anchor_factor==1` -- exact against
`entry_travel`/the anchor fraction with no separate correction needed, since
that is what they were established against) and `cs_card_rect` (as
`entry_anchor_factor` decays to 0 during release/settle -- converging on
the true, settled overview slot with no pop when `CS_ENTERING` ends).
`entry_anchor_shift_y` is removed as no longer needed; X is untouched (its
divergence, `entry_card_width` ~437px vs `card_width` ~454px, is small and
was never the reported bug). `tests/card_shell_policy_driver.c`'s
`entry_finger_y` helper (a from-scratch reimplementation used only to
independently assert the anchor-tracking invariant) is updated to mirror
the new formula; the finger-position constants it asserts against are
unchanged, since the invariant it checks (the anchor point tracks the
finger exactly) holds under both formulas by construction -- confirmed by
`tests/test_card_shell_state.py` staying 36/36 across the change.

**Verification, current build.** `nix build .#card-shell --max-jobs 1
--cores 6 --no-link --print-out-paths` ->
`/nix/store/wgzh0z3kxgj41kfgdx5sg1q5syfv0sg1-k230-card-shell`; unwrapped
compositor
`/nix/store/vr72vwrsgcya09qpannsgbv0339p242s-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`.

```sh
CARD_SHELL_SWAY=/nix/store/vr72vwrsgcya09qpannsgbv0339p242s-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  python3 tests/test_card_shell_two_axis_runtime.py
# PASS two-axis app entry: native QEMU pixels, held/reversed quick switch,
# direct release, vertical Home settlement, privacy and exit; no physical touch
# Ran 1 test ... OK
```

Same 100px upward drag, same measurement the failing assertion uses
(`color_box`'s blue mask, `origin`/`vb` from `two-axis-origin.png`/
`two-axis-up.png`):

| build | `origin` (pre-touch) | `vb` (after 100px up-drag) | `vb[1]>origin[1]` | `vb[3]<origin[3]` |
| --- | --- | --- | --- | --- |
| before fix (`regression-before-fix-up.png`) | `(0, 0, 566, 1230)` | `(16, 0, 552, 1128)` | fail (`0>0`) | pass |
| after fix (`regression-after-fix-up.png`) | `(0, 0, 566, 1230)` | `(30, 26, 536, 1128)` | pass (`26>0`) | pass |

`regression-origin.png` is the shared pre-touch frame both rows compare
against (identical before/after, since the bug only manifests once the
finger drags). The before/after pair was captured back-to-back against the
unpatched and patched compositor respectively, same fixture, same 100px
drag, same output size.

**Full card-shell suites re-verified on the fixed build:**

- `python3 tests/test_card_shell_state.py`: 36/36 (host policy driver,
  `-fsanitize=address,undefined`), including the `entry_finger_y`-based
  `two-axis-entry`/`tracked-entry` cases that directly assert the
  anchor-tracking invariant this fix preserves.
- `python3 tests/test_card_shell_two_axis_runtime.py`: PASS (above).
- `python3 tests/test_card_rounded_clip.py`: PASS, 288 rounded-clip pixel
  comparisons (host-side render check for the rounded/corner-mask cards
  this fix must not regress).
- `python3 tests/test_card_shell_video_card.py`: PASS (QEMU).
- `python3 tests/test_card_shell_switch_neighbour_runtime.py`: PASS (QEMU;
  exercises the lateral quick-switch path through the same
  `cs_entry_visual_rect`).
- `python3 tests/test_card_shell_scaled_cache_runtime.py`: PASS (QEMU, both
  cache on/off; exercises the general `CS_ENTERING` carousel path).

`tests/test_card_shell_touch_first_runtime.py` and
`tests/test_card_shell_home_bleed.py` (the latter's `--two-axis
--home-layer-client` case) each failed with a `wait_for(...)`/`restored
focus=` timeout during this session, on both the fixed build and the
unpatched `88ccca15` build (`/nix/store/j57c5im42d3rq5gxdar2ikmh22717zvc-k230-card-shell`,
identical failure) -- pre-existing, reproduced independent of this change.
The shared host ran at `load average: 25-62` throughout this session (`~50`
concurrent worktrees per `python3 tools/work-status.py`); these two QEMU
fixtures' fixed-duration `wait_for`/`time.sleep` assumptions are the most
likely explanation, but that is not independently confirmed here and is
**UNVERIFIED** as a root cause. Left as a pre-existing, out-of-scope flake
for this task; not a regression from this fix.

This still does not prove real-glass reachability, touch ownership against
actual applications or the keyboard, finger alignment, animation
smoothness, or latency. Those physical gates remain **UNVERIFIED**.
