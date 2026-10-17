# Card jobs and the one-accent rule

Change: `openspec/changes/the-shell-has-one-visual-language`, tasks 3.1–3.3.

## What changed

- **Three card jobs.** `render.rs` paints cards through `paint_card` with a
  `CardJob`:
  - **Group:** the theme's flat card tint, at radius 24 (`CARD_RADIUS_GROUP`).
  - **Control:** the same card at radius 16 (`CARD_RADIUS_CONTROL`), with
    a 5% text-colour tint on top and a 1 px top line in the text colour
    at 10%.
  - **Chosen:** the accent at 18% plus a 2 px accent rim. It is drawn as a
    pill when it marks a segment.
- **Where Chosen is used:**
  - On the Vision page, the chosen text-size step is a pill around its
    label. The other steps have no card, and the Text size card is a
    Group.
  - High contrast is Chosen when on and Control when off.
  - On the theme grid, the current theme has a 2 px Chosen rim.
- **Where Control is used:** the Settings rows (generic, Volume, Key
  backlight), the Reboot and Power off cards, the Shade's Keyboard toggle,
  the drawer search pill and the dock.
- **One accent.** The following now use the foreground colour:
  - links: Done, Vision ›, Themes ›, the chooser's ‹ Settings and Close,
    and the Shade's Settings › (which gained its chevron);
  - the drawer's Help;
  - values ("100%", "On"/"Off");
  - notification and preview source names (now Medium weight).

  The grab handles use the text colour at 50%. The accent remains only on:
  - the current choice;
  - "Dismiss all", the Shade's one primary action;
  - slider fills and thumbs, which are exempt because they mark the
    current value rather than act as links.
- **Not converted:** the Wi‑Fi pages, the Help page buttons and the theme
  carousel keep their existing card and accent use.

## Host evidence (2026-10-17)

- `cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml --tests`:
  - All targets passed (lib: 571 passed, 2 ignored).
  - This includes the new
    `render::tests::the_accent_marks_only_the_current_choice_on_settings_vision_and_the_shade`.
    That test renders each surface at 568x1232 and 1232x568, puts pixels
    within 30 of the theme accent into 8 px cells, joins cells within two
    cells of each other, and counts the groups.
  - Results: Settings 0 (no audio device; brightness is read-only, so it
    has no slider), Vision 1 (the chosen step) and the Shade 1 (Dismiss
    all).
- **Pixel-identity baselines.** The `docs/evidence/shell-responsive/`
  `settings-*`, `drawer-*` and `home-*` frames were regenerated
  deliberately with `render_responsive_evidence`. The differences are the
  link colour, the handle colour, the Control rims and the dock's Control
  treatment.
- **Renders.** The frames come from `render_accessibility_scale_evidence`.
  - **Dark:** the default and largest catppuccin generations from
    `docs/evidence/coherent-shell/accessibility-scale/README.md`
    (`5c64a4c1de62429c468041bc`, `0fc1fc47cd7b409f46f67425`).
  - **Light:** two catppuccin-latte generations, prepared the same way from
    the pinned omarchy `themes/catppuccin-latte` source with
    `theme_vision.save` before each `theme_activate.prepare`:
    - `default-latte`: `c3f3ed1da29e4794867c6407`;
    - `largest-latte`: `3d3427bb1dcfe70d59c085c3`.
  - The example reads the step from the first `-` segment of the name, so
    the latte generations were named `<step>-latte`. Each sheet is scaled
    to 50%.

| File | Content |
|---|---|
| `host-dark-default-landscape.png` | 1232x568 at 100%, 2x2: Settings, Vision (top); Shade, drawer (bottom). |
| `host-dark-largest-landscape.png` | Same at 200%. |
| `host-dark-default-portrait.png` | 568x1232 at 100%, left to right: Settings, Vision, Shade, Home. |
| `host-dark-largest-portrait.png` | Same at 200%. |
| `host-latte-*.png` | The same four sheets in catppuccin-latte. |

The grey area under the Vision page and the Shade is the example's
backdrop, not the shell.

## Limits

- The theme grid's Chosen rim is not in the host renders; it is in the board capture.
- The board captures are below. The operator's
  judgement on glass (5.1, 5.2) are separate evidence classes.

## Board evidence (2026-10-17)

- **Build.** `kernelMainlineDrmShellLandscapeHdmiBootFiles` was built at
  `2d80b1e2` and deployed live with `switch-to-configuration test`. The
  active system was
  `/nix/store/wsjjmyhq7p069g62fqi8bf7ypmbix0z3-nixos-system-nixos-26.11.20260919.20b1ddd`.
- **Capture.** HDMI was unplugged, so DSI-1 was the only output, at 1232x568
  landscape and the 100% step, with the retro-82 theme.
- **Navigation.** Each surface was opened with `k230-shell-rust --surface`.
  The Vision and Themes links were reached with injected uinput taps
  (`/tmp/bp.py`), not a finger. The frames are native `grim` captures.

| File | What it shows |
|---|---|
| `board-panel-settings.png` | Control rows, Reboot/Power off, links in the foreground colour, slider accent |
| `board-panel-vision.png` | Text size as a Group with the 100% Chosen pill; High contrast Off as Control |
| `board-panel-shade.png` | Shade with no notifications: "Settings ›" in the foreground colour, Keyboard as Control |
| `board-panel-themes.png` | Theme grid with the current theme behind a Chosen rim (other previews still loading) |

- **Not covered here.** The operator has not yet looked at the panel
  (task 5.2). These captures don't show "Dismiss all", because the board
  had no notifications.
