# Board checklist: remaining theme-work gates

2026-09-28 closeout audit. Every item below is a task that is otherwise done
(code lands, host tests pass) and is blocked only on the reserved board or an
operator's real finger. See `docs/closeout/themes-audit.md` for the full
classification and citations; this file is the operator/coordinator runbook.

**Board and serial-port protocol** (per `AGENTS.md`/SKILL.md): the board and
`/dev/ttyACM0` belong to one operator at a time. State which item below you
are running before you take the board, and release it explicitly after.
Coordinator commands go through
`flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=N '<cmd>'`.
Native screenshots come from the shell user's own session:
`SWAYSOCK=/run/shell/sway-ipc.sock WAYLAND_DISPLAY=wayland-1 XDG_RUNTIME_DIR=/run/shell grim <path>.png`.
Do not infer a hardware result from a host or QEMU check.

**Disclosure:** no item below was run by this audit. `tools/console.py`
was invoked once, by mistake, while reading its source to write this
checklist (`python3 tools/console.py --help`, which the script has no
`--help` handling for and instead opened `/dev/ttyACM0` and sent the
literal string `--help` as a command, outside `flock` coordination). The
board returned a harmless "command not found" from a live `root@nixos:`
shell. No other board interaction occurred during this audit; treat the
lock and the board's current state as if held by someone else until
confirmed otherwise.

---

## `the-shell-swaps-themes-without-a-python-stall`

### Task 2.3 — jank capture before/after `theme-helper.service`

1. Confirm the target system is installed with this change's current
   `theme-helper.service`; record its store path.
2. Coordinator, board:
   `flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=20 'k230-theme-swap-jank --theme catppuccin && k230-theme-swap-jank --theme catppuccin-latte && k230-theme-swap-jank --theme <a still-background community theme>'`
   (or the direct `tools/theme-swap-jank.py` invocation named in the task,
   run as the shell user with `journalctl -o json` access).
3. Coordinator: `flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=10 'journalctl -u theme-helper --no-pager -n 200'`.
4. Run `tools/analyze-theme-swap-jank.py` against the captured journal for
   each swap.
5. **Pass**: a before report (pre-`theme-helper.service`, if not already
   captured historically) and an after report, both showing frame-interval
   histograms, gaps over 33/50/100ms with context, and tap-to-visible
   latency against the ~100ms target named in task group 4.
6. Commit both reports plus the exact commands to
   `docs/evidence/omarchy-themes/theme-swap-jank/README.md` (a stub already
   exists there — extend it, do not overwrite).

### Task 3.4 — re-run tap-to-visible metric

Same board session as 2.3 is fine if convenient. Run
`tools/analyze-theme-swap-jank.py`'s tap-to-visible metric against the
current build (3.1b/3.2/3.3a landed; 3.3b still open, so report the number
as-is rather than waiting on 3.3b). **Pass**: a recorded number against the
~100ms target, whatever it is — a number short of target with 3.3b named as
the likely remaining cost is a valid, honest result, not a failure to
report.

### Task 6.6 — confirm Apply skips the redundant re-prepare

1. Coordinator: `flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=15 'journalctl -u theme-helper --no-pager -n 100 | grep -E "activate_generation|warm="'`
2. In the shell session, warm-up a theme by dwelling on it in the chooser,
   then tap Apply.
3. **Pass**: `activate_generation` log shows the warm receiver(s) skipped
   (a `warm=2`-shaped line, or the absence of a second
   `appearance-prepare-accepted` between warm-up and Apply), and
   `parse`/`prepare_entry` are near their cache-hit floor (task 6's own
   ~250-270ms internal-daemon floor from the 5.4 board run).
4. Also confirm the cold-open case from 6.5: the *second* previewed theme is
   already warm from the neighbour queue, not a fresh ~4s `preview`.
5. Commit to `docs/evidence/omarchy-themes/instant-theme-swap/board-checkpoint-6.6.md`.

### Task 10.7 — one-page tap-to-apply on the actual panel

1. Coordinator: install the current build; confirm services active.
2. Operator, board: open the chooser, browse to a bundled dark theme, tap
   to apply; repeat for a bundled light theme.
3. `SWAYSOCK=/run/shell/sway-ipc.sock WAYLAND_DISPLAY=wayland-1 XDG_RUNTIME_DIR=/run/shell grim theme-dark.png` and `...grim theme-light.png` after each.
4. Coordinator: `flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=10 'journalctl --no-pager -n 50 | grep "optimistic-apply stage"'`.
5. **Pass**: both themes read correctly on the panel (no clipping at
   `THEME_CAROUSEL_TOP=132.0`/`BACKGROUND_CAROUSEL_TOP=872.0`, both rows fit
   the 1232px panel); `optimistic-apply stage adopt_ms=.../wallpaper_ms=.../overlay_ms=.../flush_ms=...` recorded for a warm tap; total moved toward
   ~30ms from the 161ms baseline, or the `reason=` field names why not.
6. Commit screenshots + journal excerpt to
   `docs/evidence/theme-picker/one-page-panel-fit/README.md`.

### Task 11.3 — swipe-cost/memory comparison

1. Coordinator: confirm the installed Rust store path and catalog/background
   counts (`k230-theme list` or equivalent).
2. Operator: swipe across several themes and back without applying, using
   the verified virtual touch device or real finger (name which); then hold
   15 seconds idle.
