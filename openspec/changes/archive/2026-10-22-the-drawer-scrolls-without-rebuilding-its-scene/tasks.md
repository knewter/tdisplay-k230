## 1. Proposal

- [x] 1.1 Validate this change with `openspec validate the-drawer-scrolls-without-rebuilding-its-scene --strict`.

## 2. Client source (host proof)

- [x] 2.1 Memoize `render::wrapped_line_count` and `render::measured_text_width` with a bounded cache.
- [x] 2.2 Blit the drawer grid at a whole-pixel offset with a nearest filter.
- [x] 2.3 Repaint only the drawer grid band on a scroll-only frame. `render::tests::scrolling_repaints_clipped_rows_but_keeps_chrome` must show one rebuild and pixel equality with a fresh rebuild at whole and fractional scrolls.
- [x] 2.4 Journal only the first `touch-move` of each contact.
- [x] 2.5 Draw drawer motion on the frame callback when a frame is pending; cache the drawer sheet (`render::tests::the_cached_drawer_sheet_copies_the_same_pixels_it_paints`); report band-only damage on scroll frames.
- [x] 2.6 Proof: `cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml --lib` (581 passed), `--bins` (23 passed) and `--test responsive_pixel_identity` (4 passed) on 2026-10-22.

## 3. Profiling tool (board proof)

- [x] 3.1 Add `tools/board-profile.py` and document it in `docs/runtime-tracing.md`.
- [x] 3.2 Capture a drawer-scroll profile on the installed board before and after the change, with injected native touch. Commit the folded stacks, flamegraph SVGs and summaries under `docs/evidence/interaction-jank/drawer-profile/`.
  Done 2026-10-22: `profile-before` (`8xkkpma4`), `profile-after1` (`c702z5mz`) and `profile-after2` (`z1basiwi`), with injected native touch. Client sampled CPU fell from 8,794 to 2,121 ms per 30 s. See `docs/evidence/interaction-jank/drawer-profile/README.md`.

## 4. Board measurement (hardware-only)

- [x] 4.1 Build and test-activate the change on the board.
  Done 2026-10-22: `z1basiwicixzdgqsdbklczd0prnlwbjd` was activated with `switch-to-configuration test`. It is not the boot default. Persistent promotion remains.
- [x] 4.2 Run the unprofiled `drawer-scroll.py` workload on the installed result. Compare `K230_DRAWER_FRAME` and the presented frame rate with the 39 ms / 8.3 fps baseline and the ~20 ms target, and record a failed target as failed.
  Done 2026-10-22 with injected native touch (runs after2 and after3).
  - Contact render: median 6.3 ms, p95 8.3–9.0 ms, against the 39.5 / 53.4 ms baseline. The ~20 ms render target is met, except for one 24.8 ms outlier.
  - Presentation: distinct presented frames rose from 8.2 to about 20 per second. Intervals are 38.3 ms, which still misses the 33.334 ms card tracking budget.
- [x] 4.3 Update `docs/design/app-drawer-review.md` §6. Propose scroll-direction blitting only if 4.2 still misses the target and the profile points at the blit.
  Done 2026-10-22: the profile does not point at the client blit, so scroll-direction blitting is not proposed. Two diagnostics put the remaining limit in the compositor:
  - `max_render_time 7` left the cadence unchanged.
  - The compositor benchmark shows an 18.3 ms median sway repaint of the 514,976 px band.
