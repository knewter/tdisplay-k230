# Every edge gesture stopped until the shell restarted

## Report

The operator, 2026-10-29 00:34:26 CDT, on build `37g1magg…`, wrote: "all of
the sudden gestures stopped working though i can't open the app drawer at all
now". The last edge gesture in the shell journal was a side Back at 00:33:22.

## What was observed (board, injected touch, grim)

These were tested between 00:36 and 00:44 with `ui.py`'s uinput touchscreen
on the stuck session:

- Swipes up from the bottom and down from the top did nothing. They left no
  card-shell journal line, on Omawrite, on Timer and on Home with every app
  closed.
- Taps still reached apps: a tap on Omawrite's Open icon opened its file
  dialog.
- None of these cleared it:
  - a single tap;
  - a two-finger touch;
  - closing Omawrite and Timer;
  - killing wvkbd.
- The kernel showed no held contact: `EVIOCGMTSLOTS` on the Goodix device
  read every `ABS_MT_TRACKING_ID` as -1, with `BTN_TOUCH` 0.
- `card_shell debug-scene` showed `drawer_mapped=0` and `mode=0`, with no
  overlay or keyboard.
- Restarting the `shell` service restored the gestures. After the restart,
  grim captured the Overview from a bottom swipe and the shade from a top
  swipe.

## Cause

Taps still working means the touch-down gate fell through without consuming
anything. Every edge gesture in `input_down` (`nix/card-shell/adapter.c`)
starts only when `wlr_seat_touch_num_points() == 0`, no popup is mapped, and
Sway is not emulating a pointer from touch.

The observations rule out most of these:

- **Pointer emulation:** the tap on Omawrite was delivered, which clears or
  precludes the emulation flag.
- **An app's popup:** gestures stayed dead with every app closed.
- **The keyboard's popup:** gestures stayed dead with wvkbd killed.

That leaves a seat touch point that was never released. Two facts make such
a point permanent:

1. Card-shell forwards an undecided edge touch straight to wlroots
   (`edge_client_begin`), bypassing Sway's seatop.
2. Sway's default seatop has no `touch_up` handler. Only card-shell's own
   `edge_client_up` or `edge_cancel_client` can ever release that point.

The edge path in `input_up` ran `edge_reset(false)` when its contact count
reached zero, even if a forwarded point had not been released. A count can
reach zero on a lift that is not the forwarded contact's. The keyboard chord
(`kg_down`) runs before the edge's own second-contact handling, so it can take
a second finger without the edge counting it. When that finger lifts first,
the edge resets and the first finger's point leaks.

This is inferred from the code and fits every observation. The exact sequence
was not captured: the route trace (`SWAY_K230_TOUCH_ROUTE_TRACE`) was not
enabled in that session.

## Fix

The fix is in `nix/card-shell/adapter.c`:

- `input_up` resets a finished edge with `edge_reset(true)`. This cancels a
  still-forwarded client point. `edge_client_up` clears `edge.forwarded` once
  it has delivered the up, so a normal edge gesture is unaffected.
- `release_stale_touch_point` is a backstop. A down whose id the seat already
  holds proves that point lost its up, because a held contact id is unique.
  The point is released through the current seatop, or with
  `wlr_seat_touch_notify_up` under the default seatop, and the event is
  logged as `K230_CARD_SHELL stale-touch-point`. Any future leak therefore
  costs at most one touch, not the session.
- `card_shell debug-scene` now reports the gate's inputs: `touch_points`,
  `pointer_from_touch`, `popup_mapped`, `launcher_mapped`, `blocked_until_up`,
  `contact`, `edge_tracking`, `edge_active` and `edge_forwarded`. A refused
  gesture can be attributed over IPC without restarting.

## Verification

This was done on the board with injected touch, build `7w2fpx1f…`, test-activated
2026-10-29 00:50 CDT:

- A top swipe opened the shade (grim).
- A two-finger swipe up from the bottom raised the on-screen keyboard (grim).
- `debug-scene` read `touch_points=0 pointer_from_touch=0 popup_mapped=0 ...
  edge_active=0 edge_forwarded=0` before and after.

Limits:

- The original leaking sequence was not reproduced, so this does not prove
  the leak cannot recur.
- The `stale-touch-point` log line is what would show a recurrence.
- Glass use by the operator is the remaining evidence.
