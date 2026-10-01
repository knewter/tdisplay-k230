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
- [x] 4.2 Fixed the pre-existing host-only flake this task originally only
  flagged: `tests/card_shell_runtime.py`'s `focused()=='k230.card.two'`
  assertion (after a full horizontal drag then an immediate tap) raced
  `cs_up`'s deliberate release-continuity coast (up to a 760ms settle,
  `nix/card-shell-policy/card-shell-policy.c`) -- a tap fired immediately
  after release could land before the newly selected card reached center.
  The test now waits past the documented worst-case coast before tapping,
  and a second, independently found capture race in the same drag loop
  (`during-drag.png`, grim run immediately after an IPC `motion` with no
  wait for the next composited frame) now polls instead of asserting a
  single screenshot. No compositor source changed. Verify with `python3 -m
  unittest test_card_shell_scaled_cache_runtime -v` (run from `tests/`;
  both `SWAY_K230_CARD_SCALED_CACHE=0` and `=1` passed, reproduced clean on
  three additional direct invocations). Root cause, fix and verification
  recorded in `docs/evidence/card-shell/runtime-tap-after-drag-race/
  README.md`.

## 5. Board verification

- [x] 5.1 Accept functional real-finger ordinary-card/video behavior from the operator's 2026-10-01 report in `docs/evidence/proposal-closeout/2026-10-01/ordinary-cards.md`, supplementing existing board-injected live-preview/switch/close evidence. Transfer the unperformed sub-400ms entry and sub-100ms touch-ack measurements to `the-shell-profiles-reported-interaction-jank` task 4.1, already landed before archive; neither timing target is represented as measured or passing.

## 6. Proposal validation

- [x] 6.1 Validate this change; verify with `openspec validate
  the-card-shell-has-no-video-special-case --strict`.

Coordinator note (2026-09-28): `video-windows-become-ordinary-cards` archived
today (0 open tasks; `openspec/changes/archive/2026-09-28-video-windows-
become-ordinary-cards`), creating `openspec/specs/runtime/card-shell/
spec.md` with a Requirement named "A video playback window is an ordinary,
closable card" that describes the app_id-keyed stop hook and video-only
thumbnail freeze this change already removes from source. This change's own
delta spec (`specs/runtime/card-shell/spec.md` here) is currently authored
as `## ADDED Requirements` under a *different* requirement name ("Card
eligibility, close, and deck-preview cost do not vary by app identity"),
which its own grounding text already says "generalizes and replaces" the
now-archived one. Whoever archives this change once task 5.1's board
evidence lands should rewrite this delta as `MODIFIED`/`REMOVED` against
the now-existing "A video playback window is an ordinary, closable card"
requirement (per `openspec/config.yaml`'s archive guidance: "Check the
delta's operation against what openspec/specs/ actually holds"), not leave
both requirements sitting side by side describing contradictory behavior.

Closeout reconciliation (2026-10-01): the contradictory archived video-only
requirement is removed by this delta; generic behavior replaces it. Historical
coordinator advice above is satisfied by the REMOVED/ADDED operations.
