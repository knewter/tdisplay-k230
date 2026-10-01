## Why

Board evidence (docs/evidence/card-shell/video-card-gestures/) showed the
overview taking several seconds to enter, and touches going unacted-on,
whenever a video card was present and playing -- because the video card's
own mirror was expensive to recompose on every one of mpv's frequent
commits. The fix that shipped for that (video-windows-become-ordinary-cards)
special-cased video specifically: a `struct card.video_view` flag, an
app_id check (`video_app_id()`), a frozen-thumbnail path that only engaged
for video under the opt-in `SWAY_K230_CARD_SCALED_CACHE` toggle, and a
compositor-side close hook (`card_shell_video_stop()` /
`SWAY_K230_CARD_VIDEO_STOP`) spawning `k230-video-session stop` so its
controller would not mistake a close for a decoder failure and relaunch a
fallback player.

The user's stated principle: "there should not be any special-case shit for
video right it should just show the window because it's a compositor." The
actual cost driver -- Pixman composite work for a small deck thumbnail
whose source keeps committing new frames -- is not specific to video at
all: a game or a busy scrolling terminal commits just as often and would
pay the identical cost once it sat in the deck. Special-casing video hid a
generic performance problem behind an app_id check instead of fixing it,
and left a second, needless special case (the close hook) that only exists
because video's controller cannot otherwise tell "the user closed my
window" from "my decoder died."

## What Changes

- **BREAKING** (compositor-internal only, no user-facing API): remove
  `struct card.video_view`, `video_app_id()`, and every app_id check in
  `nix/card-shell/adapter.c`. Ordinary-card eligibility is decided
  generically: a real transient/popup (an xdg_toplevel with a parent) stays
  unmarked; a client that merely reports a fixed, non-resizable size (which
  used to need the video carve-out to avoid `wants_floating`'s min==max-size
  heuristic) is treated like any other ordinary app.
- Remove `card_shell_video_stop()` (`nix/card-shell/route.c`/`route.h`) and
  the `SWAY_K230_CARD_VIDEO_STOP` environment variable
  (`nix/shell.nix`). Closing a card sends only the ordinary xdg_toplevel
  close, for every app, with no compositor-side hook back to any
  particular client's launcher.
- Fold `nix/shell.nix`'s separate video `for_window` rule into the single
  generic ordinary-card rule (now matching any app_id, not just `[tiling]`
  ones, so a client that maps floating due to a fixed-size hint -- video's
  own reason for needing a second rule -- needs no separate match either).
- Generalize the existing downscaled-mirror path
  (`SWAY_K230_CARD_SCALED_CACHE`, previously opt-in and video-only-frozen)
  to every card, and make it the shipped default:
  - it refreshes on every client commit -- no card's preview is ever frozen;
  - a card not currently shown at full panel size is capped to about 15fps
    of re-composite work, for every app equally;
  - a cheap nearest-neighbor filter is used while the scene is actively
    animating/dragging; the default bilinear filter is used at rest.
- `nix/video-session.py` (the video-launch controller, not part of
  card-shell) replaces the removed stop hook with its own signal: it tracks
  whether mpv ever printed a first-frame status line, and only falls back
  to the software decoder when MVX failed *before* any frame was shown.
  Closing the window (or any other post-first-frame exit) never relaunches
  a fallback player.
- Update `tests/test_card_shell_video_card.py`,
  `tests/test_video_session.py`, and `tests/card_scaled_cache.c` for the
  above; the QEMU regression now proves mpv's historical app_id gets no
  special treatment, rather than proving a video-specific mechanism works.
- Mark `video-windows-become-ordinary-cards` superseded where its task 2.1
  (`card_shell_video_stop`) and task 3.1 (the video-only freeze) describe
  mechanisms this change removes; that change's own history is left intact.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `runtime/card-shell`: card eligibility, close behavior, and the deck's
  live-preview cost model no longer vary by app identity; the downscaled,
  rate-capped mirror path is the default for every card.

## Impact

- `nix/card-shell/adapter.c`, `nix/card-shell/route.c`,
  `nix/card-shell/route.h`, `nix/card-shell/scaled-cache.c`,
  `nix/card-shell/scaled-cache.h`, `nix/card-shell/render.c`,
  `nix/card-shell/render.h`, `nix/shell.nix`, `nix/video-session.py`.
- `nix/card-composition-probe-client/card-composition-probe-client.c`
  (a stale comment only; the QEMU test fixture's behavior is unchanged).
- Tests: `tests/test_card_shell_video_card.py`, `tests/test_video_session.py`,
  `tests/card_scaled_cache.c`, `tests/test_card_scaled_cache.py` (unchanged,
  exercises the same `card_scale_rgb565` entry point with a new parameter).
- Runs under QEMU (`tests/test_card_shell_video_card.py`,
  `tests/card_shell_runtime.py`) and needs the physical board for the
  performance claim itself (entry-animation and touch-latency targets with
  a live video and a separate busy non-video app) -- see design.md and
  tasks.md for what is QEMU-provable versus board-only.
