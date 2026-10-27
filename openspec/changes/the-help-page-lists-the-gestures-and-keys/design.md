## Context

`help.rs` owns Help's text, layout, scroll extent and hit-testing. `render.rs`
paints from `help::layout`, so a tap and its paint cannot drift apart. That
stays true here.

## Decisions

- **One flat guide, two groups.** `GUIDE` stays a flat list in reading order.
  `TOUCH_COUNT` marks where Touch ends and Keys begins, so the paint loop over
  `GUIDE` is unchanged. `layout` adds each group heading's origin.
- **Wide: two columns.** Touch fills the left column. The two buttons keep
  their place at the top of the right column, because Return to All apps is
  how a person leaves Help. Keys continues under them.
- **Portrait: stacked.** Touch, Keys, then the buttons, as the buttons already
  followed the guide.
- **Type roles.** Group headings use the label size in bold with the accent
  colour. Entry titles and details keep the label and caption roles. All sizes
  multiply by the vision text step, as before.
- **Scrolling.** The guide is longer than 568 units of height, so the guide
  scrolls at 100% in both orientations through the existing `help_scroll` and
  `max_scroll`. The navigation aid, which has no guide, still fits at 100%.
  The wide scale is unchanged, so text does not shrink to make it fit.
- **Grounding of each entry.**
  - Quick-switch along the bottom band, throw-to-close, side-edge dismissal,
    the keyboard gesture and handle, and the base keys: `runtime/shell`,
    `runtime/handheld-shell-design` and `runtime/card-shell` specs.
  - App menu on a held drawer tile: `main.rs` `hold_drawer_app_menu` opens the
    menu with the window list, New Window and Add to Home; `app_actions.rs`
    reads desktop actions.
  - LILYGO, LILYGO + Tab, Fn + LILYGO: `nix/shell.nix` bindings.
  - Esc: `nix/keyboard-base/keyboard_based.py` (`--escape-back`).
  - Power key: `nix/power-keyd/power_keyd.py` (`short` toggles the display,
    `hold` shows the sheet).
- **Dropped.** The drawer-search key claims, which the code contradicts (see
  the proposal's non-goals).

## Risks

- The text is longer, and the largest vision step grows it further. It scrolls,
  and the host renders cover 100%.
- The wrapped-height measure is slightly conservative, so a block can leave a
  small gap under a line count that painted shorter.
