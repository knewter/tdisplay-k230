# Settings, Vision and the Shade on the type roles

Change: `openspec/changes/the-shell-has-one-visual-language`, task 2.1.

## What changed

- **Constants.** `render.rs` names the five type roles (`TYPE_TITLE` 40,
  `TYPE_BODY` 30, `TYPE_LABEL` 26, `TYPE_CAPTION` 26; Display stays sized
  from the widget cell) and the 8 px rhythm (`SPACE_IN_ROW` 8,
  `SPACE_BETWEEN_ROWS` 16, `SPACE_CARD` 24, `SPACE_GROUP` 32). Sizes are
  design pixels at 100%, before the vision step.
- **Text calls.** Settings, the Vision page (with the chooser's Back/Close
  header) and the Shade set their text through `themed_role` and
  `themed_role_fit`:
  - A theme's `font.*` token can make a role larger, up to 1.25x, but
    never smaller than the role.
  - At a larger step, a line that would be cut off shrinks to fit its
    column, but never below the role's 100% size. Nothing is drawn under
    26 px.
- **One layout at every step.** Each of these surfaces used to have two
  layouts: fixed 100% coordinates, plus a computed layout for the larger
  steps. Now only the computed one is left.
  - Settings rows size to their lines, and the body scrolls under the
    header when it does not fit.
  - The Shade's Keyboard toggle (`shade_toggle_h`) and its notification
    rows grow with the step, and the list (`notification_top`) moves down
    with them.
  - The Vision page puts "Applies to every theme" beside the Title when
    the cards are side by side, so the page still fits the 568 px
    landscape panel at 200%.
- **Shared rows.** Lines that share a row shrink together and keep their
  ratio, so the Title stays larger than its Settings link. In the Shade,
  that applies to "Notifications" with Settings, and to the count with
  "Dismiss all".
- **Shade hint.** The hint line ("Swipe up above the list to close", plus
  the battery) is left out only when the Dismiss all band has no room for
  it.

## Host evidence (2026-10-16)

- `cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml --tests`
  at `a1a3f97b`: all eight targets passed (lib: 570 passed, 2 ignored), with
  `responsive_pixel_identity` passing against the deliberately updated
  `docs/evidence/shell-responsive/settings-*.png`.
- **Renders.** The frames come from `render_accessibility_scale_evidence`,
  using the default/large/larger/largest generations described in
  `docs/evidence/coherent-shell/accessibility-scale/README.md`. Each frame
  was scaled to 50%.

| File | Content |
|---|---|
| `host-settings-landscape-steps.png` | 1232x568 Settings, 2x2: 100%, 130% (top), 160%, 200% (bottom). |
| `host-settings-portrait-steps.png` | 568x1232 Settings, left to right: 100%, 130%, 160%, 200%. |
| `host-vision-landscape-steps.png` | 1232x568 Vision page, same grid. |
| `host-vision-portrait-steps.png` | 568x1232 Vision page, same order. |
| `host-shade-landscape-steps.png` | 1232x568 Shade with two notifications, same grid. |
| `host-shade-portrait-steps.png` | 568x1232 Shade, same order. |

## Limits

- **Host renders only**, until a board section is added.
- **Bigger at 100%.** Settings at 100% now shows text about as large as
  the old 160%. It scrolls in landscape at every step and in portrait
  from 100%.
- **Narrow landscape Shade.** The landscape Shade's 480 px controls column
  keeps the header near the Label floor at 160% and 200%: the Title is
  about 36 px.
- **Not yet on the roles.** The theme chooser's own carousel headings, the
  Wi-Fi pages, the Power sheet and the drawer are unchanged.
