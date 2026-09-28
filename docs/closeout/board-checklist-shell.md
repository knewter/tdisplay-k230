# Board / real-finger checklist for the near-done shell changes

Everything below is the complete remaining-open-task list across the seven
changes closed out on branch `close/near-done-shell`
(`video-windows-become-ordinary-cards` needed none of this -- it archived
clean). One change (`the-shell-has-a-card-composition-plan`) needs an
opt-in, shell-stopping session; everything else runs against the normal
installed shell. Reserve the board and `/dev/ttyACM0` for one operator for
the whole sitting (`AGENTS.md`); run `python3 tools/work-status.py` first.

Common setup, once, for every "normal shell" item below:

```sh
./tools/console.py /dev/ttyACM0 --wait=3 "systemctl is-active shell seatd"
```

Grim template used throughout (adjust the file name):

```sh
runuser -u shell -- env SWAYSOCK=/run/shell/sway-ipc.sock \
  WAYLAND_DISPLAY=wayland-1 XDG_RUNTIME_DIR=/run/shell \
  grim /run/shell/<name>.png
```

Pull captures back with `tools/console.py` cat + local decode, or
`tools/push-file.py`'s sibling pull path if one exists, or the existing
camera capture tool (`tools/capture-feature.py`) for anything a native
`grim` cannot show (finger occlusion, panel readability, camera-only
provenance).

---

## Session 1 -- normal installed shell (single reservation)

Do these in this order; they share one running system and one camera
setup. All are **real-finger** unless noted.

### 1. Overview no longer bleeds Home through (`the-overview-hides-the-home-screen`, task 5.1)

Change file: `openspec/changes/the-overview-hides-the-home-screen/tasks.md`

Steps:
1. Set the board's actual theme and wallpaper as normally configured (not
   a synthetic fixture).
2. Focus a real app, then:
   ```sh
   ./tools/console.py /dev/ttyACM0 --wait=3 "swaymsg card_shell enter"
   ```
3. Grim-capture the overview, and take a camera photograph of the panel
   during and just after entry (the QEMU regression already covers the
   synthetic-fixture case; this is about the real, themed canvas).

Pass: no green/placeholder Home content visible behind or around the deck
cards, in the photograph or the native capture, during entry, mid-drag,
and once settled.

Evidence file: `docs/evidence/card-shell/overview-home-bleed-through/README.md`
(append a "board re-check" section with the new capture and photo).

### 2. Home screen real-finger acceptance (`the-shell-presents-a-pinned-home-screen`, task 8.1)

Change file: `openspec/changes/the-shell-presents-a-pinned-home-screen/tasks.md`

Steps: with a real finger, in both a dark and a light installed theme:
page Home left/right, long-press an app in the drawer to pin it to Home,
long-press an icon on Home to rearrange it (and remove one via the
rearrange-mode target), tap a dock icon, and tap an already-running app's
icon (confirms focus-vs-relaunch). Camera-record each theme pass.

```sh
python3 tools/capture-feature.py home-screen --provenance real-touch \
  --duration 30 --description 'Real-finger Home page swipe, pin, rearrange, dock, launch-or-focus' \
  --output-dir docs/evidence/home-screen/real-touch
```
(run once per theme; rename or re-run with a distinct `--description` for
the second pass)

Pass: pages swipe with the finger, pin/rearrange/remove all take effect
and persist, dock taps launch, and tapping a running app's icon focuses it
instead of relaunching -- in both themes.

Evidence file: `docs/evidence/home-screen/real-touch/` (created by the
tool above).

### 3. Launch splash, three remaining states (`launching-an-app-shows-a-splash`, tasks 6.1-6.3)

Change file: `openspec/changes/launching-an-app-shows-a-splash/tasks.md`.
Operator already reported "launch splash seems fine" informally
(`docs/evidence/operator-reports/2026-09-27-shell-acceptance.md`); this
converts that into the required native capture.

**6.1 -- normal launch, no flash of the prior app.** Real-finger tap an
app from the drawer, from Home, and from the dock. Capture:
```sh
python3 tools/capture-feature.py launch-splash --provenance real-touch \
  --output-dir docs/evidence/launch-splash/real-touch --description 'drawer/Home/dock tap to splash, no prior-app flash'
```
Pass: the splash appears within one visible frame of the tap in all three
launch surfaces, with no glimpse of whatever app was previously on screen.

