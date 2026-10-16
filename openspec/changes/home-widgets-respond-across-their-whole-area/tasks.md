## 1. Implementation

- [x] 1.1 Hit multi-cell widgets across their painted rect in
      `HomeScreen::filled_slot_at`. Add a regression test using the board's
      1280x800 layout, where (300, 300) on the page 2 widget sits in a column
      gap and a row gap.
      Proof (host): `cd nix/rust-shell-client && cargo test` -- 537 lib tests
      pass (2 ignored), and the other suites pass.

## 2. Board

- [ ] 2.1 On HDMI, a scripted long press (`tools/board-pointer.py`) at
      (300, 300) on the widget enters rearrange mode. Capture it with grim.
      Evidence class: injected pointer + grim.
- [ ] 2.2 The operator moves or removes a widget with the trackpad on HDMI.
      Evidence class: operator observation.
