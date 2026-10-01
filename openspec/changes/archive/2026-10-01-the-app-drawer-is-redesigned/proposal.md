## Why

Operator report, verbatim: "when i swipe down in the app drawer to scroll
back up, it closes the drawer that's no good also review the design of the
app drawer it's fuggin awful as is performance." The scroll-reversal
drag-to-close bug landed separately, in its own reviewed commit. This
change covers the other two complaints, after a first attempt at both was
reviewed by the coordinator and correctly rejected: the redesign "was the
same design with a 4th column" (only `COLUMNS`/icon sizes changed; tile
plates, header, footer all unchanged), and the performance fix (a label
cache alone) still estimated 95-236ms/frame on the board — "isn't a fix."

Full review, including the rejected first attempt and why it fell short:
`docs/design/app-drawer-review.md`.

## What Changes

- **Redesign**, matching Android 14-16 / Material 3 Expressive and the
  Pixel launcher's drawer:
  - Per-app tiles: just a 64px icon and a single-line ellipsized 14px
    label, no card/plate/box (`paint_drawer_tile`, `render.rs`). Icon
    fallback: a round, theme-accent-tinted circle with the initial —
    confirmed rare against a real catalog (`docs/evidence/app-drawer/`).
  - The "YOUR DEVICE / All apps / Everything installed…" header and the
    "Swipe down to return to cards" footer are removed entirely,
    replaced by a slim drag handle and a rounded, pill-shaped "Search
    apps" field (`paint_drawer_chrome`, `render.rs`;
    `navigation::handle_rect`/`search_field_rect`).
  - **Search, implemented** (reopening a prior explicit deferral, at the
    coordinator's direction): tapping the field focuses it and raises a
    new, compact, lowercase-only on-screen keyboard
    (`navigation::search_keyboard_key_at`), filtering the grid live and
    case-insensitively by substring (`service_ui::filter_app_indices`) —
    a cheap, uncached linear scan over this repo's bounded (128-entry)
    catalog. An alphabetical fast-scroller remains explicitly out of
    scope (needs its own grid-width layout coupling this device's small
    catalog does not justify).
  - The sheet: an opaque theme surface colour, 28px top-corner radius,
    filling from a small fixed top inset (`navigation::panel_top`,
    replacing the old ~19%-of-height gap) rather than most of a screen
    of dead space above it.
  - The grid: 4 columns, 64px icons, ~110px row pitch, equal 24px
    margins/gutters (dividing this panel's 568px width with no
    remainder, so the grid needs no separate centering offset), a
    subtle round press highlight instead of a bordered square.
- **Performance**: a pre-rendered grid bitmap (`DrawerGridCache`,
  `render.rs`), rebuilt only when the filtered catalog, theme, panel
  width or search query actually changes; an ordinary scroll/fling frame
  reuses it and blits one viewport-sized slice instead of repainting
  every tile. `IconCache::paint_label` (from the earlier, rejected
  attempt) is retained — it is what makes each real *rebuild* (e.g. one
  search keystroke) cheap. Host benchmark, driving the real
  `RendererCache::draw` path over 200 simulated scroll frames of a
  64-app catalog: cold (fresh cache every frame) 33.6ms/frame, warm
  (persistent, scroll-only) 0.87ms/frame — a 38.8× reduction. Scaled by
  this repo's own established 20-40x host-to-board multiplier, the
  estimated board cost is 17.3-34.6ms/frame: straddling the ~20ms target
  (clears it at the low end of the multiplier, not at the high end) —
  reported honestly as **UNVERIFIED**, a real order-of-magnitude
  improvement over both the original uncached approach and the earlier
  rejected label-cache-only attempt, not claimed as a confirmed pass.
  `K230_DRAWER_FRAME ms=…` (rate-limited, `main.rs`) lets the coordinator
  read the real number on the board directly.

## Capabilities

### Modified Capabilities

- `runtime/shell`: modifies the app grid's presentation requirement (no
  per-app plate, round icon fallback, search) and adds a requirement for
  board-readable drawer frame timing. See `specs/runtime/shell/spec.md`
  in this change. (The drag-to-close direction-correctness requirement
  from the earlier bug-fix commit is unchanged by this change.)

## Impact

`nix/rust-shell-client` only (Rust shell client): `navigation.rs`,
`service_ui.rs`, `main.rs`, `render.rs`, `icon.rs`. No device tree,
kernel, or NixOS module changes. No new dependency. `cargo build
.#handheld-shell-rust` and the full system closure both cross-build
(riscv64) as proof the change compiles for the target; no QEMU or board
run was performed for this change. Real-finger, on-board frame-timing,
and real-finger search verification remain open gates (`tasks.md` §6).

Follow-up after real-glass acceptance (2026-09-30): search should use the normal wvkbd keyboard shared with Foot and Wi-Fi. The operator noticed the current compact custom keypad; track replacement, focus cleanup, reflow and new physical proof in tasks 6.1–6.3.

## Accepted closeout, 2026-10-01

The operator accepts this delivered functional scope and waives additional
capture-only acceptance gates. `docs/evidence/proposal-closeout/2026-10-01/drawer.md` records the exact report,
prior evidence and limits. Its task dispositions supersede older statements
that these acceptance gates remain open; they do not claim new test runs.

Pending measurement work is preserved in `the-shell-profiles-reported-interaction-jank` before archive.
