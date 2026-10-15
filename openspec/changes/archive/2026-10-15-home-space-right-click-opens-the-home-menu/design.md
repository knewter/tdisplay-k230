## Context

Home's menu (Widgets / Wallpaper & style / Home settings) opened only from a
long press on an empty Home cell (`HomeScreen::down` sets
`empty_slot_at_down`, `tick` opens the menu after `LONG_PRESS_MS`). The
secondary-click handler in `main.rs` `pointer_frame` (button 0x111) resolved
only app icons (`HomeScreen::app_at`), so a right-click on empty Home space
did nothing. On HDMI the board's touchscreen is a libinput touchpad with
`tap enabled` and `tap_button_map lrm`, so a two-finger tap is a right-click.

## Goals / Non-Goals

**Goals:** a right-click on empty Home space opens the same Home menu as the
long press, with the same exclusions.

**Non-Goals:** changing how taps become clicks, the app menu, or the long
press.

## Decisions

1. **One method on `HomeScreen`, the long press's conditions.**
   `open_menu_at` refuses while the menu is open, while rearranging, with a
   folder open, or during a drag or contact. It opens only on an addressable
   cell that `filled_slot_at` does not resolve, which is the same test as
   `empty_slot_at_down`.
2. **Apps first.** The handler still asks `app_at` first and opens the app
   menu when there is one; `open_menu_at` runs only when no app was hit.
3. **Evidence.** A host unit test covers empty space, an icon and an
   already-open menu. The operator's two-finger taps on the HDMI trackpad are
   the board proof.
