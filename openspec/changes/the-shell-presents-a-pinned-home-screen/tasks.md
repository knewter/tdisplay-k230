## 1. Reconciliation and scope

- [x] 1.1 Read the sibling `the-handheld-presents-a-coherent-shell` and
  `the-shell-manages-apps-as-cards` proposals/designs and record the exact
  decision superseded and the exact gestures kept unchanged; verify with
  `openspec validate the-shell-presents-a-pinned-home-screen --strict`.

## 2. Pager, grid, and dock physics (host-testable, no hardware)

- [x] 2.1 Implement `nix/rust-shell-client/src/home_pager.rs`: whole-page 1:1
  drag, momentum decay, ease-out settle, page/dot math, mirroring
  `theme_carousel.rs`'s and `navigation.rs`'s existing conventions and unit
  test shapes; verify with `cargo test --offline -p k230-shell-rust
  home_pager`. Done: 8 unit tests.
- [x] 2.2 Implement `nix/rust-shell-client/src/home_grid.rs`: page/dock slot
  geometry and hit-testing (tap vs. drag vs. long-press timing, page-size
  slots, dock slot count) as pure, host-testable functions; verify with
  `cargo test --offline -p k230-shell-rust home_grid`. Done: 6 unit tests.

## 3. Persistence

- [x] 3.1 Implement `nix/rust-shell-client/src/home_state.rs`: the
  `$XDG_STATE_HOME/k230-shell/home.json` (falling back to
  `$HOME/.local/state/k230-shell/home.json`) versioned layout file, atomic
  write, missing-entry-preserves-slot load behavior, and default-seed
  selection from `catalog::installed_apps()`; verify with `cargo test
  --offline -p k230-shell-rust home_state`. Done: 12 unit tests.

## 4. Rendering and shell wiring

- [x] 4.1 Add `Route`-adjacent Home surface state to `main.rs` (a new
  always-mapped `Layer::Bottom` layer-shell surface, its own buffer pool
  usage, frame/configure callbacks, and touch dispatch keyed on that
  surface, mirroring the existing `WallpaperState` pattern) and a
  `paint_home` renderer in `render.rs` that composites pinned icons and the
  dock, alpha-transparent elsewhere so the existing wallpaper layer shows
  through; verify with `cargo test --offline -p k230-shell-rust` (existing
  suite stays green) and `cargo build --offline -p k230-shell-rust`. Done:
  175 tests pass (139 lib/bin + 36 across the existing integration
  suites), full binary builds clean.
- [x] 4.2 Wire long-press-to-pin in the drawer and long-press-to-rearrange on
  Home, including the rearrange mode's Done/Remove-target affordances;
  verify with the new host tests in 2.2/3.1/home_screen.rs plus the QEMU
  harness in 6.3, which exercises the real long-press-pin and drag-to-
  remove flow end to end. (The originally sketched "Add to Home"
  confirmation dialog and its `--render-fixture home` verification were
  dropped in favor of a direct pin on long-press, matching both reference
  launchers' grab-then-place gesture -- see design.md decision 5's revised
  text and `home_state::HomeLayout::pin`'s no-op-if-already-pinned
  semantics; `--render-fixture` still only covers `drawer|shade|settings`,
  since Home is not a `Route` value.)
- [x] 4.3 Implement `home_screen::focus_or_launch`'s best-effort
  desktop-entry-id-to-running-`app_id` match (off the Wayland dispatch
  thread, on the existing launch worker), falling back to
  `launch_selected` unchanged on no match; verify with `cargo test --offline
  -p k230-shell-rust home_screen` covering the id-normalization and
  fallback logic against a synthetic `get_tree` fixture. Done: 4 unit
  tests (`app_id_matches`/`find_running_con_id`); the QEMU harness proves
  the not-yet-running launch path end to end, not the focus-an-existing-
  window path (no fixture client with a matching `app_id` was spawned in
  this pass -- see `docs/evidence/home-screen/qemu/README.md`).

## 5. Minimal compositor hook

- [x] 5.1 Change `nix/card-shell/adapter.c`'s `rebuild_chrome` title from
  `"Home"` to `"Overview"`, and add `"home"` to `nix/card-shell/route.c`'s
  `card_shell_launch_surface` allow-list; verify with `nix build --no-link
  --print-out-paths --max-jobs 1 --cores 6 .#card-shell`. Done: builds;
  `strings` on the resulting `sway-unwrapped` binary confirms "Overview"
  and the "home" allow-list entry are present.

## 6. Build and QEMU proof

