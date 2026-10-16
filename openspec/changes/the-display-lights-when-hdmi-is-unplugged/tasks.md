## 1. Unplug lights the display

- [x] 1.1 Touch relay: on the Trackpad → DirectTouch transition, send
  `output * power on` before the direct-touch mapping, once, retrying with
  the mapping if Sway is not ready. Verify with
  `cargo test --offline --manifest-path nix/touch-trackpad/Cargo.toml`.
  Done 2026-10-16 (host): 49 + 2 tests passed.
- [x] 1.2 Power-key daemon: read `get_outputs` before each action, and keep
  the cached state when Sway is unreadable or reports no active output.
  Verify with `python3 -m unittest tests.test_power_keyd`.
  Done 2026-10-16 (host): 13 tests OK.
- [ ] 1.3 On the board, with HDMI connected, darken the display with a short
  power-key press, unplug HDMI, and observe the panel lit with direct touch.
  Then confirm one short press darkens it. Record the journal lines
  (`power off`, HPD disconnect, `power on`) and a native capture. This needs
  the operator to unplug the cable; the key press may be the operator's or
  an injected `KEY_POWER`.
