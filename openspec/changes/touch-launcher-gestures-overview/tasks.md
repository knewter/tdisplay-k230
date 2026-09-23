## 1. Gesture state machine

- [x] 1.1 Add pure launcher gesture-state tests for 48-pixel threshold, horizontal 1.25 dominance, tap retention below threshold, and one-action-per-release behavior; verify with `python3 tests/test_launcher_navigation.py` or a focused gesture test.
- [x] 1.2 Implement single-touch tracking for threshold crossing, direction classification, multi-touch rejection, and compositor cancellation without changing existing tap actions; verify short taps, diagonal motion, and cancelled touches through the focused state tests.
- [x] 1.3 Add horizontal page transitions capped at 200 ms with immediate settle fallback; verify no missed/duplicate page changes across 20 injected left and right swipes and no card launch after a classified swipe.

## 2. Metadata window overview

- [x] 2.1 Add an overview mode reached by an upward classified gesture and exited by Back or a downward classified gesture; verify mode transitions and keyboard-non-interactive layer-shell behavior with launcher tests.
- [x] 2.2 Read current Sway window metadata into title/app-id/state cards without thumbnails or screencopy; verify cards render for multiple windows and an empty state remains usable using a deterministic IPC fixture.
- [x] 2.3 Revalidate a selected window identifier before focusing it and handle stale/closed windows without exiting; verify stale selection, empty overview, and successful focus paths through the fixture test.

## 3. Preserve shell controls

- [x] 3.1 Keep Previous, Next, Back, Apps, Windows/Home, Keyboard, Help, Terminal, Monitor, and System actions available across launcher and overview transitions; verify `python3 tests/test_touch_menu.py` and existing launcher/catalog tests pass.
- [x] 3.2 Ensure the launcher releases or closes before focusing a selected window and does not steal the terminal keyboard path; verify a scripted Sway-tree fixture shows focus/return without duplicate terminal or monitor processes.
- [ ] 3.3 Record a rollback switch or safe failure path that disables gestures/overview while preserving tap and button navigation; verify a forced render/input failure returns to usable Apps and Back state.

## 4. Rendering and resource checks

- [x] 4.1 Measure launcher/overview transition update time and memory at 568x1232 RGB565/Pixman, including keyboard-visible and multiple-card states; verify median, p95, buffer count, and limitations are recorded in `docs/evidence/`.
- [x] 4.2 Keep the implementation client-only with no Sway/wlroots, GPU, VGLite, or screencopy dependency; verify the package diff and `nix build .#touch-launcher` show only the intended userspace closure.

## 5. Board validation

- [ ] 5.1 Build and flash the integrated image only after host tests pass; verify the normal shell, Apps, Help, keyboard, Terminal, Monitor, and Home controls still work on the board.
- [x] 5.2 Exercise 20 injected swipes in both directions plus tap, Back, overview focus, stale/empty state, and button fallbacks; verify console/native evidence labels injected input separately from physical-finger proof.
- [ ] 5.3 Capture a concise physical camera trial showing a real left swipe, right swipe, overview entry/exit, card tap, and Back with the display sharply focused; verify no legs/private scene content and retain physical-glass/readability limitations.

## 6. Review and integration

- [x] 6.1 Run `openspec validate touch-launcher-gestures-overview --strict` and verify every new requirement has evidence or an explicit `UNVERIFIED` marker.
- [ ] 6.2 Run `./scripts/build_site.py` and `./tools/blob-scan.py --no-vendor`; verify any evidence images/video have provenance, hashes, and DATA inventory rows.

Task 1.3: `docs/evidence/launcher-gestures/integrated-injected/README.md` records the flashed-image matrix: 20 exact left/right pairs, no new application window, and all 41 settled transitions within 163 ms. This is injected input; final-glass acceptance remains open.

Task 4.1: the integrated-injected evidence includes 40 keyboard-hidden Apps transitions, a two-window overview, and ten keyboard-visible transitions, with elapsed/process CPU median/p95, buffer/snapshot counters and before/after RSS/PSS. These are CPU-side measurements, not optical timing.

Task 3.2: `docs/evidence/launcher-gestures/metadata-budget/README.md` records the production-client host ordering fixture plus an injected Monitor-to-Terminal selection on the board: launcher closed, Terminal focused, existing Foot/htop process sets unchanged. The same report records 20 keyboard-visible two-card overview refreshes using the separated metadata deadline; final-image and physical-finger acceptance remain distinct.
