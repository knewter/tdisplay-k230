## 1. Home menu on secondary click

- [x] 1.1 `HomeScreen::open_menu_at` opens the Home menu on an empty
      addressable cell, under the long press's conditions; the
      secondary-click handler calls it when the click is not on an app.
      Host test:
      `home_screen::tests::secondary_click_on_empty_home_space_opens_the_menu_but_not_on_an_icon`
      (`cd nix/rust-shell-client && cargo test --lib`, 514 passed,
      2026-10-15).
- [x] 1.2 Board: on the HDMI trackpad, a two-finger click on empty Home
      space opens the Home menu and a two-finger click on an app still opens
      its app menu (operator report). 2026-10-15, system
      `/nix/store/acmin041a4hb7nglym6h1lcm66sp3wyh-nixos-system-nixos-26.11.20260919.20b1ddd`
      (bundle `6cchn05l…`, HDMI 1280x800, tap_button_map lrm). The operator
      tried both and said "both work". Evidence class: operator report, no
      capture.
