## 1. Implementation

- [x] 1.1 Add `HomeScreen::rearrange_at` and call it from the secondary-click
      path in `main.rs` after `app_at` and before `open_menu_at`. Host tests:
      a right-click on a widget enters rearrange mode with no drag; on an app
      or empty space it does not.
- [x] 1.2 Paint a remove badge on widgets in rearrange mode at
      `HomeScreen::badge_corner`, and hit-test the same corner in `badge_at`.
      Host test: clicking a widget's badge removes it.
      Proof (host): `cd nix/rust-shell-client && cargo test` -- 540 lib tests
      pass (2 ignored), and the other suites pass.

## 2. Board

- [x] 2.1 On HDMI, a scripted right-click (`tools/board-pointer.py`) on a
      widget enters rearrange mode showing widget badges; a scripted click on
      a widget's badge removes it. Capture with grim.
      Evidence class: injected pointer + grim.
      Done 2026-10-15: right-click on page 1
      (`docs/evidence/home-screen/widget-right-click/README.md`); right-click
      and a badge click removing a widget on page 2
      (`docs/evidence/home-screen/page-settle/README.md`).
- [x] 2.2 The operator right-clicks a widget on the trackpad, then moves or
      removes it. Evidence class: operator observation.
      Done 2026-10-15: operator verdict "works ship"; physical right-click on a
      widget logged at 23:47 and badge removals at 22:14 (`docs/evidence/home-screen/operator-trackpad-2026-10-15.md`).

