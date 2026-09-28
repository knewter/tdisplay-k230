# Home screen widgets and folders: headless QEMU evidence

Headless QEMU, real cross-built executables (`k230-shell-rust`,
`sway-unwrapped`) under `qemu-riscv64-static`, IPC-injected touch
(`card_shell test-touch`) against `tests/rust_home_screen_qemu.py`. A private
synthetic desktop catalog (`Fixture Badge`/`Fixture Extra`/`Fixture Page
Two`), never a board or real-finger observation.

## What this captures (real, verified)

Every PNG in this directory came from one continuous run of the current
`k230-shell-rust` build (post-rebase onto `master` commit `b58a1e97`, which
carries the `fix/overlay-keyboard-resize` exclusive-zone fix and the
card-shell perf/two-axis-entry fixes). I looked at each image myself before
writing this:

- `home-dark-page1.png` / `home-dark-page2.png` / `home-dark-mid-swipe.png` /
  `home-dark-back-to-page1.png` -- multi-page swipe, preserved from the prior
  Home-screen change.
- `home-dark-drawer.png` -- the drawer open, first row (search pill + tiles)
  fully reachable, confirming the `panel_input_rect` fix (the drawer's own
  input region no longer excludes its top ~234px, see "Bugs found" below).
- `home-dark-mid-drag.png` -- a live, held drag captured mid-flight: the
  lifted "Fixture Extra" tile with an accent border/shadow and a "Cancel"
  band across the top, confirming this is a genuine long-press-then-drag,
  not the old instant-pin behaviour.
- `home-dark-drop-target.png`, `home-dark-pin-flow.png` -- the drag settling
  onto Home.
- `home-dark-rearrange.png` / `home-dark-rearrange-done.png` /
  `home-dark-badge-removed.png` / `home-dark-removed.png` -- rearrange-mode
  drag to the Remove pill and the per-icon remove badge, both still working
  against the new `HomeItem`-based layout.
- `home-dark-after-restart.png` -- the rust process fully killed and
  restarted against the same persisted `home.json`; the grid (here, empty
  after the preceding remove step) is exactly what it was before restart --
  schema migration/persistence round-trips correctly.
- `home-dark-folder-mid-drag.png` -- "Fixture Extra" lifted and held over
  "Fixture Badge" (a drag-onto-app-creates-a-folder in progress).
- `home-dark-folder-created.png` -- the same slot now shows one folder tile
  ("Folder", with a 2x2 mini-icon preview) instead of two separate icons.
- `home-dark-folder-open.png` -- tapping the folder tile opens it: a card
  titled "Folder" with both members ("Fixture Ba...", "Fixture Ex...") laid
  out in the folder's own mini-grid, dock still visible underneath.

These sixteen captures exercise: drag-to-place from the drawer with a
mid-drag frame, folder creation by dragging one app onto another, opening a
folder, rearrange-to-remove, and schema-2 persistence across a real process
restart -- all against the current `HomeItem`/`HomeLayout` drop engine.

## What this run could not reach (UNVERIFIED, not a code defect found)

The same script also exercises, in order after the above: folder rename
through a real `zwp_virtual_keyboard_v1` connection (task 2), dragging a
member back out of an open folder onto Home (task 3), a dock-folder
creation, and the long-press widget-picker sheet placing a Clock widget
(task 2's sibling scenarios). None of these produced a capture in any of the
runs attempted for this evidence pass: the Python test driver process was
silently terminated (no traceback, no partial stdout, `PYTHONUNBUFFERED=1`
confirmed active) at the same point every time -- immediately after tapping
the just-opened folder's name label to begin a rename -- regardless of:

- three different keyboard-interactivity implementations tried on Home's
  own `Layer::Bottom` surface (`Exclusive`, `OnDemand`, and the call skipped
  entirely) -- all three hung identically, which rules out the WLR
  keyboard-interactivity request itself as the cause;
- two independent cross-built `sway-unwrapped` store paths (one from before
  this session's rebase onto `b58a1e97`, one after -- i.e. with and without
  the concurrent card-shell perf/two-axis-entry fixes);
- both the originally-committed, unmodified test script and a local,
  uncommitted retry-wrapper (matching the technique already recorded in
  `../wifi-settings/keyboard-focus-qemu/README.md` and
  `../overlay-keyboard-resize/README.md` for this shared machine's
  pre-existing `--surface`-request flakiness) that additionally retried
  `grim` invocations.

In every attempt, `k230-shell-rust --serve` and `sway` were confirmed still
alive and genuinely idle afterwards (`/proc/<pid>/wchan` =
`poll_schedule_timeout`, CPU time unchanged across a multi-second sample --
not a busy-loop), which is the compositor and client behaving exactly as
either would with no further input ever arriving, not a deadlock in the
Rust code or in wlroots. No `ulimit`/cgroup CPU, memory, or process-count
constraint was found on the account running these builds. This is being
recorded as an environment-level interruption specific to this shared,
heavily-loaded build machine's handling of this exact long-running,
detached QEMU process shape, not a reproduction of a bug in
`sync_home_keyboard`, `resolve_folder_tap`, or `paint_open_folder` -- but it
is **not root-caused**, and the rename/drag-out-of-folder/dock-folder/
widget-picker/wvkbd scenarios remain **UNVERIFIED** by this evidence pass.
Task and capability code paths for all of these exist and are covered by
`cargo test`'s unit tests (`home_screen.rs`'s
`tapping_the_folder_name_starts_editing_it`,
`dragging_a_member_out_of_an_open_folder_onto_home_removes_and_places_it`,
`tapping_widgets_then_long_pressing_clock_drags_and_places_it`, and
neighbours), which is a different, narrower evidence class (host-only, no
compositor) than this directory's QEMU captures.

