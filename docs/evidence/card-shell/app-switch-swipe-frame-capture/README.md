# App-switch swipe: per-frame QEMU capture

Coordinator's report: a webcam recording of an injected bottom-edge
horizontal swipe on the physical board (installed system `061a1zbh…`, master
`64c38998`, two apps open) showed a dark band flickering along the panel's
top edge as the switch starts, and more frame-to-frame changes later in the
swipe. The camera angle was steep ("only indicative"), so this reproduces
the same gesture under headless QEMU with per-step compositor capture to
tell a real rendering defect from a camera artifact.

## Reproduction

`tools/repro-app-switch-swipe.py --sway <unwrapped riscv64 sway> --client
<card-composition-probe-client> --output /tmp/k230-bc-N`: two apps marked
`card_shell ordinary, floating enable, resize set 100 ppt 100 ppt, move
position 0 0` (the board's own for_window config), a real `wlr_touch`
device via `card_shell test-touch` (`SWAY_K230_CARD_TEST_INPUT=1`), and a
single-stepped bottom-edge horizontal swipe from (420,1226) to (120,1226) --
the coordinator's exact coordinates -- capturing one `grim` frame after
every injected `down`/`motion`/`up` plus six settle frames. This is
headless-QEMU-injected-input evidence, not board/panel proof.

Card-shell's touch-first two-axis entry (`cs_begin_entry`/`cs_entry_motion`)
is what a horizontal-only swipe at a constant bottom-edge `y` actually
drives -- the non-touch-first classic edge recognizer
(`cs_edge_down`/`cs_edge_motion` in `nix/card-shell-policy/card-shell-
policy.c`) only reacts to upward vertical motion, so this reproduction
necessarily runs with `SWAY_K230_CARD_TOUCH_FIRST=1`.

## Finding 1 (fixed): a real 1:1-tracking regression from this change's own plate-pad work

`tests/test_card_shell_two_axis_runtime.py` failed once while iterating on
the bare-app-cards fix: a tracked content edge moved 110px for a 100px drag
(tolerance 7). `CARD_PLATE_PAD` was being subtracted from the card's fit
bounds unconditionally, including during the entering/expanding transition,
so the mirrored content started life a few px smaller than the real window
it was shrinking from -- breaking the direct 1:1 finger-tracked scene the
two-axis gesture depends on. Fixed by interpolating the pad by
`entry_progress`/`expand_progress` (0 at the source-geometry end, full pad
only once settled) -- see the `fix/bare-app-cards` commit "Fix a
1:1-tracking regression: interpolate the plate pad by entry/expand
progress". The two-axis suite passes again (18/18 checkpoint frames). This
was a genuine regression from this change; it is not what the coordinator's
camera saw on `64c38998` (this repro's own binaries are already built from
the fixed adapter.c), but it is exactly the class of defect the coordinator
asked to rule out, so it is recorded here too.

## Finding 2 (reproduced, not fixed here): one "ordinary" floating window's percentage resize can stick at its pre-resize size

This is the more likely explanation for the reported dark-band/frame-to-
frame glitch, and it is **not** in `nix/card-shell/adapter.c`'s card
geometry/plate/label code (this change's scope) or in `card-shell-
policy.c`'s gesture math.

`frame-000` through `frame-025` (and a second run's `frame-015-…-run2.png`)
show a persistent, reproducible asymmetry: one of the two "100 ppt" floating
windows never reaches the output's full 568x1232 -- it stays at the synthetic
client's pre-configure default (480x720) -- while the other does. A direct
`get_tree` dump (not committed; reproducible with the tool above) confirms
the stuck window's `rect` staying `{480,720}` for 6+ seconds after mapping,
with no further resize. Which of the two windows gets stuck is not fixed
across runs (observed both ways), consistent with a race rather than an
ordering rule.

Effect on the capture: `frame-002` (x=420, right after touch-down) still
shows a full-bleed source app with no bands. By `frame-009` (x=280) the
stuck-small neighbour is visible on the right with dark top/bottom margins
around it while the still-full-height dragged app occupies the left --
`frame-015` (x=160) and `frame-018` (x=120) show the same margins, now
covering most of the visible width. `frame-019` (`up`) and `frame-025`
(settled) show the mismatch persisting after the switch completes: the
newly-focused app (meant to be full-screen again) renders at its stuck
smaller size, leaving the other app's real content visible in the
remaining screen area as a horizontal split. None of this is a
compositor-added plate, backdrop flash, or chrome bleed-through -- both
windows' own live pixels are correct throughout, just wrongly sized for one
of them.

This matches the coordinator's suspect list under "a stale or wrong-size
buffer from a client resize (maximized apps being resized to card size and
back)". `card_shell ordinary` (the mark applied here) only sets a boolean
(`nix/card-shell/adapter.c` ~line 2276) and touches no geometry, so the race
is most plausibly in generic Sway/wlroots floating-resize-to-percentage
handling for a window still mid-configure when a second floating window's
own resize/output-geometry read happens -- independent of anything in
card-shell's own scene code. It has not been root-caused or fixed here:
that needs its own investigation (start with `container_floating_resize`'s
percentage math and the configure/ack/commit ordering for two floating
windows resized back-to-back by the same `for_window` rule at startup),
and ideally a real-board check for whether the same race is reachable
there (real client configure round-trips are slower than these synthetic
clients', which could make it easier, not harder, to hit).

## Everything else observed

Across all 26 frames of both runs: no wallpaper/backdrop flash, no frame
showing deck/card-overview chrome during an ordinary-app switch, no focus
flicker (`final focus: k230.card.two` matches the swipe direction both
times), and no jump at release beyond the pre-existing size mismatch above.
