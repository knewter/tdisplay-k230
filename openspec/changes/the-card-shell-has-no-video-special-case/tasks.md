## 1. Remove the video special-casing

- [x] 1.1 Remove `struct card.video_view`, `video_app_id()`, and every
  app_id check from `nix/card-shell/adapter.c`; replace the `ordinary`
  command's exclusion with a generic transient test
  (`con->view->wlr_xdg_toplevel->parent`), keeping
  `card_shown_large()`/`card_source_size()` unchanged (already generic).
  Verify with a clean `nix build .#card-shell --max-jobs 1 --cores 6`.
- [x] 1.2 Remove `card_shell_video_stop()` (`nix/card-shell/route.c`/
  `route.h`) and `SWAY_K230_CARD_VIDEO_STOP` (`nix/shell.nix`); a card's
  close sends only the ordinary xdg_toplevel close, for every app.
- [x] 1.3 Fold `nix/shell.nix`'s separate video `for_window` rule into one
  generic `[app_id=".+"]` ordinary-card rule (no `[tiling]` qualifier).
  Verify with `nix eval .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel.drvPath`.

## 2. Fix mpv relaunch-on-close in the launcher

- [x] 2.1 `nix/video-session.py`: track whether mpv ever printed a
  first-frame status line (`V:  ...`); only fall back to the software
  decoder when MVX failed *before* any frame was shown. Verify with
  `python3 -m pytest tests/test_video_session.py -v` (adds
  `test_mvx_exit_after_first_frame_does_not_fall_back`).

## 3. Generalize the scaled-cache path and make it the default

- [x] 3.1 `scaled_mirror` (`nix/card-shell/adapter.c`): remove the
  video-only frozen-thumbnail branch; every card not shown at full panel
  size (`card_shown_large()`) is capped to about 15fps (66ms) of
  recomposition instead, refreshed on every commit once due -- never
  frozen indefinitely. Add `scene_in_motion()` (factored out of
  `tick_impl`'s own frame-scheduling gate) and use it to select a cheap
  nearest filter while animating/dragging, bilinear at rest
  (`card_scale_rgb565`'s new `fast` parameter,
  `nix/card-shell/scaled-cache.c`/`.h`, threaded through
  `card_scaled_buffer_create`, `nix/card-shell/render.c`/`.h`). Verify
  with `python3 tests/test_card_scaled_cache.py -v` (adds a
  nearest-vs-bilinear divergence assertion) and a clean
  `nix build .#card-shell --max-jobs 1 --cores 6`.
- [x] 3.2 Make `SWAY_K230_CARD_SCALED_CACHE=1` the shipped default
  (`nix/shell.nix`).

## 4. Tests and QEMU regression

- [x] 4.1 Update `tests/test_card_shell_video_card.py` for the single
  generic `for_window` rule and the removed stop-hook assertion; it now
  proves mpv's historical app_id gets the same ordinary/switchable/
  closable treatment as any other app, with no compositor-side
  video-stop call to check for. Verify with `python3
  tests/test_card_shell_video_card.py -v` (7/7 passes observed against
  real cross-built Sway under `qemu-riscv64-static`).
- [ ] 4.2 <!-- UNVERIFIED: tests/card_shell_runtime.py's own
  `focused()=='k230.card.two'` assertion (line ~578, after a full
  horizontal drag then an immediate tap) was found already failing on
  the pre-change baseline (commit 59e0eb78) during this work, unrelated
  to anything in this change -- confirmed by running the identical test
  against a worktree checked out at that commit. Not fixed here; flagged
  as a pre-existing issue for a separate task. -->

## 5. Board verification

- [ ] 5.1 <!-- UNVERIFIED: with a live video playing AND, separately, a
  busy non-video app (e.g. `yes` in foot, or btop) in the deck: overview
  entry completes in under about 400ms; a touch is acted on within about
  100ms; the small preview is visibly live (never frozen); flick, switch
  and close all work; closing the video card makes mpv exit with
  `pgrep -x mpv` empty and no relaunch. Record commands, journal
  excerpts, and a camera contact sheet under
  `docs/evidence/card-shell/live-card-cost/` (or the existing
  `docs/evidence/card-shell/video-card-gestures/`), with blob-inventory
  rows; `python3 tools/blob-scan.py` must exit 0. -->

## 6. Proposal validation

- [x] 6.1 Validate this change; verify with `openspec validate
  the-card-shell-has-no-video-special-case --strict`.
