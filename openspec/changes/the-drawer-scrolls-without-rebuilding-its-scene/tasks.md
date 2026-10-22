## 1. Proposal

- [ ] 1.1 Validate this change with `openspec validate the-drawer-scrolls-without-rebuilding-its-scene --strict`.

## 2. Client source (host proof)

- [ ] 2.1 Memoize `render::wrapped_line_count` and `render::measured_text_width` with a bounded cache.
- [ ] 2.2 Blit the drawer grid at a whole-pixel offset with a nearest filter.
- [ ] 2.3 Repaint only the drawer grid band on a scroll-only frame. `render::tests::scrolling_repaints_clipped_rows_but_keeps_chrome` must show one rebuild and pixel equality with a fresh rebuild at whole and fractional scrolls.
- [ ] 2.4 Journal only the first `touch-move` of each contact.
- [ ] 2.5 Proof: `cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml --lib`.

## 3. Profiling tool (board proof)

- [ ] 3.1 Add `tools/board-profile.py` and document it in `docs/runtime-tracing.md`.
- [ ] 3.2 Capture a drawer-scroll profile on the installed board before and after the change, with injected native touch. Commit the folded stacks, flamegraph SVGs and summaries under `docs/evidence/interaction-jank/drawer-profile/`.

## 4. Board measurement (hardware-only)

- [ ] 4.1 Build and test-activate the change on the board.
- [ ] 4.2 Run the unprofiled `drawer-scroll.py` workload on the installed result. Compare `K230_DRAWER_FRAME` and the presented frame rate with the 39 ms / 8.3 fps baseline and the ~20 ms target, and record a failed target as failed.
- [ ] 4.3 Update `docs/design/app-drawer-review.md` §6. Propose scroll-direction blitting only if 4.2 still misses the target and the profile points at the blit.
