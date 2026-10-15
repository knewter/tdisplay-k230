## Why

The operator, using the HDMI trackpad on 2026-10-15, expected a two-finger
right-click on empty Home space to open the Home menu (Widgets / Wallpaper &
style / Home settings). Today only a long press there opens it. Secondary
click on empty space does nothing; it opens the app menu only on an app icon
(`main.rs` secondary-click handler, `HomeScreen::app_at`).

## What Changes

- A secondary click on an empty, addressable Home cell opens the Home menu,
  under the same conditions as the long press. It does not open while the
  menu is already open, while rearranging, with a folder open, or during a
  drag or contact.
- Secondary click on an app icon keeps opening that app's menu; nothing else
  changes.

## Impact

- `nix/rust-shell-client/src/home_screen.rs` (`HomeScreen::open_menu_at`) and
  the secondary-click branch of `pointer_frame` in `main.rs`.
- Spec: `runtime/home-screen` gains one requirement.