- [x] 6.1 Build the updated Rust client and card-shell derivations; verify
  with `nix build --no-link --print-out-paths --max-jobs 1 --cores 6
  .#handheld-shell-rust .#card-shell`. Done:
  `/nix/store/4vwq285cbg1w0s4is25s76gq6nk49abf-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`
  and `/nix/store/3gk7wpcrj11hpivfsq4ph9qzyxf55pwg-k230-card-shell`.
- [x] 6.2 Confirm the coherent-shell system closure still evaluates with
  these changes; verify with `nix eval
  .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel.drvPath`.
  Done: evaluates to
  `/nix/store/gxvv2vy1g23m86qlhvs4d60aqr2fvpj2-nixos-system-nixos-26.11.20260919.20b1ddd.drv`.
- [x] 6.3 Add a paired Sway/Rust QEMU injected-touch test in the style of
  `tests/rust_theme_chooser_qemu.py`: boot the cross-built `sway` (from
  `nix-store -qR <card-shell store path>`) and the cross-built Rust client
  under `qemu-riscv64-static` with a synthetic desktop-entry/icon fixture,
  inject touch to swipe Home's pages, tap the dock, long-press to pin from
  the drawer and to rearrange on Home, and screenshot each step; verify
  with `python3 tests/rust_home_screen_qemu.py --sway <sway> --swaymsg
  <swaymsg> --rust <rust> --theme-bundle <theme-bundle> --icons <icons> --client <native-probe-client>
  --output <dir>`.
  Passed all 24 checks with the exact candidate compositor/Rust executables;
  see `docs/evidence/home-screen/navigation/qemu-result.json`. Done: PASS, all twelve checks true; see
  `docs/evidence/home-screen/qemu/`. (User-mode `qemu-riscv64-static`
  headless Pixman, not `qemu-system-riscv64`'s `k230` machine -- this
  repo's existing Rust-client QEMU tests all use the same user-mode
  approach, since the compositor/client pairing needs no board devices,
  and it is what `tests/rust_theme_chooser_qemu.py` itself actually uses
  despite this task's original text.) This is QEMU proof of wiring/layout,
  not of the physical panel, touch controller, or real-glass feel.

## 7. Evidence and repo hygiene

- [x] 7.1 Capture Home on page 1 and page 2, mid-swipe, and the pin flow, in
  both a dark and a light installed theme, from the QEMU harness in 6.3;
  commit under `docs/evidence/home-screen/qemu/`. Done, plus a rearrange/
  remove/restart-persistence sequence and an additional "showcase" pass
  (a fully-populated, colorfully-iconed fresh Home) for visual review.
  These are QEMU/synthetic captures, not board photographs; the
  physical-panel, real-finger, and daylight-readability gates remain open
  for the coordinator (see task 8.1).
- [x] 7.2 Keep the blob scan passing; verify with `python3
  tools/blob-scan.py` and check its exit code directly. Done: exit 0.
- [x] 7.3 Rebase onto the latest `origin/master` before final report;
  verify with `git -C <worktree> fetch origin && git -C <worktree> rebase
  origin/master` and re-run 6.1-6.3, 7.2. Done: rebased cleanly (no
  conflicts) onto `fa1f54e6`; 6.1/6.2 and the QEMU harness (6.3) all
  re-passed against the rebuilt store paths, and 7.2 (`blob-scan`) passes
  after adding inventory rows the rebase's upstream commit newly required.

## 8. Board acceptance (explicitly out of scope for this pass)

- [ ] 8.1 **Hardware, not claimed by this change.** Real-finger Home page
  swipe, long-press pin/unpin/rearrange, dock taps, and launch-vs-focus,
  photographed on the physical AMOLED in both a dark and a light theme;
  verify on hardware with `python3 tools/capture-feature.py home-screen
  --provenance real-touch --duration 30 --description 'Real-finger Home
  page swipe, pin, rearrange, dock, launch-or-focus' --output-dir
  docs/evidence/home-screen/real-touch`. Left open per the coordinator's
  explicit instruction that this implementation does not touch the board
  or `/dev/ttyACM0`.

## 9. Proposal validation

- [x] 9.1 Validate this change; verify with `openspec validate
  the-shell-presents-a-pinned-home-screen --strict`. Done: valid.

Coordinator note: `the-handheld-presents-a-coherent-shell/design.md`'s
decision 1 ("Home is the deck, not a grid") is superseded by this change's
`design.md`. This change does not edit that file (it is unarchived and
under active, concurrent revision by other work); the coordinator should add
a superseding note to its decision 1 at that change's next revision or
archive, the same way its own decision 12 already superseded decision 11 in
place.

## 10. Reach Home through the user's navigation sequence

- [x] 10.1 Implement tracked Overview-to-Home navigation, cancellation and
  compositor Home visibility/focus restoration; Home's next bottom-edge
  swipe opens the drawer. Keep card throws, app entry and horizontal
  switching intact. Verify route ownership with
  `python3 -m unittest tests.test_card_shell_route` and the existing policy
  command `python3 -m unittest tests.test_card_shell_state`.
  Source `f39cb7eb`; 37 route/policy checks pass. The Home-layer runtime
  regression passes, as do 20 Rust Home tests and the desktop-ID regression.
- [x] 10.2 Extend the paired real-compositor/Rust QEMU fixture to exercise
  app → Overview → Home → Drawer with running windows; confirm window IDs
  survive Home, selecting an existing app restores it, and short/reversed
  gestures do not navigate or close apps. Run
  `python3 tests/rust_home_screen_qemu.py --sway <sway> --swaymsg <swaymsg> --rust <rust> --theme-bundle <theme-bundle> --icons <icons> --client <native-probe-client> --output <dir>`.
  Passed all 24 checks with the exact candidate compositor/Rust executables;
  see `docs/evidence/home-screen/navigation/qemu-result.json`.
- [x] 10.3 Build the coherent-shell system with
  `nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel --no-link`.
  On the reserved board, repeat the navigation sequence through verified
  injected touch, capture Overview/Home/Drawer, and check app identity and
  focus after returning. Keep real-finger acceptance distinct and open.
  Passed: `docs/evidence/home-screen/navigation/README.md` and `result.json`;
  three window IDs retained, measured held motion, Home icon restores Terminal.
- [x] 10.4 Land and deploy the qualified system, commit reviewed evidence
  and screenshot inventory, and verify the public work card and CI/Pages.
  Preserve task 8.1 and any unperformed physical checks; do not archive yet.

Task 10 delivery verified at `04eefdbf`: source and physical-board evidence
landed on `master`, the qualified system is running and persistently selected,
and Pages run `36300532436` passed build and deployment. The published evidence
page and `/work/` card both serve the new native captures. Task 8.1 remains
open; no archive is claimed.

## 11. GNOME activation refinement (user decision 2026-10-01; implementation underway)

Historical 4.2 remains the accepted long-press-to-grab implementation. The
operator rejected replacing it with a stationary-hold menu on 2026-10-01.
This group adds right-click app actions without changing touch placement. It is
separate from the accepted mouse/HDMI navigation closeout.

- [x] 11.1 Implement shared app-icon activation and menu action policy: reliably identify/recently focus existing windows, otherwise launch; read supported desktop actions/single-window metadata, prefer declared New Window and avoid duplicates. Verify `cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml` with multi-window, missing/mismatched identity and desktop-action fixtures.
- [x] 11.2 Wire secondary click to the app menu on Home/dock and the shared app-icon path; preserve long-press-to-grab and do not open a menu on touch hold; preserve deliberate drag-to-pin/rearrange, focus, cancellation and menu dismissal. Verify the same Rust suite with grab/move/cancel/secondary-click routing fixtures.
- [x] 11.3 Extend the paired real-compositor/Rust fixture to prove primary activation retains a known window ID while explicit New Window produces another, named actions work, unsupported actions are absent and canceled menus preserve input/layout. Record the concrete invocation in `docs/evidence/home-screen/`; run `python3 tests/rust_home_screen_qemu.py --sway <sway> --swaymsg <swaymsg> --rust <rust> --theme-bundle <theme-bundle> --icons <icons> --client <native-probe-client> --output <dir>`, then commit its actual result. QEMU injection is not finger evidence.
- [ ] 11.4 Build `nix build .#handheld-shell-rust .#nixosConfigurations.k230-coherent-shell-hdmi-trial.config.system.build.toplevel --no-link --print-out-paths`; install the recoverable candidate under the board reservation and record exact identities with `python3 tools/console.py /dev/ttyACM0 --wait=3 'readlink -f /run/current-system'`. Obtain operator acceptance of tap/focus, right-click New Window and preserved icon dragging; a committed operator report suffices unless a defect needs capture.
- [ ] 11.5 Validate with `openspec validate the-shell-presents-a-pinned-home-screen --strict`, land/push source and evidence and inspect matching CI/Pages. Keep original unresolved placement and physical scope tracked; this planning refinement alone does not ship the menu.

App-actions groups 11.2–11.3 passed: `docs/evidence/home-screen/app-actions/qemu/README.md`.
Cross Rust and the matching full coherent system also built from source `2885352`;
11.4 retains operator acceptance; its named HDMI trial build and recoverable
component installation have now passed. Original 8.1 remains open.

Recoverable component installation passed: `docs/evidence/home-screen/app-actions/board/README.md`.
The candidate has a 30-minute independent restoration timer; operator feedback
is still required by 11.4. The named individual Rust and HDMI toplevel builds
have now passed; their exact output paths are recorded in that board README.
