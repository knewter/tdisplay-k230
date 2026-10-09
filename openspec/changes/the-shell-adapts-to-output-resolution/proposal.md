## Why

`nix/rust-shell-client` is authored entirely against the 568x1232 portrait
AMOLED: `lib.rs`'s `configure_preserves_aspect` rejects any Wayland
layer-surface configure whose aspect drifts more than 10% from
568:1232, so the panel's own occasional keyboard-exclusive-zone squish gets
rejected instead of squashing every glyph. `feat/hdmi-pillarbox` (commit
`4c2eb57c`, same day) hit this the moment an HDMI monitor's own whole-output
configure (1920x1080 landscape, or 1080x1920 rotated portrait) failed that
same check, and made it pass by asking the compositor for a centered
568-aspect column instead — the shell drew, but pillarboxed, with black bars
either side. The operator does not want that: plugging in a wider monitor
should make the shell use the extra space, not float a narrow column inside
it. `openspec/changes/the-hdmi-shell-works-in-landscape/tasks.md` group 5
("Shell and card-shell landscape support," tasks 5.2–5.3) already named this
exact gap — "not visually broken... without necessarily redesigning the
layout for landscape" — before any HDMI output existed to test it against;
this change is that work, now that a whole-output configure is something
the client actually receives (`feat/hdmi-pillarbox`'s own board log:
`pillarbox 1080x1920 -> 885x1920`, Home and wallpaper visibly on
`HDMI-A-1`).

Two different resize shapes reach the exact same `LayerShellHandler::
configure` callback and must be told apart: a genuine whole-output resize
(an HDMI monitor at its own size, any aspect) and a keyboard-exclusive-zone
shrink confined to one axis (the regression `configure_preserves_aspect`
itself was added to catch, 2026-09-28, `wvkbd` squashing the Wi-Fi page to
about 0.66x height). Both fail the same aspect check. Only one of them
should ever be accepted at its own size; the other must still be rejected.

## What Changes

- Replace the pillarbox fallback with whole-output acceptance:
  `main.rs`'s three `LayerShellHandler::configure` branches (wallpaper,
  Home, and the shared Drawer/Shade/Settings/Power overlay) now accept a
  configure that fails `configure_preserves_aspect` when, and only when,
  it exactly matches a currently known output's own logical size
  (`is_whole_output`, replacing the removed `pillarbox`/`pillarbox_width`).
  A keyboard-style shrink is never a whole output and stays rejected,
  unchanged.
- Widen the geometry sanity bounds that assumed a panel-or-pillarboxed-
  column width: `lib.rs`'s `frame_bytes` (was `300..=1024` on width, now
  `300..=2048` on both axes) and `background_decode.rs`'s still-wallpaper
  decode bounds (`MAX_OUTPUT_WIDTH`/`MAX_OUTPUT_PIXELS`, was 1024/1024×2048,
  now 2048/2048×2048) — both previously hard-rejected a real 1920-wide
  configure outright, independent of the pillarbox question.
- Make the Drawer's grid genuinely reflow instead of just stretching: a new
  `navigation::columns_for_width` scales the drawer's column count with the
  configured width (proportional to this panel's own 4 columns at 568px),
  so a wide HDMI output gets more, similarly-sized columns rather than 4
  very wide, sparse ones. Purely a live geometry/hit-test computation (no
  persisted per-column state to keep in sync), used by `tile_rect`,
  `tile_at` and `max_scroll`.
- Audit the rest of the fixed-568/1232 surface (`render.rs`, `home_grid.rs`,
  `home_pager.rs`, `home_state.rs`, `wifi_ui.rs`) and record, in
  `design.md`, what already reflows for free, what this change makes
  reflow, and what stays a deliberately deferred follow-up.
- **Follow-up, same branch (coordinator-requested after the above landed):**
  add a shared `crate::density_scale`/`crate::reflow_columns` pair (`lib.rs`)
  and use them for two further reflows, each guarded by new host tests:
  - Home's grid/dock now reflow their column count too, exactly like the
    Drawer's, via a new `columns` field on the persisted `HomeLayout` and
    `HomeLayout::reflow_to` -- a safe migration (flatten the stored items in
    reading order, re-place them through the existing, already-tested
    `place_first_fit` bin-packing at the new column count) that never
    drops, duplicates, or reorders a pinned item, and round-trips
    4→8→4 back to the exact original page shape. `HomeScreen::sync_columns`
    keeps it in lockstep with the live surface width, called once per
    `draw_home`.
  - Settings' body content (everything below its unscaled header strip) now
    paints in a centered column, scaled by `crate::density_scale`, instead
    of stretching row cards edge to edge on a wide output or leaving a
    short, content-sized "stub" panel over empty space on a tall one.
    `service_ui::panel_intent`'s Settings arm maps a touch point through
    the identical transform before its row-rhythm checks, so paint and
    hit-test can never drift apart.
  - `tests/responsive_pixel_identity.rs` (new) decodes each committed
    `docs/evidence/shell-responsive/*-568x1232.png` and asserts it is
    byte-for-byte identical to a fresh render through the same
    `evidence_render` module on every `cargo test` -- an automated,
    durable form of "568x1232 stays pixel-identical," not just a one-time
    visual check at capture time.

**Non-goals:** Home's and the Drawer's own icon/text *pixel sizes* do not
scale with `density_scale` -- only their column counts reflow. A tall,
dense HDMI output gets more same-sized (80px-icon) tiles, not visibly
larger ones the way Settings' text/rows now do; a literal icon/text density
scale for the grid surfaces remains a named follow-up (see `design.md`).
Settings' Wi-Fi sub-page (its own pre-existing, independent, non-uniform
`cr.scale(width/568.0, height/1232.0)`) and the theme chooser are untouched
by and excluded from the new content transform -- `scene`'s Settings arm
returns before reaching it whenever either sub-page is open. No kernel,
device-tree, or board-flashing change of any kind; this change touches only
`nix/rust-shell-client`. No board or QEMU access is used or required to
implement or test it — see `tasks.md` for what remains genuinely
board-gated.

## Capabilities

### Modified Capabilities

- `runtime/shell`: adds a requirement that the shell fills a whole
  non-panel output at its own resolution instead of letterboxing it, while
  keeping the existing keyboard-squish rejection intact.

## Impact

- `nix/rust-shell-client/src/lib.rs`, `main.rs`, `navigation.rs`,
  `background_decode.rs`, and their existing test suites
  (`cargo test`/`cargo clippy --all-targets`, host-only, no board/QEMU
  needed for these files' own unit tests).
- New host-render evidence under `docs/evidence/shell-responsive/` (a new
  `examples/render_responsive_evidence.rs` harness), showing Home, the
  Drawer, Settings and the wallpaper background at 568x1232, 768x1024,
  1080x1920 and 1920x1080 through the real production paint path — not a
  Wayland/QEMU/board capture; see that directory's own `README.md` for
  exactly what is and is not proven.
- No change to any Nix derivation, device tree, kernel patch, or the SD
  image; `nix build .#handheld-shell-rust`-style closures are unaffected in
  shape, only in the Rust source they build from.
- Real HDMI-attached board verification (does the compositor actually offer
  this client a whole-output configure at 1920x1080/1080x1920 today, does
  a person's finger land on the reflowed drawer tiles correctly) remains
  open and board-gated, tracked in `tasks.md` and cross-referenced from
  `the-hdmi-shell-works-in-landscape`'s own task 5.4.