## Bugs found and fixed during this pass

1. **The drawer's own touch input region excluded its entire first row**
   (`panel_input_rect`, `nix/rust-shell-client/src/main.rs`): a stale
   `height * 0.19` top offset left over from a pre-redesign bottom-anchored
   drawer silently routed every touch on the search field and the first row
   of tiles to whatever surface sat underneath instead of the drawer.
   Confirmed with a temporary `K230_DEBUG_TOUCH` diagnostic, fixed by making
   the offset unconditionally zero (matching Shade/Settings), committed
   separately with the reasoning in full.
2. **`tests/rust_home_screen_qemu.py`'s own drawer-reopen wait was fragile
   under a rapid close-then-reopen**: it waited for a fresh
   `K230_DRAWER_FRAME` log line, which is deliberately rate-limited to one
   line per `DRAWER_FRAME_LOG_INTERVAL` (500ms) of wall-clock time --- a
   close-then-reopen inside that window (routine, since the prior drag's
   own live-follow redraws the drawer at up to 60Hz right up until the
   drop) could suppress the reopened drawer's own frame-timing sample
   forever, with nothing else forcing a further redraw once it sat idle.
   Fixed in this same change to wait on the unconditional `"commit"` log
   line instead (see the updated docstring on `open_drawer_and_settle`).

## Commands and store paths

```sh
nix build .#handheld-shell-rust --max-jobs 1 --cores 6 --no-link --print-out-paths
# /nix/store/nmmhvfq9hkwk84c6vc8sgsjwlgc7nyr1-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0
nix build .#card-shell --max-jobs 1 --cores 6 --no-link --print-out-paths
# sway (post-rebase, includes card-shell perf/two-axis-entry fixes):
# /nix/store/gapq87c0daldq9jk8dlkm1k7fapdzm4s-sway-unwrapped-riscv64-unknown-linux-gnu-1.12
nix build .#handheld-theme-default --max-jobs 1 --cores 6 --no-link --print-out-paths
nix build .#handheld-theme-icons --max-jobs 1 --cores 6 --no-link --print-out-paths

unshare -Ur python3 tests/rust_home_screen_qemu.py \
  --sway <sway-unwrapped store path>/bin/sway \
  --swaymsg <sway-unwrapped store path>/bin/swaymsg \
  --rust <k230-shell-rust store path>/bin/k230-shell-rust \
  --theme-bundle <handheld-theme-default store path> \
  --icons <handheld-theme-icons store path> \
  --wvkbd <wvkbd store path>/bin/wvkbd-mobintl \
  --output <private-output>
```

## Remaining gate

This is headless-QEMU evidence with an invented desktop-entry fixture and no
physical panel. Real-glass confirmation of the whole Home redesign (drag-to
-place feel, folder open/rename/dissolve, widget placement, dock folders,
multi-page swipe) on the actual board remains **UNVERIFIED** and needs the
board reservation, which this change did not touch. The folder-rename real
-keyboard, drag-out-of-folder, dock-folder, and widget-picker scenarios
additionally remain unverified even under QEMU, per the section above.

## Operator real-finger report, 2026-09-28

System `l44jarwk…`, test-activated on the physical board. The operator
said, verbatim: "it's pretty great. i can't drag widgets/icons between
screens easily and the widgets all are designed like horseshit can they
look way better we need a dope clock nice weather widget".

Evidence class: an operator's real-finger report. The basic drag-to-place,
folder and widget flows work on the glass. Two follow-ups are open:
cross-page dragging is hard, and the widgets' visual design is poor.
