# Host evidence: the virtual device is classified as a touchpad

**Class: host build / host uinput device creation.** Run on the development
host (x86_64-linux), not the K230 board. This proves the ioctl sequence in
`nix/touch-trackpad/src/uinput.rs` produces a device Linux's own udev
classifier calls a touchpad; it does **not** prove libinput/Sway behave
correctly with the real GT9895 driving it, or that gestures work on glass.
That remains board evidence, gated in `tasks.md`.

## Command

```
cd nix/touch-trackpad
K230_TT_SMOKE_SLEEP_SECS=6 cargo test creates_and_destroys -- --nocapture --test-threads=1 &
sleep 3
for p in /sys/class/input/event*; do
  name=$(cat "$p/device/name" 2>/dev/null)
  if [[ "$name" == *"k230-touch-trackpad-test"* ]]; then
    echo "found: $p ($name)"
    udevadm info --query=property --path="$p"
  fi
done
wait
```

(`K230_TT_SMOKE_SLEEP_SECS` was a temporary env-gated sleep added to the
`creates_and_destroys_a_real_virtual_touchpad_if_permitted` test for this one
capture, then reverted -- the committed test creates and immediately
destroys the device, as normal.)

## Result

```
found: /sys/class/input/event24 (k230-touch-trackpad-test)
DEVPATH=/devices/virtual/input/input37/event24
DEVNAME=/dev/input/event24
MAJOR=13
MINOR=88
SUBSYSTEM=input
USEC_INITIALIZED=513569911194
ID_INPUT=1
ID_INPUT_TOUCHPAD=1
ID_SERIAL=noserial
```

`ID_INPUT_TOUCHPAD=1` is udev's own `60-input-id` builtin classifier
(the same mechanism libinput's udev-backed device enumeration in Sway
consults), set from exactly the bits `uinput.rs`'s `VirtualTouchpad::create`
declares: `EV_KEY` capability including `BTN_TOOL_FINGER` +
`INPUT_PROP_POINTER`/`INPUT_PROP_BUTTONPAD`, with `INPUT_PROP_DIRECT` never
set. No `ID_INPUT_TOUCHSCREEN` property appears.

## Also covered by this same host run

`cargo test` (20/20 passing, see `nix/touch-trackpad/src/*.rs` `#[cfg(test)]`
modules):
- `relay.rs`: the protocol-translation state machine against synthetic
  1/2/3-finger event sequences (tap, drag, lift, 2-to-1-finger transition).
- `mode.rs`: DRM-sysfs-fixture-driven mode detection (panel-only, HDMI
  connected, HDMI present-but-unplugged, missing/absent DRM root).
- `devsearch.rs`: `/proc/bus/input/devices` stanza parsing against a
  fixture containing the real recorded device name
  ("Goodix Berlin Capacitive TouchScreen", from
  `docs/evidence/touch-evtest.txt`).
- `uinput.rs`: every `UI_*`/`EVIOCGRAB`/`EVIOCGABS` ioctl number
  independently hand-computed and checked against the kernel's own
  `linux/uinput.h`/`linux/input.h` macro expansions, plus the two on-wire
  struct sizes (`uinput_setup` = 92 bytes, `uinput_abs_setup` = 28 bytes).

`cargo clippy --all-targets`: clean (0 warnings) after fixing one
`collapsible_if` lint.