**6.2 -- `Terminal=true` app_id mismatch hand-off.** Real-finger tap the
Terminal entry. While it launches:
```sh
./tools/console.py /dev/ttyACM0 --wait=3 "SWAYSOCK=/run/shell/sway-ipc.sock swaymsg -t get_tree"
```
Pass: the splash shows, then hands off to a focused `foot` window (not the
splash's own launched-entry app_id) -- confirm via the tree dump's focused
node, plus a native capture around the hand-off moment.

**6.3 -- `TimedOut` and `Failed` states, real-finger dismiss.** Stage two
temporary desktop entries as user `shell` (remove both when done):
```sh
# TimedOut: SPLASH_TIMEOUT is 10s (nix/rust-shell-client/src/splash.rs) --
# a command that never maps a window reaches it.
cat > /home/shell/.local/share/applications/k230-splash-test-timeout.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=Splash Test Timeout
Exec=sleep 20
EOF
# Failed: a command that exits immediately without mapping anything.
cat > /home/shell/.local/share/applications/k230-splash-test-failed.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=Splash Test Failed
Exec=/bin/false
EOF
```
Launch "Splash Test Timeout" from the drawer with a real finger; wait past
10s for `TimedOut`, then dismiss it with a real-finger tap; capture
before/during-wait/after-dismiss. Separately launch "Splash Test Failed";
confirm it reaches `Failed` and auto-dismisses around 1.6s later without
being tapped. Grab the Rust client's own log for the `SplashStatus`
transitions alongside the capture:
```sh
./tools/console.py /dev/ttyACM0 --wait=3 "journalctl --user -u k230-shell-rust -n 100 --no-pager"
```
(or wherever this system's shell-client log actually lands -- confirm the
unit/journal name with `systemctl --user status` first if unsure).
Remove the two fixture entries afterward.

Pass: `TimedOut` is reached at ~10s and a real-finger tap dismisses it;
`Failed` is reached quickly and auto-dismisses on its own within about
1.6s without input.

Evidence file: `docs/evidence/launch-splash/real-touch/` for all three
sub-tasks (one manifest per capture is fine).

### 4. Brightness slider real-finger acceptance (`the-brightness-control-is-a-slider`, tasks 6.1-6.3)

Change file: `openspec/changes/the-brightness-control-is-a-slider/tasks.md`

**6.1 -- Settings slider.** Open Settings, drag the brightness slider with
a real finger across its full range, and tap-to-jump partway. Confirm the
panel's actual brightness visibly follows the finger live, and that
dragging to the very bottom clamps at 3% (never a fully dark/off panel at
0%).

**6.2 -- Shade slider, gesture disambiguation.** Open the Shade, drag its
own brightness slider horizontally -- confirm the Shade does NOT begin
closing during that drag. Then start a drag on a different part of the
Shade (not the slider band) and confirm it still closes normally.

**6.3 -- Cross-sheet sync.** Set brightness via the Shade's slider, close
it, open Settings, and confirm it shows the same value (not stale). Then
reverse: set via Settings, open the Shade, confirm it matches.

Capture each with:
```sh
python3 tools/capture-feature.py brightness-slider --provenance real-touch \
  --duration 20 --description '<settings-drag | shade-drag-no-close | cross-sheet-sync>' \
  --output-dir docs/evidence/brightness-slider/real-touch
```

Pass: live tracking, 3% floor (not 0%), Shade slider drag never triggers
close-drag, a drag starting elsewhere on the Shade still closes it, and
both sheets agree on the current value after an external change.

Evidence file: `docs/evidence/brightness-slider/real-touch/`.

### 5. Video-card cost, remaining timing + real-finger piece (`the-card-shell-has-no-video-special-case`, task 5.1 remainder)

Change file: `openspec/changes/the-card-shell-has-no-video-special-case/tasks.md`.
Most of this task is **already done** --
`docs/evidence/card-shell/live-card-cost/README.md` (2026-09-26, injected
touch + IPC) already covers flick/switch/close and mpv's clean exit with
no relaunch. What's left is narrow:

Steps: start a video playing and, separately, a busy non-video app
(`btop` in `foot`) in the deck. With a **real finger**, enter the
overview and time it (stopwatch or camera timestamp overlay), then tap a
card and time the ack. Repeat for both cards.

```sh
python3 tools/capture-feature.py live-card-cost --provenance real-touch \
  --duration 20 --description 'real-finger overview entry + touch-ack timing, video and btop cards' \
  --output-dir docs/evidence/card-shell/live-card-cost
```

Pass: overview entry completes in well under ~400ms and a touch is acted
on within ~100ms, for both the video card and the busy non-video card,
as timed from real-finger input (the existing injected-touch measurement
was inconclusive because the injection tool's own per-step process-spawn
overhead dominated the numbers -- see that README's "Entry-animation
timing" section).

Evidence file: append this real-finger timing pass to
`docs/evidence/card-shell/live-card-cost/README.md`.

---

## Session 2 -- opt-in card-composition-probe session (stops normal shell)

### 6. Continuous real-finger card drag (`the-shell-has-a-card-composition-plan`, task 3.2)

Change file: `openspec/changes/the-shell-has-a-card-composition-plan/tasks.md`.
Extensive **injected**-touch/IPC board evidence already exists
(`docs/evidence/card-composition-board/README.md`); what remains is
specifically **continuous real-finger tracking**, which native captures
and injected events cannot establish.

This stops the normal `shell` service for the duration and restores it
afterward -- reserve the board explicitly for this, separately from
Session 1 (do not run it while anything above still needs the normal
shell).

```sh
probe_path=$(nix build --no-link --print-out-paths .#card-composition-probe)
tools/card-composition-board-session.sh --probe "$probe_path/bin/card-composition-probe" --restore-shell
```

While the session is active (real finger on the glass): two app surfaces
visible, shrink into the probe's small-card view, a continuous drag
(not a tap or injected event) moving one card, an adjacent
select/expand, and both a refused-close and an accepted close/exit.

```sh
tools/card-composition-board-session.sh --collect
tools/card-composition-board-session.sh --verify-restored
```

Pass: `--collect` writes sanitized evidence naming renderer, format,
buffer lifetime, damage/commit and frame/presentation signals, process
CPU and memory, with the drag visibly continuous (not stepped) under a
real finger; `--verify-restored` confirms normal `shell`/`seatd` and Apps/
keyboard/Terminal all work again afterward.

Evidence file: `docs/evidence/card-composition-board/README.md` (append a
"continuous real-finger drag" section citing the new collection), or a
new `docs/evidence/card-composition-board/real-finger/` if the existing
file is easier to leave intact.

---

## After this checklist

Once each item above lands with its evidence file committed, tick the
corresponding task in that change's `tasks.md` citing the new file, then
re-run for that change:

```sh
openspec validate <change> --strict
```

When every task in a change is checked, archive it:

```sh
openspec archive <change> --yes
openspec validate --all --strict
python3 scripts/render_work_board.py > /dev/null
```