3. Coordinator: `flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=20 'journalctl --no-pager -n 300'` for the touch/frame timeline, plus a CPU/RSS sample via the existing `theme-swap-jank` capture extended for this gesture sequence (task's own suggestion).
4. **Pass**: active generation unchanged throughout; repeated thumbnail
   loading settles (does not re-request); warm swipes improve versus the
   pre-fix baseline without a memory increase over the idle window.
5. Commit before checking the task box, per the task's own text.

### Task 13.4 — blocked on 13.1-13.3

Do not schedule board time for this until `tools/theme-picker-profile.py`
(13.1), its cost attribution (13.2), and the motion-gating fix identified in
`theme_ui.rs::poll_prepare_ahead` (13.3) have landed and passed their own
host proof. Once they have, this is a >=3-matched-pair alternating-order
board comparison; see the task's own text for the exact operator interface
(`python3 /run/theme-picker-profile.py capture --plan ... --output ...`).

### Task 14.4 — operator real-finger acceptance

1. Install the qualified finger-tracking build (already installed per
   14.3's own evidence; confirm it is still current).
2. **Operator, using an actual finger, not injected input**: drag both the
   theme row and the background row; reverse direction mid-drag; stop and
   hold, then release, on each row.
3. **Pass**: both rows visibly track the finger without exaggerated travel,
   and neither row shows a backlog (continued movement) after the finger
   lifts.
4. Record a short native video or a coordinator's own observation note (no
   special capture tooling required — this is a qualitative acceptance
   gate) to `docs/evidence/theme-picker/finger-tracking/real-finger-acceptance.md`.
   This does **not** by itself close 11.3/13.4's own performance gates.

### Task 15.2/15.3 — compositor-stage profiling and a second interaction

1. Coordinator: `nix build .#runtime-perf --cores 8` (already passed once;
   confirm still current).
2. Board: re-run the existing CPU-clock capture
   (`docs/evidence/theme-picker/cpu-profile/README.md`'s own command) with
   compositor render/commit/present spans instrumented per 15.2's own ask,
   and with matching symbols so the 648/697 unknown-caller samples resolve.
3. Run the same tracing tool against **one other interaction** beyond the
   theme picker (task 15.3's own requirement — pick whichever other gesture
   this project is currently proving, e.g. app-switch swipe).
4. **Pass**: a reviewed timeline, frame-stall report and supported
   flamegraphs with runtime identities, commands, and named coverage gaps
   for both interactions.
5. Commit to `docs/evidence/theme-picker/runtime-trace/README.md` (extend)
   and `docs/evidence/theme-picker/cpu-profile/README.md` (extend).

---

## `the-shell-loads-omarchy-themes`

### Task 5.3b — real-finger chooser/gesture video, cancel behavior

1. Operator, board, **real finger**: open the chooser; browse the theme
   carousel by real swipe; tap to apply a bundled dark theme, then a
   bundled light theme, then the unchanged community theme already proved
   in 5.3a; specifically exercise whatever cancel-equivalent exists today
   (per the sibling change's task 10 redesign, there is no longer a
   separate Apply/Cancel step — confirm what "cancel" means now, e.g.
   swiping away before dwell-driven prepare-ahead completes, and record
   that finding).
2. Record on video (phone camera or equivalent) the finger actually
   touching the glass, framed to also show the panel.
3. `SWAYSOCK=/run/shell/sway-ipc.sock WAYLAND_DISPLAY=wayland-1 XDG_RUNTIME_DIR=/run/shell grim` a still for each of the three themes.
4. **Pass**: video shows a real finger driving the carousel and applying
   all three theme classes; stills confirm the applied result matches.
5. Commit video + stills to
   `docs/evidence/omarchy-themes/board-switching/real-finger-2026-MM-DD.md`
   (new file; do not overwrite the existing injected-input README).

### Task 5.4 — `--workload backgrounds` on the actual board

1. Coordinator: confirm `tools/handheld-theme-trial.py --workload backgrounds`
   is available on the installed image (host tests already pass; this is
   the first board run).
2. Coordinator: `flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=30 'python3 /run/shell/theme-trial-tools/handheld-theme-trial.py --candidate-manifest /run/shell/theme-candidate.json --output /run/shell/theme-evidence-bg --workload backgrounds'`
   (paths follow the same pattern as the committed
   `docs/evidence/omarchy-themes/board-switching/README.md` invocation).
3. **Pass for the static arm**: combined CPU, RSS, decode/presentation and
   card input/frame budgets recorded; covered-media pause and restoration
   observed.
4. **Video arm stays blocked** until task 4.3 (video background decode)
   lands in code — do not attempt it before that, and do not relabel a
   fallback-only result as playback.
5. Commit to `docs/evidence/omarchy-themes/background-workload-board/README.md`.

### Task 5.5 — `--workload reboot`

Not board-ready yet: `tools/handheld-theme-trial.py` has no `--workload
reboot` mode. Write and host-test it first (host-doable, not a board task);
only then schedule board time for a normal reboot with console plus panel
observation of remembered theme/wallpaper, fresh-home default and
unavailable-source recovery.

---

## Evidence already satisfied — no board time needed

- `the-shell-swaps-themes-without-a-python-stall` task group 16 (background
  selection generation and feedback): fully done, evidence already on
  `master` at `docs/evidence/theme-picker/background-selection/README.md`.
- `the-shell-loads-omarchy-themes` task 5.3a (board activation of a dark,
  light and unchanged community theme): already done —
  `docs/evidence/omarchy-themes/board-switching/README.md` and
  `docs/evidence/omarchy-themes/community-board-fixed/README.md`.

Do not re-run these; they are cited, reviewed, and already committed.
