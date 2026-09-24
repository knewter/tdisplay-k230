# Fixing the bottom-edge app-switch swipe (real-finger report)

Real-finger board report: swiping left/right along the bottom to switch apps
needed far more travel than it looked like, momentum was ignored, and an
80%+ swipe still snapped back to the current app. This is a follow-up fix to
the same-day two-axis entry work in `the-handheld-presents-a-coherent-shell`
(design.md decision 11); see decision 12 there for the amended design record.

## Root causes, confirmed against the existing test suite

Both are in `nix/card-shell-policy/card-shell-policy.c`, function
`cs_entry_up_at` (the release decision for the bottom-edge entry/app-switch
gesture used from `nix/card-shell/adapter.c`).

**1. A "central quick-switch band" gate, keyed on touch-DOWN x position.**
`cs_begin_entry` recorded `entry_quick_allowed = x>=width*.25 && x<width*.75`
at the moment of touch-down, and the release decision was
`if (lateral && (vertical || entry_quick_allowed)) target=...`. A pure
horizontal swipe starting outside the central 50% of the screen width
additionally required the *same contact* to also travel `entry_distance`
(72px) upward -- something a deliberately horizontal swipe does not produce.
So a swipe starting near either side of the bottom edge reversed regardless
of how far it travelled sideways. This was already reproducible in the
existing host test suite before this fix: `tests/card_shell_policy_driver.c`
`two_axis_entry`'s "Side start is not the central quick-switch region" case
(x=80, dx=130, i.e. 23% of the 568px panel width) asserted `entry_reversing`
as the *expected* behaviour. That test now asserts the opposite (a switch),
and was verified failing against the pre-fix source (see below).

**2. Release velocity was a single last-interval delta, valid for only 80ms
after the *last recorded sample*.** `cs_entry_motion` updated
`entry_velocity_x`/`entry_velocity_progress` from only the immediately
preceding sample (`dt>=4` gate, no history), and `cs_entry_up_at` zeroed it
unless `time_ms - entry_sample_ms <= 80`. Real touch reports arrive roughly
every 8ms while the finger is moving continuously
(`docs/evidence/touch-reports.md`, `docs/evidence/touch-evtest.txt`: SYN_REPORT
intervals of ~8.1ms during a drag, e.g. `236.696828 -> 236.704991 -> ...`),
but the *last* sample before a release can legitimately be older than 80ms
relative to the release timestamp -- a naturally decelerating final sample,
a slightly delayed release dispatch, or a sparser cadence under load all
zero the momentum this way, discarding a flick the finger clearly made.

## Fix

`nix/card-shell-policy/card-shell-policy.c` / `.h`:

- Removed `entry_quick_allowed` and the `vertical`-or-band gate. A horizontal
  bottom-edge swipe now switches on distance or flick velocity alone,
  regardless of where along the qualified bottom edge band it started, and
  regardless of any upward component (up-then-sideways still works
  identically, since a strong vertical component does not defeat the lateral
  check).
- New config fields `entry_select_fraction` (default `.3`) and
  `entry_flick_speed` (default `.4` px/ms), replacing the old
  `pitch*select_fraction` distance test (`select_fraction` is still used,
  unchanged, for the separate in-deck horizontal card-browse drag).
  `entry_select_fraction` is a fraction of the **screen width**
  (568 * .3 = 170.4px on this panel), not of the card pitch: the old
  `pitch*select_fraction` (452.8 * .25 = 113.2px, ~20% of the screen) mixed a
  UI layout quantity (card width + gap) into what should be a finger-travel
  threshold. 30% sits in the middle of a deliberate-page-turn range (25-35%
  is Android/iOS-like; ViewPager-style pagers commonly page past half their
  own width, and a third of the *full* screen is comfortably reachable in one
  thumb stroke on a 568px-wide panel without being mistaken for a scroll).
  0.4 px/ms sits in the middle of a 0.3-0.5 px/ms flick range: half the new
  distance threshold (85.2px) covered in about 213ms reaches exactly that
  speed, matching what a normal, unhurried "flick" (not a slow drag, not a
  deliberate full-distance drag) looks like at the measured ~8ms report
  cadence.
- Release velocity (`entry_release_velocity` in the .c file) is now a
  recency-biased estimate over a small ring buffer of recent samples
  (`entry_history`, capacity 8): it walks backward from the newest sample
  only as far as needed to reach a minimum usable span (`CS_ENTRY_MIN_SPAN_MS`
  = 6ms -- since real samples are ~8ms apart, this normally resolves to just
  the last interval, preserving instant reversal sensitivity), capped at
  `CS_ENTRY_WINDOW_MS` = 120ms (wide enough to bridge a sparse ~100ms event
  cadence). The sample is accepted as long as it is no more than
  `CS_ENTRY_FRESHNESS_MS` = 160ms old relative to the release timestamp
  (up from the old fixed 80ms), which is why a naturally-stale last sample or
  a delayed release no longer zeroes momentum.
- The half-distance-plus-flick-speed hybrid, and the projected-endpoint
  same-side check that cancels on reversal, are otherwise unchanged in
  structure from the pre-existing (already reviewed and tested) design --
  only their inputs were corrected.

`tests/card_shell_policy_driver.c` / `tests/test_card_shell_state.py`:

