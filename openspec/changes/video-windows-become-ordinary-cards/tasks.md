## 1. Card eligibility

- [x] 1.1 Remove `k230-video-software`/`k230-video-mvx` from `card_shell`
  adapter.c's `ordinary` command exclusion (`video_app_id`), keeping the
  `wants_floating` exclusion for genuine transient/popup views; verify with
  `python3 tests/test_card_shell_state.py` (unaffected: policy-layer only)
  and a clean `nix build .#card-shell --max-jobs 1 --cores 6`.
- [x] 1.2 Give both video app_ids the same `card_shell ordinary, floating
  enable, resize set 100 ppt 100 ppt, move position 0 0` for_window
  treatment as every other coherent-shell app (`nix/shell.nix`), keeping the
  old 480x270/568x320 floating rule only for the plain (non-coherent-shell)
  touch launcher, which has no deck to close a card from; verify with
  `nix eval .#nixosConfigurations.k230.config.system.build.toplevel.drvPath`.

## 2. Close stops the controller, not only the window

- [x] 2.1 Add `card_shell_video_stop()` (`nix/card-shell/route.c`/`route.h`),
  spawning `$SWAY_K230_CARD_VIDEO_STOP stop` (`k230-video-session stop`)
  alongside the existing `view_close()` whenever a closed card's
  `video_view` is set; wire `SWAY_K230_CARD_VIDEO_STOP` in `nix/shell.nix`.
  Verify with `nix build .#card-shell --max-jobs 1 --cores 6` and the QEMU
  regression in 4.1.

## 3. Deck thumbnail does not pay continuous decode-to-thumbnail cost

- [x] 3.1 Add `struct card.video_view` and `card_shown_large()`
  (`nix/card-shell/adapter.c`); freeze `scaled_mirror`'s cached copy on its
  most recently captured frame once a video card has one and is not shown
  at full panel size, unconditionally re-checking size so a resize/entry
  transition still snaps to correct geometry. <!-- UNVERIFIED: this freeze
  only engages under the opt-in SWAY_K230_CARD_SCALED_CACHE=1 path; the
  default (scaled-cache off) raw-mirror path still points the deck
  thumbnail at mpv's live decoded buffer every sync, so real CPU-cost
  reduction in the shipped default configuration remains unmeasured. A
  dedicated small always-on cached buffer for video mirrors, independent of
  the general scaled-cache toggle, is a named follow-up, not claimed done
  here. --> Verify with `nix build .#card-shell --max-jobs 1 --cores 6`;
  non-video cards take an unchanged code path (`c->video_view` false), so
  every existing card-shell QEMU suite continues covering them.

## 4. QEMU regression

- [x] 4.1 `tests/test_card_shell_video_card.py` proves, against real
  cross-built Sway under `qemu-riscv64-static` with injected touch: a video
  app_id reaches full ordinary-maximized card geometry; a real touch-first
  vertical entry swipe from a focused video card is accepted into the
  overview; the video card is a genuine, switchable deck member reachable
  by `previous`/`next` (the persistent-button route a lateral release
  resolves to); requesting its close sends the ordinary xdg_toplevel close
  and invokes the video-stop helper exactly once; the other ordinary card
  and the deck are unaffected. Verify with `python3 -m unittest
  test_card_shell_video_card` (run from `tests/`, 7/7 consecutive passes
  observed). `docs/evidence/card-shell/video-card/README.md` records the
  command and log excerpt. <!-- UNVERIFIED: no board evidence; QEMU cannot
  prove mpv decode, MVX hardware fallback behavior, or physical
  close-gesture feel -- those stay with runtime/video's existing board
  evidence and a future physical check. -->

## 5. Proposal validation

- [x] 5.1 Validate this change; verify with `openspec validate
  video-windows-become-ordinary-cards --strict`.
