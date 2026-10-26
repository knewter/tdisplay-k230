## Why

Sliding the keyboard down exposes an opaque card-coloured strip under the
app. On every frame the app's reserved space grows with the keyboard, but
the app (Foot, for example) redraws at the new height a frame or more later.
Since 2026-09-24 a compositor backdrop has filled that gap
(`ordinary_backdrop_sync` in `nix/card-shell/adapter.c`). On 2026-10-25 the
operator reported the strip and chose to have the app grow first.

## What Changes

- As soon as the keyboard starts moving down (a grip drag, or a release
  settling toward hidden), the app is given its full height in one step,
  behind the keyboard. The sliding keyboard then uncovers app content the app
  has already drawn.
- While the keyboard moves up, reserved space keeps following it as today.
  The app shrinks under a keyboard that already covers its bottom edge, so no
  gap appears.
- A resize reported during a keyboard drag is committed on the next frame.
  Before, `ordinary_sync_usable` recorded the new usable area without
  committing it and then skipped the commit on every later frame, so the app
  kept its old size until an unrelated event. This was found on the board
  (`docs/evidence/interaction-jank/keyboard-hide`).
- The policy for this, `kg_reserved`, lives in
  `nix/card-keyboard-policy/keyboard-gesture.c`. The adapter uses it for the
  usable area; the keyboard and grip still follow progress exactly.
- Non-goals:
  - changing keyboard motion, settling or ownership;
  - removing the backdrop, which still covers the one or two frames before
    the app's first full-height commit;
  - opaque regions on sliding surfaces.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `runtime/shell`: "Keyboard motion follows contact and settles
  continuously". The reserved app space now leads a hiding keyboard instead
  of tracking it.

## Impact

`nix/card-keyboard-policy/keyboard-gesture.{c,h}`, `nix/card-shell/adapter.c`
and `tests/keyboard_gesture_driver.c`. Board proof is native captures of a
slow and a held hide, then the operator's look on real glass.
