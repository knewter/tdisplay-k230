## Why

A person cannot close network video today. `k230-video-software` and
`k230-video-mvx` (mpv, launched by `nix/video-session.py`) were deliberately
excluded from `card_shell ordinary` alongside real transient/popup views
(`nix/card-shell/adapter.c`'s now-removed "video and transient views stay
unmarked" check), so a playing video stayed a small 480x270/568x320 floating
window: no card, not in the overview, not reachable by the bottom-edge
switch gesture, and with no other close control in this touch-only shell. A
user who ends up on the video entry (deliberately, or by an accidental tap
while navigating the drawer) has no way back except restarting the session.
Board evidence: a real session in which nobody deliberately tapped Video
still ended up with Big Buck Bunny playing and unclosable.

## What Changes

- Give `k230-video-software` and `k230-video-mvx` the same ordinary-maximized
  card treatment as every other coherent-shell application: full-panel,
  present in the overview, reachable by the bottom-edge switch gesture, and
  closable by the same swipe-up-to-close every other card uses. The
  480x270/568x320 floating geometry is kept only for the plain (non-card-shell)
  touch launcher, which has no deck to close a card from.
- Requesting a video card's close now additionally asks the
  `video-session.py` controller itself to stop (`card_shell_video_stop`,
  `SWAY_K230_CARD_VIDEO_STOP`), not only the xdg_toplevel close request the
  compositor already sends every other card. Without this, the controller
  cannot distinguish "the user closed the card" from "the decoder died", and
  the MVX fallback path relaunches a fresh software player right after the
  card is closed -- the observed "unclosable video" is `xdg_toplevel` close
  alone not being enough, not a missing gesture.
- A video card's deck-sized thumbnail stops rebuilding itself from every
  newly decoded frame once it has a captured thumbnail and is not currently
  shown at full panel size (`struct card.video_view`, `card_shown_large`),
  matching every other card's static-while-small treatment instead of paying
  continuous decode-to-thumbnail rescale cost for motion nobody can see in
  the deck. The thumbnail still updates live whenever the card is actually
  shown large (focused full-screen, mid-entry, or expanded).

## Capabilities

### New Capabilities

None. `runtime/card-shell` is being defined by the sibling, still-open
`the-shell-manages-apps-as-cards` change, so it does not exist under
`openspec/specs/` yet; this change ADDs one further requirement to the same
capability rather than MODIFYing text that is not archived. Whichever change
archives first creates `openspec/specs/runtime/card-shell/spec.md`; the
other's later archive adds to it. Neither change depends on the other's
archive order for its own requirement to stand.

### Modified Capabilities

None.

## Impact

- `nix/card-shell/adapter.c`, `nix/card-shell/route.c`/`route.h`: card
  eligibility, the video-close helper call, and the frozen-thumbnail
  optimization.
- `nix/shell.nix`: `for_window` rules (video is `card_shell ordinary` under
  `coherentShell`; the old floating rule is kept only when card-shell is
  off) and the new `SWAY_K230_CARD_VIDEO_STOP` environment variable.
- `nix/video-session.py` is unchanged: its existing `stop` subcommand and
  `k230-video-session stop` process-group teardown already do what the new
  helper call needs.
- No kernel, boot, or device-tree change. QEMU can prove card membership,
  switch/close reachability, and that closing a video card does not leave a
  second process running; it cannot prove decoded-frame presentation or
  physical touch, which stay with `runtime/video`'s existing board evidence.
