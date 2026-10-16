## 1. Implementation

- [x] 1.1 Reconnect once and resend a `card_shell trackpad begin` that fails
      with an I/O error (`shell_ipc::run`). Host test
      `a_compositor_restart_does_not_lose_the_next_gesture`: it fails without
      the retry and passes with it.
- [x] 1.2 Hold a still multi-finger candidate until it moves, pinches or
      lifts (`Gate::expire`, `Gate::push`), and present it as a 40 ms tap
      ending at the lift. Host test
      `a_long_still_two_finger_press_reaches_libinput_only_at_the_lift`.
      Proof (host): `cd nix/touch-trackpad && cargo test` -- 49 and 2 tests
      pass.

## 2. Board

- [ ] 2.1 On HDMI, after a live deployment restarts sway, the first two-finger
      swipe on Home pages it. A two-finger press held for about 1 s with the
      cursor on a widget enters rearrange mode, both before and after a swipe.
      Use a fake protocol-B touchscreen fed to a second daemon instance
      (`--device=`), so the run covers the real gate, relay, libinput and
      shell path. Evidence class: injected raw touch + shell log.
- [ ] 2.2 The operator swipes between Home pages and right-clicks a widget with
      a two-finger press on the trackpad. Evidence class: operator observation.
