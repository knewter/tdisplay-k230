# Gesture rollback on the board

On 2026-09-23T06:17Z the source-built launcher from `e297d6e` was run
with `K230_LAUNCHER_GESTURES=0` on the physical board. Installed system:
`/nix/store/568vf3220mpvdmgjgfnz5ln0qn09934r-nixos-system-nixos-26.11.20260919.20b1ddd`.
Launcher wrapper: `/nix/store/fajixpwc8gvsz1h4pf4c4hksyjqzjasg-k230-touch-launcher`.
This predates the final-image regression and is explicitly injected input.

The [result](result.json) records that the disabled-gesture drag left the
Apps canvas unchanged, Next changed page, Previous restored the original
canvas, and Back closed the launcher. The process environment was checked
before the interaction. The exact helper is
[`../metadata-budget/check.py`](../metadata-budget/check.py), phase `rollback`.

The initial test incorrectly dragged from (430,320) to (130,320), staying
inside the Terminal card. With gestures disabled this retains legacy tap
behavior and opens Terminal. That run was rejected. The corrected test ends
at (15,320), outside the card: legacy tap tracking cancels activation, while
the enabled gesture recognizer would classify the same motion as paging.
The accepted run used this corrected trajectory; this was a test correction,
not a production-code change.

This result alone does not close forced-render-failure recovery, final-image
acceptance, physical-finger accuracy or focused-camera proof.
