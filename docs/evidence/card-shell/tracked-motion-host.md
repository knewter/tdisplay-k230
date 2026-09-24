# Finger-tracked live-card motion: host source checkpoint

Source branch: `impl/live-card-integrated`, based on `cc32f26a240e108c5e8821223ca8e754d00d8ff0`.
Source commits: `e11af6f7` (entry), `f7a510c6` (expansion), `90b19e42` and
`5113c3c2` (route/command guards), `760e7de2` (release and fallback corrections).
Date: 2026-09-24 UTC. This is source and native-host proof only.

With `SWAY_K230_CARD_TOUCH_FIRST=1`, a live selected view is mirrored by the
compositor scene while bottom-edge motion moves it from its actual view
geometry toward its card slot. The mirror is a live scene surface, not a saved
screenshot. Reversing the finger changes that same geometry. Releasing below
the full travel reverses the partial motion over a bounded timer interval and
restores the app. If the selected source is private, unavailable, or absent,
the bottom contact is reserved but the app remains visible until the upward
threshold qualifies; a stationary bottom tap does not enter the deck. The
truthful placeholder is then shown without synthesizing app pixels.

A live card tap expands its visible card geometry toward its source-view
geometry. Focus transfer waits until a full-geometry **policy dwell**. The dwell
is one timer state, **not proof that an output frame was presented**. A new
contact, shade/drawer route, touch cancel, or source loss reverses or aborts
according to the policy; focus and privacy still require compositor runtime
verification. The rollback route remains available with the touch-first flag
off. No measured performance improvement is claimed.

Host commands run in this source worktree:

```text
python3 tests/test_card_shell_state.py
  PASS: 25 native policy cases under the test harness, including tracked entry,
  partial reversal, stationary private/absent-source taps, expansion interruption,
  and cancel consumption.
python3 tests/test_card_shell_chrome.py
  PASS: 1 native chrome case.
python3 tests/test_card_shell_route.py
  PASS: 1 native fixed-argv route case.
git diff --check
  PASS.
```

Remaining gates: cross-build the exact source revision with `nix build
.#card-shell --max-jobs 1 --cores 4 --no-link --print-out-paths`, run the actual
cross-built Sway and live nested-surface client in headless QEMU with
`CARD_SHELL_SWAY=<built-sway>/bin/sway CARD_SHELL_CLIENT=<built-client>/bin/card-composition-probe-client python3 tests/test_card_shell_touch_first_runtime.py`, and inspect captured start/middle/end and expansion pixels plus focus, cancel, source-unmap, and privacy behavior. Then a separately reserved board/camera run must establish real-finger tracking, visible presentation, CPU/frame budgets, and optical acceptance. Host policy ticks, QEMU screenshots, and physical panel presentation are distinct evidence classes; none of the latter three is claimed here.
