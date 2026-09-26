# Video card trap: root cause, fix, and board verification

Evidence class: board webcam recording with **injected** touch (evdev, via
`evemu-device`/`tools/inject-tap.sh`) for the open and close gestures, plus
the compositor's own `card_shell` debug/step IPC (`swaymsg card_shell
previous|next|debug-scene`) used to select a card deterministically for the
switch step -- the deck's own per-card screen rects are not exposed by any
external query, and a hand-computed guess at their pixels proved unreliable
for a horizontal drag. Not a real finger. Captured 2026-09-26.

## The report

"the video's on the screen and i can't close it or interact with the screen
any more". The coordinator stopped it with `k230-video-session stop`. The
compositor log from the incident:

```
for_window '[app_id="^k230-video-(software|mvx)$"]' matches view ...
  cmd: 'card_shell ordinary, floating enable, resize set 100 ppt 100 ppt, move position 0 0'
K230_CARD_SHELL map id=12 class=2
K230_CARD_SHELL restored focus=12 message=10   (repeated on every later gesture)
```

`message=10` is `CS_MESSAGE_FAILED`: the overview never opened, and
`cs_leave`'s fallback re-focused the same full-screen video (id 12) every
time -- the trap.

## Root cause

`nix/card-shell/adapter.c`'s `sync_card`/`sync_scene_impl` feed the
direct-switch entry gesture's anchor math (`cs_entry_set_geometry`) the
card's **source rect**: the on-screen box the app is dragged away from. For
every other app this is `view->geometry.width/height`, because a
well-behaved xdg_shell client acks the compositor's `resize set 100 ppt 100
ppt` and its own reported window geometry ends up matching the container's
real, full-panel size.

mpv's `--vo=wlshm` (launched by `nix/video-session.py` with
`--force-window=yes --geometry=480x270` or `568x320`) does not: it ignores
the resize configure entirely and keeps reporting its small initial decode
buffer as `view->geometry` forever, even once `card_shell_commit`'s
`ordinary_resize` has put its container at the full `568x1232` panel size.
Confirmed live on the board via `swaymsg -t get_tree` while a video card was
mapped:

```
"rect":        {"x": 0, "y": 0, "width": 568, "height": 1232}   # container: correct, full panel
"window_rect": {"x": 0, "y": 0, "width": 568, "height": 1232}   # correct
"geometry":    {"x": 0, "y": 0, "width": 480, "height": 270}    # view's own geometry: stale, the launch size
```

Feeding that stale `480x270` into `cs_entry_set_geometry` as the source rect
puts the gesture's anchor point far past the bottom of the screen (the
anchor fraction `(edge.y-source_y)/source_height` blows up with the tiny
`source_height`), so `travel < config.entry_distance` and the call is
rejected on the very first frame of the direct-switch entry gesture -- for
every subsequent attempt, since nothing about mpv's geometry ever changes.

## Diagnostic logging (commit `fb30f890`)

Added a failure-only `sway_log(SWAY_INFO, ...)` naming the reason at every
silent `return false` in `sync_scene_impl`, `sync_card`, `sync_node`,
`chrome_impl`/`rebuild_chrome`. Built and test-activated as
`i6mz5kzrg9rrkln7040gbgnddq2l8afz-nixos-system-nixos-26.11.20260919.20b1ddd`,
reproduced the bug with a real mpv session and injected touch, and got the
exact new log line for the first time:

```
K230_CARD_SHELL sync_scene fail reason=entry-geometry-rejected id=6
K230_CARD_SHELL restored focus=6 message=10
```

(id 6 was the video card in that session; matches the incident's id 12
exactly in shape.)

## Fix and safety net (commit `4ad12358`)

- `card_source_size()` (new, in `adapter.c`) feeds an ordinary-maximized
  card's real **committed container box**
  (`container->current.content_width/content_height` -- always exactly the
  output's usable area for this card class) as the source rect, instead of
  `view->geometry.width/height`. A compliant client's geometry already
  tracks its resize exactly, so this changes nothing for every other card;
  it only stops trusting a client (mpv) that never acks the resize. Used at
  both call sites: `sync_scene_impl`'s `CS_ENTERING` fast path and
  `sync_card`'s `cs_entry_set_geometry`/`cs_entry_visual_rect` calls. The
  small deck thumbnail's own aspect-fit sizing keeps using the view's real
  geometry (480x270) unchanged, since that one wants the decoded video's
  actual aspect ratio, not the full-panel box.
- Safety net: a mirror-sync failure inside `sync_card` (a wlshm buffer the
  compositor can't sample, an allocation failure under memory pressure) no
  longer fails the whole scene sync. The affected card falls back to its
  plain plate + icon + title (the same placeholder already used for
  `CS_PRIVATE`/`CS_UNAVAILABLE` cards), with no live mirror that frame, and
  the overview still opens -- so a mirroring failure alone can never trap
  the user behind a full-screen card again, even for a cause other than the
  one reproduced here.
- `tests/card_shell_policy_driver.c`: added
  `entry_geometry_rejects_undersized_source`, pinning the exact mechanism at
  the policy layer -- the identical edge/finger state that opens the
  overview with the real full-panel source rect is rejected outright with a
  small one. Registered in `tests/test_card_shell_state.py`. Host run,
  `cc -std=c11 -Wall -Wextra -Werror -pedantic -g -fsanitize=address,undefined`:
  all 35 cases pass (`python3 tests/test_card_shell_state.py -v`).

## Board verification

System test-activated:
`c57f8gflr1hw25hddp67rd960j5kyw5c-nixos-system-nixos-26.11.20260919.20b1ddd`
(`fix/video-card-gestures` at `4ad12358`, base `feat/more-apps` at
`1e17d6c5`), replacing
`i6mz5kzrg9rrkln7040gbgnddq2l8afz-...` (the logging-only build used for the
repro above), which replaced the board's prior system
`har97636isrripp3iyi0gf9ar04mg2v9-...`.

Video started the way the drawer does (`k230-video.desktop`'s
`Exec=k230-video-session run`), as the `shell` user with
`XDG_RUNTIME_DIR=/run/shell WAYLAND_DISPLAY=wayland-1`. Injected touch via
an `evemu-device` clone of `/dev/input/event0` (real GT9895 description),
driven with `tools/inject-tap.sh` (open, panel pixels on the 568x1232
portrait panel) and a small custom `close-throw.sh` (fewer/larger steps than
the generic drag helper, so per-step speed reliably clears the deck's
`throw_speed=0.4px/ms` close threshold).

1. **Open** -- bottom-edge swipe-up, `(284,1228)->(284,760)`:
   `K230_CARD_SHELL_DEBUG_SCENE ... mode=1 ... selected_app_id=k230-video-software`
   (`mode=1` is `CS_DECK`). No `entry-geometry-rejected`, no
   `message=10` anywhere in the log for the rest of the session. Camera:
   `contact-sheet.png` panel 1 (video full-screen, the state the user was
   stuck in) -> panel 2 (overview open, the video's real thumbnail small and
   centered).
2. **Switch** -- `swaymsg card_shell previous` moved the deck's selection
   off the video card to the other live card (`selected_app_id=k230-terminal`
   in `debug-scene`); a plain tap `(284,550)` on the now-centered card
   (injected touch) expanded it to full screen:
   `K230_CARD_SHELL restored focus=5 message=0`. The video kept playing in
   the background, unaffected.
3. **Swipe-up close** -- back in the deck (`swaymsg card_shell next`
   reselected the video card), a fast injected vertical throw on the video
   card's own rect, `(284,900)->(284,400)` over ~120ms
   (`close-throw.sh /dev/input/event1 284 900 400`):
   ```
   K230_CARD_SHELL close-request id=7
   K230_CARD_SHELL state mode=1 actions=33 message=9 cards=1
   K230_CARD_SHELL unmap id=7
   ```
   (`message=9` is `CS_MESSAGE_SOURCE_GONE`.) No
   `video-stop-helper unavailable` log line, so `card_shell_video_stop()`
   (the `SWAY_K230_CARD_VIDEO_STOP` helper, i.e. `k230-video-session stop`)
   was actually invoked and succeeded, alongside the ordinary xdg_toplevel
   close.
4. **Confirmed stopped**: `pgrep -x mpv` empty immediately after, and the
   `k230-inject-video` unit wrapping `k230-video-session run` had exited
   (`systemctl is-active` -> `inactive`) -- the session controller's own
   process ended, not merely the mpv child. Camera: `contact-sheet.png`
   panel 3 (deck now shows only the remaining terminal card; the video
   thumbnail is gone).
5. Left the deck (`swaymsg card_shell back`): `active=0 mode=0`, back to
   the normal Home/ordinary-app state, no video playing.

Rollback timer (`k230-deploy-restore.timer`) disarmed after activation;
`readlink -f /run/current-system` confirms `c57f8gfl...` is what the board
is actually running.

## Not established

A real-finger check by the user on the glass. Everything above is injected
touch (open, close) or the compositor's own deterministic step/debug IPC
(switch); no physical finger touched the panel for this change.

## Follow-up: the overview became unusable after opening ("no touches
## register"), on `integrate/apps-video-catalog`

Reported after the fix above landed on an integration build carrying the
apps/live-catalog/shade changes rebased with it: "once i open the cards
list i can't do anything no touches register". Reproduced with injected
touch (`/run/k230-vo.sh`: launch video, bottom-edge swipe-up, tap, flick,
tap) against system
`p40rq5r8w8pfibl7nyhkr6vq4qs0w3n7-nixos-system-nixos-26.11.20260919.20b1ddd`
(the first fix's commits rebased onto `integrate/apps-video-catalog`, no
further change yet). Extended the `state mode=...` debug log with
`entry_settling/entry_reversing/entry_interrupted_hold/entry_progress/
blocked_until_up/blocked_contacts` to see the mechanism directly instead of
guessing from mode numbers alone.

**Root cause 1** (`card-shell-policy.c`, commit `f53f451c`): a touch
landing during the post-release entry settle triggers `cs_down`'s
existing "catch and reverse" path, which sets `entry_interrupted_hold`
and freezes `cs_tick`'s own elapsed-time computation until that same
contact's `up` clears the hold via `cs_up` -- but adapter.c routes every
`up` through `cs_entry_up_at` while `mode == CS_ENTERING` (covers both
settling and reversing), which only ever resolves the *original*
bottom-edge contact and bails for any other id. The interrupting
contact's own release can therefore never reach `cs_up`, so the hold has
no way to clear on its own; a chain of closely-spaced touches (tap, then
flick, then another tap, each landing before the previous one's hold
could clear) held the transition frozen far longer than its own ~240ms
clock. Fix: `entry_interrupt_started_ms` bounds the freeze to one settle
duration regardless of whether that contact's `up` ever arrives, then
proceeds on the untouched `entry_started_ms` timeline. New policy test
`entry_settle_completes_despite_stuck_interrupt` models the worst case
directly (an interrupting touch that never gets an `up` at all).

**Root cause 2** (`adapter.c`, commit `2c838d0b`, then `1ff6a837`):
board-reproduced separately -- launching video and swiping up almost
immediately let the video's `xdg_shell` map (`card_shell_observe`) land
*while* the deck was already `CS_ENTERING`. The brand-new card had never
captured a scene position, so `sync_card`'s entering branch hard-failed
it (`reason=entry-source-invalid`), which failed the whole `sync_scene`,
which `cs_leave`-with-`CS_MESSAGE_FAILED`'d the entire transition back to
`CS_NORMAL` with a stray `blocked_until_up` left behind -- matching the
report exactly:
```
K230_CARD_SHELL sync_card fail id=6 reason=entry-source-invalid
K230_CARD_SHELL sync_scene fail reason=card-sync-failed id=6
K230_CARD_SHELL restored focus=5 message=10
```
Fix: only the `entry_id` card (the one actually being dragged away from
its live position) needs a real captured position; any other card
appearing mid-transition is now skipped for the rest of the entry
animation (`reason=entry-source-not-ready`) instead of aborting the whole
transition. A follow-up board run then surfaced a second-order bug this
introduced: `sync_card`'s own position capture was gated on
`!c->hidden`, and a deferred card is marked `hidden` on the very same
frame, so it could never become `source_valid` -- a later tap-to-expand
on that exact card failed the identical way forever
(`reason=expand-source-invalid`). `1ff6a837` lets a card keep retrying
its position whenever `!c->hidden || !c->source_valid`, preserving the
existing freeze-once-valid-and-hidden behavior other cards rely on for
their entry/expand return-to-source animation.

**Performance finding, not fully resolved** (`adapter.c`, commit
`ef63a564`): with both correctness bugs fixed, the entry animation still
took ~4.2-4.4s wall-clock end to end (bottom-edge swipe release to
`CS_DECK`) against the coordinator's ~400ms target, with `state mode=4`
steps landing roughly every 150-250ms instead of ~20ms. `handle_result`
was running a full, synchronous `sync_scene()`+`chrome()` pass for
*every* raw touch motion sample (tens a second during the drag),
duplicating what the existing 16ms `tick_impl` timer already guarantees
moments later. Coalescing that redundant per-sample sync to at most once
per ~12ms during an active gesture is a safe, real improvement (touch
dispatch itself is unaffected, since it is computed from policy state
alone) but did **not** measurably shorten the ~4.2s total, because
`tick_impl`'s own unconditional per-16ms `sync_scene()` call (via
`card_shell_prepare`) is equally expensive and is not gated by this
throttle -- the dominant cost is each `sync_scene()` pass itself taking
~150-200ms wall time while mpv decodes and Pixman recomposites the whole
568x1232 output in software, not how many times it is invoked per touch
sample. The coordinator was explicit that the small preview must stay
live (no freezing, no pausing mpv), so the only path left to meet the
timing target is to make each recomposition of the video card's mirror
cheaper while still updating every commit -- e.g. extending the existing
`SWAY_K230_CARD_SCALED_CACHE` machinery's cheap pre-scaled-buffer path to
video cards unconditionally, with its "frozen thumbnail" behavior
removed, rather than reducing how often the mirror is refreshed. That is
follow-up work, not done here.

### Board verification (system
`28qilnk3zqlivjgij78ahqnjvnjz8j5y-nixos-system-nixos-26.11.20260919.20b1ddd`,
`integrate/apps-video-catalog` at `1ff6a837`)

With all three correctness/coalescing commits applied, a full injected
`/run/k230-vo.sh` run (swipe-up, tap, flick, tap) and a follow-up
`swaymsg card_shell` enter/next/close cycle produced **zero**
`reason=...` failure or defer lines and **zero** `message=10`/restored
focus with `CS_MESSAGE_FAILED` anywhere in the journal across multiple
repeated runs. Concretely:

- Bottom-edge swipe-up: `state mode=1` (`CS_DECK`) reached, video's own
  mirror created (`mirror id=6 ... width=568 height=320`), no failure.
- A tap on the deck's centered card correctly expanded it
  (`restored focus=5 message=0`, `message=0` is success, not
  `CS_MESSAGE_FAILED`).
- `swaymsg card_shell enter` / `next` / `close` against the video card:
  `close-request id=6` -> `source-gone id=6` -> `unmap id=6`, and
  `pgrep -x mpv` empty immediately after -- the video actually stops.
- The overview never got stuck; every gesture eventually completed and
  the shell returned to a normal, interactive state.

**Not met**: the ~400ms/~20ms-step timing target, for the performance
reason above -- entry still takes several real seconds end to end while
mpv is actively decoding. Contact sheet
`contact-sheet-overview-freeze.png` (webcam, injected/IPC-driven, not a
real finger): video full-screen live -> overview open with the video's
real live thumbnail -> overview after close (video card gone, mpv
exited). Rollback timer disarmed after activation;
`readlink -f /run/current-system` confirms `28qilnk3...` is what the
board is actually running, with no video playing and no failed units.

**Still not established**: a real-finger check, and the deeper
performance fix (cheap live pre-scaled video mirror, decoupled from
`SWAY_K230_CARD_SCALED_CACHE`'s frozen-thumbnail behavior) needed to meet
the entry-timing target while keeping the preview live.
