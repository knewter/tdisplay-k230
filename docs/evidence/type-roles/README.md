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
  at `46d46038`: all eight targets passed (lib: 570 passed, 2 ignored), with
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

## Board evidence (2026-10-16)

- **Deploy.** Commit `46d46038` was deployed live with `deploy-live.sh`.
  The board ran
  `/nix/store/f7hplx7lwc3zl1pppj1q6bjdbfyzscfk-nixos-system-nixos-26.11.20260919.20b1ddd`
  on the HDMI output (1280x800, the only active output), with the
  retro-82 theme.
- **Text step.** It was set with `k230-theme vision --text-scale
  {default,larger,largest}` and returned to `larger` (160%) afterwards.
- **Each frame.**
  1. Settings, opened with `k230-shell-rust --surface settings`.
  2. The Vision page, reached by an injected pointer tap (uinput,
     `tools/board-pointer.py`) on the "Vision ›" link at that step's
     position: (1026, 109) at 100%, (911, 138) at 160%, (833, 164) at 200%.
     It opened at every step, so paint and hit-test agree.
  3. The Shade, opened with `--surface shade`.
- **Capture.** `grim`, each frame scaled to 50%, captured at
  2026-10-17T04:05Z (UTC).

| File | Content |
|---|---|
| `board-hdmi-100.png` | Settings, Vision, Shade at 100%. |
| `board-hdmi-160.png` | The same at 160%. |
| `board-hdmi-200.png` | The same at 200%. |

**Fixes from the first board deploy.** An earlier deploy (`a1a3f97b`) at
160% showed three faults, all fixed in `46d46038`:

- Settings' Keyboard gesture hint was cut off at the 26 px floor. It is now
  two short lines, "Two fingers up: show" and "Drag handle down: hide".
- In the Shade, "0 notifications" was larger than the shrunken Title.
  Header rows now keep their ratio to the Title.
- The Shade hint was cut off beside the battery. It now drops out instead.

That deploy's Settings, Vision and Shade frames were not committed.

## Limits

- **Board frames are HDMI only.** The landscape panel was not active, so
  task 5.1 (panel captures) remains open.
- **Shade hint.** On the 480 px controls column, the Shade's hint line is
  left out at every step whenever a battery is present.
- **Volume value.** Volume read 100% in one frame and 40% in another. The
  default sink changed between deploys (Dummy Output, then Built-in Audio);
  this change did not touch it.
- **Bigger at 100%.** Settings at 100% now shows text about as large as
  the old 160%. It scrolls in landscape at every step and in portrait
  from 100%.
- **Narrow landscape Shade.** The landscape Shade's 480 px controls column
  keeps the header near the Label floor at 160% and 200%: the Title is
  about 36 px.
- **Not yet on the roles.** The theme chooser's own carousel headings, the
  Wi-Fi pages, the Power sheet and the drawer are unchanged.
