Commands naming new files below are planned interfaces, not existing proof. Preserve real-glass gates until observed and commit evidence under `docs/evidence/keyboard-gestures/`.

## 1. Input ownership and motion policy

- [x] 1.1 Implement bounded two-contact edge recognition, separate grip dismissal, direct tracking and release settlement; verify hold/reverse, early/late second contacts, stale velocity and reduced motion with `python3 tests/test_keyboard_gestures.py`.
- [ ] 1.2 Prove cancellation, keyboard loss/output change and ordinary key/app input isolation through the same host fixture; run `python3 tests/test_keyboard_gestures.py` before marking complete.

Proof: `python3 tests/test_keyboard_gestures.py` is host policy evidence only.

## 2. Live keyboard integration and discoverability

- [x] 2.1 Integrate the actual keyboard surface, themed grip, clipping, focus and consistent exclusive area with compositor ownership; build `nix build .#card-shell --max-jobs 1 --cores 4 --no-link --print-out-paths` under the sole build reservation.
- [x] 2.2 Add the Settings gesture hint and retain explicit keyboard control, distinct from Wi-Fi editor cancellation; verify dark/light host rendering and build `nix build .#handheld-shell-rust --max-jobs 1 --cores 4 --no-link --print-out-paths`.
- [x] 2.3 Add and run `python3 tests/test_keyboard_gestures_runtime.py` against the exact built compositor and keyboard, verifying injected two-contact show, grip hide/hold/reverse, typed text ownership and settled app geometry. Record native screenshots and source/store identities.
- [x] 2.4 Fix a jank regression in 2.1's "consistent exclusive area": the ordinary-maximized app's usable-area reservation is recomputed every ~16ms animation tick, and a real client cannot redraw/commit a matching buffer that fast on this CPU, so its stale, old-sized buffer left an unpainted margin exposing the desktop background during a keyboard drag. Added `ordinary_backdrop` (`nix/card-shell/adapter.c`), a card-coloured `wlr_scene_rect` in `output->layers.tiling` resized to the current `usable_area` on every `ordinary_sync_usable()` call — a compositor-side reposition with no client round trip — directly behind ordinary cards. Added a `--stall-resize-ms` fixture to `card-composition-probe-client` to model a slow client, and a hard-assertion regression check `python3 tests/keyboard_drag_backdrop_qemu.py`; confirmed it fails against the pre-fix source and passes against the fix. Evidence: `docs/evidence/keyboard-drag-usable-area-gap/`.

Proof: the two narrow Nix builds plus `python3 tests/test_keyboard_gestures_runtime.py` and `python3 tests/keyboard_drag_backdrop_qemu.py`. Native headless QEMU does not establish panel touch reachability or smoothness, and this harness has no wallpaper renderer, so the "before" gap reads flat black rather than the real desktop wallpaper photo.

## 3. Install and prove on glass

- [x] 3.1 Build `nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel --max-jobs 1 --cores 4 --no-link --print-out-paths`; record exact output and a recovery-capable installed identity via `python3 tools/console.py /dev/ttyACM0 --wait=3 'readlink -f /run/current-system'` while holding the board reservation.
- [ ] 3.2 Run a documented real-finger show, type, slow hide/hold/reverse, committed hide and app-navigation sequence. Capture focused feature video with `python3 tools/capture-feature.py keyboard-gestures --duration 15 --provenance real-touch --description "Two-finger show, typing, handle dismissal and reversal"`, record the actual camera and output directory plus camera/native provenance, and keep user acceptance open until explicitly confirmed.
- [ ] 3.3 Measure keyboard visibility and gesture workload against the existing shell responsiveness budgets using the installed compositor instrumentation; commit the exact workload/operator invocation and observed results. Do not infer motion quality from static captures.

Proof: exact build and console identity above, committed concrete camera/workload commands and real-glass observations. No routine flash readback is required.

## 4. Publish and close

- [ ] 4.1 Publish feature media and updated dashboard evidence as it arrives; run `python3 scripts/build_site.py`, push master and inspect exact-revision Pages deployment.
- [ ] 4.2 After all source and physical gates pass, run `openspec validate the-keyboard-follows-touch-gestures --strict`, archive/sync the runtime/shell delta, commit and push. Leave incomplete tasks open.

Proof: `python3 scripts/build_site.py` and `openspec validate the-keyboard-follows-touch-gestures --strict`, followed by exact deployed revision inspection.

Installed checkpoint: [native board identity and captures](../../../docs/evidence/keyboard-gestures/installed-preview/README.md). Tasks 2.2 and 3.1 have their named build/identity proof; real-finger and output-change recovery gates stay open; the later native Foot text proof completes task 2.3.