- Added `app-switch-swipe`, replaying: an 80% slow horizontal swipe (distance
  alone, low measured velocity, from a side start); a 30% fast flick (half
  distance + flick velocity); a sparse ~100ms event cadence; a flick whose
  last recorded sample is 100ms stale relative to the release event; an
  up-then-sideways swipe; a reversal flick that still cancels; and a pure
  vertical swipe that still opens the overview.
- Updated the existing `two_axis_entry` "side start" case (see root cause 1)
  and recalibrated three `two_axis_conflicts`/`direct_carousel` cases whose
  magic numbers had been tuned to just clear the *old*, smaller distance
  threshold (~113px) or to exercise reversal-by-sign-flip with margin under
  the *new* half-distance floor (~85px); see inline comments at each site for
  why each number changed.

## Confirming the bug and the fix (host, `tests/test_card_shell_state.py`)

Fresh worktree checkout, plain `cc` with the exact flags
`tests/test_card_shell_state.py` uses (`-std=c11 -Wall -Wextra -Werror
-pedantic -g -fsanitize=address,undefined`):

```sh
cc -std=c11 -Wall -Wextra -Werror -pedantic -g -fsanitize=address,undefined \
  -fno-omit-frame-pointer -I /tmp/k230-as-baseline \
  tests/card_shell_policy_driver.c /tmp/k230-as-baseline/card-shell-policy.c \
  -lm -o /tmp/k230-as-policy-baseline   # /tmp/k230-as-baseline = origin/master's .c/.h
ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 /tmp/k230-as-policy-baseline app-switch-swipe
# Assertion `up_result.consumed && p.entry_settling && p.entry_target_id==101' failed. (FAILS pre-fix)
ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 /tmp/k230-as-policy-baseline two-axis-entry
# Assertion `... p.entry_settling && p.entry_target_id==101' failed. (FAILS pre-fix, root cause 1)
```

A standalone reproduction of root cause 2 alone (fast drag, then a release
100ms after the last motion sample): pre-fix source returns
`target=0, reversing=1`; this fix returns `target=101, settling=1`, same
`raw_dx=120` in both.

Post-fix, full suite:

```sh
python3 tests/test_card_shell_state.py -v
# Ran 29 tests in 2.024s -- OK (includes the new app-switch-swipe case)
```

## QEMU proof (real cross-built Sway/wlroots, injected touch; not physical)

```sh
nix build --no-link --print-out-paths --max-jobs 1 --cores 6 .#card-shell
# /nix/store/rlq5hkf01gd8hcfmfidzqqp2jg215c9v-k230-card-shell (riscv64, fresh
# rebuild of sway-unwrapped/sway/card-shell/k230-card-shell -- 5 derivations)
nix build --no-link --print-out-paths --max-jobs 1 --cores 6 --impure --expr \
  'let f=builtins.getFlake (toString ./.); p=import f.inputs.nixpkgs {system=builtins.currentSystem;}; \
   in p.callPackage (f.outPath + "/nix/card-composition-probe-client") {}'
# /nix/store/r0i7x90xbk8hnnz081ffkrzgqqbkmiwl-card-composition-probe-client-0.1

CARD_SHELL_SWAY=/nix/store/66dk7fsb3kgfw6mg4xqk2m7h4qhsgq7z-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
CARD_SHELL_CLIENT=/nix/store/r0i7x90xbk8hnnz081ffkrzgqqbkmiwl-card-composition-probe-client-0.1/bin/card-composition-probe-client \
python3 tests/test_card_shell_two_axis_runtime.py -v   # PASS (same-contact scene, quick switch, vertical Home, privacy, exit)
python3 tests/test_card_shell_gestures.py              # PASS (17 checks, unchanged)
python3 tests/test_card_shell_recovery.py              # PASS (unchanged)
python3 tests/test_card_shell_touch_first_runtime.py   # PASS (unchanged)
python3 tests/test_card_touch_clock.py -v              # PASS (unchanged)
python3 tests/test_card_touch_routing.py --sway <unwrapped sway>  # PASS, 7 checks (unchanged)
```

`evidence_class` on every runtime result remains
`headless-qemu-injected-input` / `native-wayland-receiver-headless-injected-device`.
This exercises the real compositor, real wlroots touch routing and the real
scene under QEMU user-mode emulation; it is not the panel, not the GT9895
touch controller, and not a real finger.

`python3 tools/blob-scan.py` exit status: `0` ("every binary is accounted
for").

## What remains open

This change has no board/panel/touch-controller evidence and makes no such
claim. Everything above is host-ASan proof and QEMU-injected-touch proof.

**Real-glass check for the user (operator command):** on the board, from a
running app, place a finger anywhere along the bottom ~48px edge band
(not just the screen's central half) and swipe left or right. It should
switch to the adjacent app either when the swipe covers roughly 30% of the
panel's 568px width (~170px), or on a shorter, decisive flick, with the app
tracking the finger 1:1 while held and coasting into place (no snap, no
dead stop) on release; a flick back toward the start should still cancel.
Starting with an upward component and curving sideways in the same touch
should behave identically. A pure vertical swipe should still reach the
card overview. Capture with the existing card-shell board harness, e.g.:

```sh
python3 tools/capture-feature.py coherent-two-axis --provenance real-touch \
  --duration 60 --description 'Bottom-edge app-switch swipe after the \
  distance/velocity fix' --output-dir docs/evidence/coherent-two-axis
```

(board task 5.7 in `the-handheld-presents-a-coherent-shell/tasks.md`, still
open).
