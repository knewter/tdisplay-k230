## Context

`nix/card-shell/adapter.c` currently special-cases video in three places:
`video_app_id()` gates ordinary-card eligibility, `struct card.video_view`
gates a frozen-thumbnail path inside `scaled_mirror` (itself gated behind
the opt-in `SWAY_K230_CARD_SCALED_CACHE`, off by default), and closing a
video card additionally spawns `$SWAY_K230_CARD_VIDEO_STOP stop`
(`nix/card-shell/route.c`). Board evidence
(`docs/evidence/card-shell/video-card-gestures/`) traced the actual
overview-responsiveness problem to `scaled_mirror`/the raw mirror fallback
recomposing a card's content on every client commit, which is expensive
under this compositor's Pixman software path and has nothing to do with
the client being video specifically -- any frequently-committing client
(a game, a busy terminal) pays the identical cost once it sits in the
deck.

## Goals / Non-Goals

**Goals:**
- Delete every video-specific code path in `nix/card-shell/adapter.c`,
  `route.c`/`route.h`, and `nix/shell.nix`; card eligibility and close
  behavior are decided the same way for every app.
- Make the downscaled-mirror path the default for every card, refreshing
  on every commit (no freezing), with a generic ~15fps cap for small
  thumbnails and a cheap-filter-while-moving optimization -- so the
  *reason* video needed a special case (recomposition cost) is fixed
  generically instead of hidden behind an app_id check.
- Move "did the user close this, or did decode fail" detection into
  `nix/video-session.py` itself (first-frame-seen), since there is no
  longer a compositor-side signal for it.

**Non-Goals:**
- Card geometry/corner-radius changes: explicitly left to
  `feat/android-sized-cards` (a concurrent branch); this change does not
  touch card sizing or radius.
- A full "only re-sync the scene on geometry change, never on content
  commit" architecture change -- considered, not implemented; the
  refresh-rate cap and filter choice are the scoped fix here.
- Anything about mpv's own decode path, MVX hardware fallback correctness,
  or `runtime/video`'s existing board evidence, beyond the relaunch-on-close
  behavior this change fixes in the controller.

## Decisions

- **Transient test, not app_id test.** `cmd_card_shell`'s `ordinary`
  handler now excludes a container only when its view is an xdg_toplevel
  with a parent set (`con->view->wlr_xdg_toplevel->parent`). This is
  strictly narrower than the old `wants_floating()` check (which also
  excluded any fixed-size, non-resizable window) and needs
  `#include <wlr/types/wlr_xdg_shell.h>` for the full struct definition.
  XWayland is disabled in this build (`enableXWayland = false`), so the
  `wlr_xdg_toplevel` union member is always the live one.
- **One `for_window` rule.** `nix/shell.nix`'s `[tiling app_id="^(?!k230-video-...).+"]`
  and video's separate `[app_id="^k230-video-...$"]` rule become one
  `[app_id=".+"]` rule with no `[tiling]` qualifier, so a window that maps
  floating for any reason (video's own fixed-size hint, or any other
  client's) still reaches the same ordinary-maximized treatment.
- **`card_source_size()` stays generic, unchanged in spirit.** The
  earlier fix (using a card's real committed container box instead of
  the client's self-reported geometry for the entry-transition anchor
  math) was already keyed on `card_shell_ordinary_maximized`, not app
  identity; nothing about it needed to change for this proposal.
- **Refresh cap and filter live in `scaled_mirror`, keyed on
  `card_shown_large()`/`scene_in_motion()`.** Both are pre-existing
  concepts (a card shown at full panel size, and the scene actively
  animating) reused rather than duplicated: `scene_in_motion()` is
  factored out of `tick_impl`'s own frame-scheduling gate so
  `scaled_mirror` can share the exact same "is something moving right
  now" answer.
- **~15fps (66ms) and nearest-vs-bilinear are fixed constants, not
  configurable.** Simpler to reason about and board-verify; revisit only
  if board evidence shows the wrong number.
- **First-frame detection via mpv's own stdout status line.** mpv's
  terminal status begins printing `V:  HH:MM:SS / ...` only once a
  decoded frame has actually been shown; `nix/video-session.py` already
  parses stdout for a different diagnostic (`truncated_http`), so this
  reuses the same `PlayerOutput.feed()` path rather than adding a new
  IPC round-trip over mpv's `--input-ipc-server` socket.

## Risks / Trade-offs

- The generic transient check (parent-only) is narrower than
  `wants_floating()`'s combined heuristic; a genuine dialog-style app
  that sets a fixed size but never sets a parent would now become an
  ordinary card where it previously would not have. No such client is
  known to exist in this shell today (checked: only mpv relied on the
  fixed-size exclusion).
- Capping refresh to ~15fps for small, non-focused cards is a real,
  intentional trade-off: a very fast-moving thumbnail (e.g. an
  action game) will look slightly less smooth at deck-thumbnail size.
  Traded deliberately for overview responsiveness; a card shown large
  (focused, mid-entry, mid-expand) is never capped.
- `first_frame_seen` is a heuristic (mpv's own terminal output format),
  not a protocol guarantee; if mpv's status-line format changes upstream,
  the fallback-suppression could regress silently. Bounded risk: the
  fallback is a safety net for a decode failure, not the close-detection
  path anymore, so a false negative here only means an occasional missed
  fallback, not a broken close.
