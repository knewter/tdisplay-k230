## 1. Unplug lights the display

- [x] 1.1 Touch relay: when the HDMI connector's status changes from
  `connected` to not connected (a real unplug, not a power-key blank that only
  disables scanout), send `output * power on` before the direct-touch
  mapping, once, retrying with the mapping if Sway is not ready. Verify with
  `cargo test --offline --manifest-path nix/touch-trackpad/Cargo.toml`.
  Done 2026-10-16 (host): 50 + 2 tests passed, including
  `only_a_real_unplug_counts_not_a_blanked_monitor`.
- [x] 1.2 Power-key daemon: read `get_outputs` before each action, and keep
  the cached state when Sway is unreadable or reports no active output.
  Verify with `python3 -m unittest tests.test_power_keyd`.
  Done 2026-10-16 (host): 13 tests OK.
- [x] 1.4 On the board with HDMI connected, a short power-key press keeps the
  monitor dark (no wake while the cable stays in). Then unplugging lights the
  panel. Record the journal lines.
- [x] 1.3 On the board, with HDMI connected, darken the display with a short
  power-key press, unplug HDMI, and observe the panel lit with direct touch.
  Then confirm one short press darkens it. Record the journal lines
  (`power off`, HPD disconnect, `power on`) and a native capture. This needs
  the operator to unplug the cable; the key press may be the operator's or
  an injected `KEY_POWER`.

Tasks 1.3 and 1.4 done 2026-10-16 (board, operator cable and key, journal):
`docs/evidence/power-key/hdmi-unplug-wake/board-2026-10-16.md`.
