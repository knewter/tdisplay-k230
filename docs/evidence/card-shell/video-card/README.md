# Video windows are ordinary, closable cards

Headless-QEMU-injected-input evidence only; no physical touch, panel, or
mpv/decode proof. See `runtime/video`'s existing board evidence for actual
decode/presentation, and task 4.1 of
`openspec/changes/video-windows-become-ordinary-cards/tasks.md` for the
outstanding board re-check.

## Root cause

`k230-video-software`/`k230-video-mvx` (mpv, launched by
`nix/video-session.py`) were excluded from `card_shell ordinary` alongside
real transient/popup views (`nix/card-shell/adapter.c`'s "video and
transient views stay unmarked" check). A playing video therefore stayed a
small 480x270/568x320 floating window: no card, not in the overview, not
reachable by the bottom-edge switch gesture, and with no other close
control in this touch-only shell. Separately, `xdg_toplevel` close alone
cannot tell `video-session.py`'s controller "the user closed this" from
"the decoder died", so the MVX fallback path could relaunch a fresh
software player right after a close.

## Fix

- `nix/card-shell/adapter.c`: `video_app_id()` replaces the video-app_id
  exclusion in `cmd_card_shell`'s `ordinary` handler; only genuine
  transient/popup views (`wants_floating`) stay unmarked.
- `nix/shell.nix`: `k230-video-(software|mvx)` gets the same
  `card_shell ordinary, floating enable, resize set 100 ppt 100 ppt, move
  position 0 0` treatment as every other coherent-shell app. The old
  480x270/568x320 floating rule is kept only for the plain (non-coherent-
  shell) touch launcher, which has no deck to close a card from.
- `nix/card-shell/route.c`/`route.h`: `card_shell_video_stop()` spawns
  `$SWAY_K230_CARD_VIDEO_STOP stop` (wired to
  `${videoSession}/bin/k230-video-session`) alongside the existing
  `view_close()` whenever a closed card's `video_view` flag is set.
  `video-session.py`'s existing `stop` subcommand and process-group
  teardown are unchanged.
- `nix/card-shell/adapter.c`: `struct card.video_view` and
  `card_shown_large()` freeze a video card's deck-sized mirror on its most
  recently captured frame once it is not shown at full panel size, so a
  playing video does not pay continuous decode-to-thumbnail rescale cost
  for an unselected small card. <!-- UNVERIFIED in the shipped default
  configuration: this path is inside `scaled_mirror`, which is a no-op
  unless `SWAY_K230_CARD_SCALED_CACHE=1`; `nix/shell.nix` sets that env var
  to `"0"` by default (`docs/evidence/card-shell/scaled-cache-board/
  README.md` records why). The freeze is real and reachable whenever
  scaled-cache is enabled, but delivers no measured CPU-cost reduction in
  the default (scaled-cache off) configuration today. A dedicated small
  always-on cached buffer for video mirrors, independent of the general
  scaled-cache toggle, is a named follow-up. -->

## QEMU regression

`tests/test_card_shell_video_card.py` maps a real `k230.card.one` fixture
and the video app_id `k230-video-software` (both via
`card-composition-probe-client`, extended to accept the two video app_ids
alongside its existing `k230.card.one|two|three` fixture set) under real
cross-built Sway/`qemu-riscv64-static` with injected touch
(`SWAY_K230_CARD_TEST_INPUT=1`), and proves:

1. Both reach full `568x1232` ordinary-maximized geometry.
2. A real touch-first vertical entry swipe (`down`/`motion`/`motion`/`up`
   via `card_shell test-touch`) starting from the focused video card is
   accepted and settles into the overview (`mode==CS_DECK`), exactly as it
   would for any other source.
3. The video card is a genuine, switchable deck member: `card_shell
   previous`/`next` (the persistent-button route a lateral release
   resolves to) reaches the other card and back. The video app_id was
   mapped second in this run (deck index 1), so `previous` moves toward
   `k230.card.one` and `next` returns to the video card -- see the
   compositor log excerpt below.
4. `card_shell close` on the selected video card sends the ordinary
   `xdg_toplevel` close (the probe client exits with code 0, matching its
   default close-accept behavior) *and* invokes the video-stop helper
   exactly once with the argument `stop`.
5. The other ordinary card is unaffected (still running) and the deck
   still shows one card afterward.

Verify with (from `tests/`):

```
python3 -m unittest test_card_shell_video_card
```

7 consecutive passes were observed locally (`~8-11s` each). Two intermediate,
now-fixed bugs surfaced while developing this test, kept here because they
are real properties of the compositor, not artifacts of the test:

- A real frame must render between the entry gesture's `down` and its
  first `motion` so the adapter's per-frame geometry reconciliation
  (`cs_entry_set_geometry`, called from `card_shell_prepare`) sets a
  positive `entry_travel` before `cs_entry_motion` runs; otherwise it sees
  `entry_travel<=0` and immediately fails/reverts the gesture
  (`cs_entry_motion`, `nix/card-shell-policy/card-shell-policy.c`). Other
  suites (`tests/card_shell_runtime.py`) get this for free from a `grim`
  capture between `down` and `motion`; this test has no capture, so it
  sleeps for one frame instead.
- `card_shell previous`/`next` are a deliberate no-op while
  `mode==CS_ENTERING` (`cs_step`, same file), so a test must wait for the
  entry animation to actually settle to `CS_DECK` (debug-scene's `mode==1`)
  before stepping -- `selected_app_id` alone is not a sufficient gate,
  since `shell.policy.selected` is already correct and unchanged throughout
  the settle.

A new `debug-scene` field, `selected_app_id`, was added
(`nix/card-shell/adapter.c`'s `debug_scene_text`) so a test can read the
deck's own current selection directly; Sway's real seat focus does not move
while merely browsing the deck (`restore()` only reassigns it at
`CS_RESTORE`, i.e. when the overview is actually left), so polling the IPC
tree's `"focused"` node cannot observe `previous`/`next` stepping.

### Log excerpt (representative run)

```
K230_CARD_SHELL_DEBUG_SCENE active=1 ... mode=1 entry_progress=1.0000 ... selected_app_id=k230-video-software   # after entry: video selected
K230_CARD_SHELL_DEBUG_SCENE active=1 ... mode=1 entry_progress=1.0000 ... selected_app_id=k230-video-software   # after `next` (already last index: no-op)
K230_CARD_SHELL_DEBUG_SCENE active=1 ... mode=1 entry_progress=1.0000 ... selected_app_id=k230.card.one         # after `previous`
K230_CARD_SHELL close-request id=5
K230_CARD_SHELL mirror-release id=5 (x2)
K230_CARD_SHELL source-gone id=5
K230_CARD_SHELL unmap id=5
K230_CARD_SHELL_DEBUG_SCENE active=1 ... mode=1 ... ordinary_maximized_cards=1 ... selected_app_id=k230.card.one  # after close: video gone, one card remains
video.poll() = 0   # the probe client exited cleanly on the ordinary xdg_toplevel close
```

(Full unittest run's assertions additionally confirm the video-stop helper
log contains exactly one line, `stop`, and that the other card's process
is still running (`poll() is None`) throughout.)

## Narrow proof commands

- `nix build .#card-shell --max-jobs 1 --cores 6`
- `nix build .#handheld-shell-rust --max-jobs 1 --cores 6`
- `nix eval .#nixosConfigurations.k230.config.system.build.toplevel.drvPath`
- `python3 -m unittest test_card_shell_video_card` (from `tests/`)
- `python3 -m unittest test_card_shell_state` (from `tests/`, unaffected:
  29/29 pass)
- `openspec validate video-windows-become-ordinary-cards --strict`

## Limits

- No board evidence. QEMU cannot prove mpv decode, MVX hardware fallback
  behavior, actual panel presentation, or physical close-gesture feel --
  those stay with `runtime/video`'s existing board evidence and the
  outstanding board re-check (task 4.1 in this change's `tasks.md`).
- `tests/test_card_shell_home_bleed.py` (a pre-existing, unrelated two-axis
  suite) was observed failing both with and without this change's diff
  applied on this host (confirmed via `git stash`), so it is a pre-existing
  environment-sensitive flake, not a regression introduced here; it was not
  otherwise investigated or fixed as part of this change.
