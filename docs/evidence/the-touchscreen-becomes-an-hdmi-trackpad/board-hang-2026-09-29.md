# Board evidence: the first board run hung and needed a hardware reset

**Class: board observation, reported by the coordinator** (operator has
sole board/serial access on this change; this crate had none). Recorded
here verbatim from their report so the fix below is traceable to a real
board symptom, not a hypothesis.

## What was run

```
/nix/store/sklwlg9n...-k230-touch-trackpad/bin/k230-touch-trackpad
```
as root, no flags, during an HDMI one-shot boot (2026-09-29, ~20:57).

## What happened

```
mode -> Trackpad (panel connected: false)
entered trackpad mode, grabbed /dev/input/event0 (x 0..1023 y 0..2399)
```
Kernel: `input: K230 Virtual Touchpad (HDMI mode) as /devices/virtual/input/input2`

Sway/libinput:
```
[ERROR] [libinput] event2 - K230 Virtual Touchpad (HDMI mode): kernel bug: device has min == max on ABS_MT_PRESSURE
```

No cursor appeared. Within seconds the whole board hung: the serial
console echoed typed commands but never ran them, the journal ends at that
point, and recovery needed a hardware reset (not a clean reboot).

Independently, the coordinator confirmed the underlying touchscreen itself
is fine: running `libinput debug-events` against `/dev/input/event0`
*before* this program's grab showed 66 `TOUCH_DOWN` and ~1000
`TOUCH_MOTION` events over 20 seconds of normal use.

## Invalid pressure axis identified (confirmed by host reproduction)

The real GT9895's `EVIOCGABS(ABS_MT_PRESSURE)` reports a **degenerate
range** (`minimum == maximum`, specifically `0 == 0`) -- this driver
apparently does not implement real pressure reporting and just zero-fills
the capability rather than omitting it. `nix/touch-trackpad/src/touchdev.rs`'s
`read_ranges()` mirrored that `input_absinfo` onto the virtual device
completely unvalidated (and its own failure-path fallback,
`InputAbsInfo::default()`, was *equally* degenerate -- `min=0,max=0` --
so even an `EVIOCGABS` ioctl failure for that one axis would have produced
the same bug). libinput's `evdev_configure_device()` flags exactly this
shape (`min == max` on a reported axis) as a "kernel bug" workaround case,
logs the error shown above, and does not add the axis -- this by itself is
not fatal to libinput and is not, on its own, sufficient to explain a full
board hang requiring a hardware reset.

**Reproduced on the host** (not the board, but the same ioctl sequence
against a real Linux kernel): before the fix,
`nix/touch-trackpad/src/uinput.rs`'s `VirtualTouchpad::create` would
mirror a `min=0,max=0` `ABS_MT_PRESSURE` range onto `/dev/uinput`
unchanged, exactly reproducing the shape libinput flagged.

## What was not established

Board access was not available to this change to isolate *which specific
mechanism* turned the libinput warning (non-fatal by itself) into a full
system hang requiring a hardware reset. The fix below (see `design.md`
decision 5) does not claim to have proven the exact mechanism; it instead:

1. Eliminates the confirmed-real bug (the degenerate pressure axis) at its
   source, so the exact reported symptom cannot recur.
2. Adds defensive bounds against every plausible busy-loop mechanism named
   by the coordinator's fix request (a `poll(2)` `revents` bug that could
   make `wait_readable` return "ready" instantly forever; an unbounded
   event-drain loop; no signal handling to interrupt a stuck run), each
   independently host-tested, without asserting any one of them is *the*
   cause.

Whether this fully resolves the hang can only be established by re-running
on the board -- `tasks.md` group 3 names the safe re-test procedure
(`--dry-run --log-events` first, `timeout`-wrapped) and keeps the
`<!-- UNVERIFIED -->` marker in `specs/display/touch/spec.md` until that
happens.

## Host re-verification after the fix

`cargo test` in `nix/touch-trackpad/` (28/28 passing) includes, added in
response to this report:
- `uinput::tests::axis_plan_omits_degenerate_pressure_matching_the_observed_board_bug`:
  the exact `min=0,max=0` `ABS_MT_PRESSURE` fixture is now omitted from the
  device's axis plan entirely rather than reaching `/dev/uinput`.
- `uinput::tests::axis_plan_rejects_a_degenerate_load_bearing_axis`: a
  degenerate `ABS_MT_POSITION_X`/`_Y`/`_SLOT`/`_TRACKING_ID` range (unlike
  pressure, load-bearing) now refuses device creation outright
  (`io::ErrorKind::InvalidData`) instead of creating a device libinput
  cannot use.
- `uinput::tests::creates_a_real_virtual_touchpad_with_the_boards_exact_degenerate_pressure_range`:
  a **live** `/dev/uinput` device creation using the board's exact
  degenerate-pressure fixture, re-checked with the same `udevadm`
  technique as `host-uinput-classification.md`:

  ```
  found: /sys/class/input/event24 (k230-touch-trackpad-test-degenerate-pressure)
  ID_INPUT=1
  ID_INPUT_TOUCHPAD=1
  ```

  confirming the sanitized device (pressure axis omitted) is still
  classified as a touchpad, and no longer declares the axis libinput
  flagged.
- `touchdev::tests::wait_readable_blocks_for_the_timeout_then_returns_promptly_once_data_arrives`:
  proves `wait_readable` (the mechanism the whole poll loop depends on to
  avoid busy-spinning) genuinely blocks for its timeout on an idle fd and
  returns promptly once data is written, using a FIFO (a real
  `/dev/input/event*` node is `root:input` with no seat ACL in this
  sandbox, unlike `/dev/uinput`, so a FIFO exercises the same
  `poll(2)`-on-a-waitable-fd code path instead).
