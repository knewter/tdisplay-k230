## Context

`card_shell_keyboard_adjust_usable` runs on every arrange. It moves the
keyboard's layer node by `progress` and grows the usable area by the
keyboard space that `progress` releases. The client resize behind that
usable area takes a Wayland configure/commit round trip. Until the app
commits, the margin between its old bottom edge and the keyboard top shows
`ordinary_backdrop`.

## Goals / Non-Goals

- **Goal:** a hiding keyboard reveals app pixels, not a fill.
- **Non-goal:** hiding the round trip by stretching or scaling client
  content.

## Decisions

- **Direction, not mode.** `kg_reserved` remembers the last progress it saw.
  When progress falls it returns 0. When progress rises it returns the
  progress, and an unchanged progress keeps the previous answer. This covers
  grip drags, settles and hold-and-reverse alike, with no per-mode cases.
- **Show is unchanged.** When a shrinking app lags, its old pixels sit under
  the keyboard and nothing is exposed.
- **Commit the carried resize.** `arrange_layers` calls
  `ordinary_sync_usable` with `commit` false. The call records the usable
  area, so the next frame's call (with `commit` true) found nothing changed
  and returned. `ordinary_resize_pending` now carries the uncommitted resize
  to that next call. On the board, growing first without this left the app
  at its old size for the whole drag (84–130 light rows above the grip); with
  it, none.
- **The backdrop stays.** The app still needs one round trip after the first
  downward step. During it the keyboard has moved only a few pixels, and the
  backdrop is better than wallpaper there.

## Risks / Trade-offs

- A small downward wobble during an upward drag grows the app to full height,
  and the next upward step shrinks it again. Each step is one resize behind
  the keyboard, so no gap is exposed. The app's content may still jump.
- With hold-and-reverse, the app stays at full height until the keyboard
  moves up again.
- Show now commits a resize on every frame, which it did not before. On the
  board, presented-interval medians were unchanged; hide-contact render rose
  from 6.2 to 6.9 ms and hold-and-reverse render p95 to about 12 ms.
