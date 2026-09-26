# No video special-casing; generic live-card cost model (board check)

Evidence class: board webcam recording, plus the compositor's own
`card_shell` debug/step/close IPC (`swaymsg card_shell
enter|previous|next|close|debug-scene`) for the busy non-video workload
and the final video close, alongside genuine injected touch (evdev, via
`evemu-device`/`tools/inject-tap.sh`, pushed to `/run/k230-inject-tap.sh`)
for the video-card open. Not a real finger. Captured 2026-09-26.

System: `plmk2mvm7j76kvd35acj5888sc847lja-nixos-system-nixos-26.11.20260919.20b1ddd`
(`integrate/apps-video-catalog` at `dcc0692b`), test-activated over
`28qilnk3zqlivjgij78ahqnjvnjz8j5y-...`. Rollback timer disarmed after
activation; `readlink -f /run/current-system` confirms the board is
running it, with no video or btop playing and no failed units.

## What changed (see the commit for the full list)

- Removed `struct card.video_view`, `video_app_id()`, and every app_id
  check from `nix/card-shell/adapter.c`. Card eligibility now depends
  only on whether a view is a real transient (an xdg_toplevel with a
  parent); closing any card sends only the ordinary xdg_toplevel close.
- Removed `card_shell_video_stop()`/`SWAY_K230_CARD_VIDEO_STOP`
  entirely; folded `nix/shell.nix`'s separate video `for_window` rule
  into one generic `[app_id=".+"]` rule.
- Generalized the previously opt-in, video-only-frozen
  `SWAY_K230_CARD_SCALED_CACHE` downscaled-mirror path to every card and
  made it the shipped default: refreshes on every commit (never frozen),
  caps a not-shown-large card to ~15fps of recomposition, uses a cheap
  nearest filter while the scene is animating/dragging and bilinear at
  rest.
- `nix/video-session.py`: tracks whether mpv ever printed a first-frame
  status line: MVX only falls back to software before a frame was shown;
  a closed window (or any other post-first-frame exit) never relaunches.

## Board verification

### Video workload

`/run/k230-vo.sh` (video launched the way the drawer does, bottom-edge
swipe-up via injected touch, a tap, a flick, a second tap) produced
**zero** `reason=...` failure/defer lines and **zero**
`CS_MESSAGE_FAILED` restores in the journal (`journalctl -u shell`,
`05:36:03`-`05:36:23`). The tap-to-switch-away sequence completed and
`restored focus=5 message=0` (success). Closing the video card
afterward (`swaymsg card_shell close` with the video card selected):

```
V: 00:05:18 / 00:10:34 (50%) Dropped: 145 Cache: 316s/27MB
Exiting... (Quit)
```

`pgrep -x mpv` empty immediately after and stayed empty; the
`k230-inject-video` unit exited on its own (no relaunch, no fallback
software player spawned).

### Busy non-video workload (btop in foot)

Launched `foot -a k230-busytest -- btop` via `swaymsg exec`; it became
`ordinary_maximized_cards=3` (the existing terminal, video, and btop) with
no code change needed for a new, previously-unseen app_id -- the whole
point of removing the app_id check. `swaymsg card_shell enter` with the
btop card focused opened the overview cleanly (`mode=1
selected_app_id=k230-busytest`), again with zero failure/defer/restore
lines. `swaymsg card_shell previous`/`next` switched selection to the
other card and back. `swaymsg card_shell close` with the btop card
selected: `pgrep -x btop` empty immediately after -- no special code
path was needed, since there never was one for a non-video app to
begin with.

Contact sheet (`contact-sheet.png`, left to right): video playing
full-screen live; overview open with the video's own live thumbnail
(matching frame content, not frozen); the btop card in the overview
showing its actual live terminal content (the green/blue CPU/memory bar
visible at the bottom, not a placeholder); the overview after closing
btop with the video and terminal cards remaining.

### Entry-animation timing: not measurable with the available injection tool

The coordinator's target (entry completes in under ~400ms, a touch acted
on within ~100ms) could not be confirmed or refuted by timing
`tools/inject-tap.sh`'s synthetic drag on this board. Isolated
measurement: running the exact same 20-step drag helper with **no**
overview or card-shell interaction at all (a plain swipe over the idle
desktop) took **3.3 seconds** wall-clock just to generate the touch
events (`date` before/after the script, no compositor logic involved).
The compositor's own `state mode=...` log timestamps track this same
per-step cadence essentially 1:1 (each logged step lands within a few ms
of when the script's corresponding `evemu-event` call actually ran), for
every build tested across this whole investigation -- before and after
every adapter.c change made in this session, including the scaled-cache
generalization. This means the wall-clock "entry takes ~4 seconds"
number measured throughout this investigation was dominated by
`inject-tap.sh`'s own per-step process-spawn overhead (multiple
`evemu-event` invocations per motion sample), not by the compositor
falling behind: the compositor is processing each sample essentially as
fast as the script produces it. A **discrete** tap (down+up, no
intermediate motion samples) completed end-to-end in well under a
second in every observed run (e.g. the video tap-to-switch above:
`state mode=2` at compositor uptime `01:20.513` to `restored focus=5` at
`01:21.067`, ~550ms including the full expand animation's own dwell).

<!-- UNVERIFIED: the sub-400ms entry-animation and sub-100ms touch-ack
targets, specifically. Confirming them needs either a real finger (native
touch-controller sampling, not gated by shell-script process-spawn
overhead) or an injection tool that holds the uinput device open and
writes events without re-executing `evemu-event` per sample. Neither was
available in this pass. -->

## Not established

A real-finger check by the user on the glass, and the specific
entry/touch timing targets (see above). Everything above is injected
touch, the compositor's own deterministic step/debug/close IPC, or a
board-observed process exit; no physical finger touched the panel for
this change.
