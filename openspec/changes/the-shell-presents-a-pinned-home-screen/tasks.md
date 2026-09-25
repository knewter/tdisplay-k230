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
  <swaymsg> --rust <rust> --theme-source nix/handheld-theme-default
  --output <dir>`. Done: PASS, all twelve checks true; see
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
- [ ] 7.3 Rebase onto the latest `origin/master` before final report;
  verify with `git -C <worktree> fetch origin && git -C <worktree> rebase
  origin/master` and re-run 6.1-6.3, 7.2.

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
