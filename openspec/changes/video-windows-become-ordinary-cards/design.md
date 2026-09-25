## Context

Video windows (`k230-video-software`, `k230-video-mvx`) were excluded from
`card_shell ordinary` and stayed small floating windows. The touch-only shell
had no control that could close them, and the MVX fallback path relaunched a
software player after an `xdg_toplevel` close.

## Goals / Non-Goals

**Goals:**

- Make a playing video an ordinary card: full-panel, in the overview,
  reachable by the bottom-edge switch gesture, closable by swipe-up.
- Make closing the card end playback for good, with no relaunch.
- Keep video thumbnails from rescaling every decoded frame while they are
  small in the deck.

**Non-Goals:**

- Changing decoders, `nix/video-session.py`, the kernel, or the device tree.
- Changing the floating geometry of the plain, non-card-shell launcher.

## Decisions

1. Treat video app IDs as `card_shell ordinary` under `coherentShell` in
   `nix/shell.nix`. Keep the old floating rule only when card-shell is off.
2. When a video card is closed, also run the controller's existing `stop`
   (`SWAY_K230_CARD_VIDEO_STOP`). The controller then cannot mistake a user
   close for a decoder failure.
3. Freeze a video card's thumbnail once it has been captured and the card is
   not shown large. Update it live only while the card is focused
   full-screen, entering, or expanded.

## Risks / Trade-offs

- A frozen thumbnail can show a stale frame in the overview. That matches
  every other card and saves continuous rescale cost on a single slow core.
- QEMU proves card membership, gesture reachability, and single-process
  teardown. Decoded-frame presentation and physical touch still need board
  evidence.
