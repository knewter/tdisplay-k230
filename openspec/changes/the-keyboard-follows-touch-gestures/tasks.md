Commands naming new files below are planned interfaces, not existing proof. Preserve real-glass gates until observed and commit evidence under `docs/evidence/keyboard-gestures/`.

## 1. Input ownership and motion policy

- [ ] 1.1 Implement bounded two-contact edge recognition, separate grip dismissal, direct tracking and release settlement; verify hold/reverse, early/late second contacts, stale velocity and reduced motion with `python3 tests/test_keyboard_gestures.py`.
- [ ] 1.2 Prove cancellation, keyboard loss/output change and ordinary key/app input isolation through the same host fixture; run `python3 tests/test_keyboard_gestures.py` before marking complete.

Proof: `python3 tests/test_keyboard_gestures.py` is host policy evidence only.

## 2. Live keyboard integration and discoverability

- [ ] 2.1 Integrate the actual keyboard surface, themed grip, clipping, focus and consistent exclusive area with compositor ownership; build `nix build .#card-shell --max-jobs 1 --cores 4 --no-link --print-out-paths` under the sole build reservation.
- [ ] 2.2 Add the Settings gesture hint and retain explicit keyboard control, distinct from Wi-Fi editor cancellation; verify dark/light host rendering and build `nix build .#handheld-shell-rust --max-jobs 1 --cores 4 --no-link --print-out-paths`.
- [ ] 2.3 Add and run `python3 tests/test_keyboard_gestures_runtime.py` against the exact built compositor and keyboard, verifying injected two-contact show, grip hide/hold/reverse, typed text ownership and settled app geometry. Record native screenshots and source/store identities.

Proof: the two narrow Nix builds plus `python3 tests/test_keyboard_gestures_runtime.py`. Native headless QEMU does not establish panel touch reachability or smoothness.

## 3. Install and prove on glass

- [ ] 3.1 Build `nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel --max-jobs 1 --cores 4 --no-link --print-out-paths`; record exact output and a recovery-capable installed identity via `python3 tools/console.py /dev/ttyACM0 --wait=3 'readlink -f /run/current-system'` while holding the board reservation.
- [ ] 3.2 Run a documented real-finger show, type, slow hide/hold/reverse, committed hide and app-navigation sequence. Capture focused feature video with `python3 tools/capture-feature.py --help` used to select its concrete recording command, commit that command and camera/native provenance, and keep user acceptance open until explicitly confirmed.
- [ ] 3.3 Measure keyboard visibility and gesture workload against the existing shell responsiveness budgets using the installed compositor instrumentation; commit the exact workload/operator invocation and observed results. Do not infer motion quality from static captures.

Proof: exact build and console identity above, committed concrete camera/workload commands and real-glass observations. No routine flash readback is required.

## 4. Publish and close

- [ ] 4.1 Publish feature media and updated dashboard evidence as it arrives; run `python3 scripts/build_site.py`, push master and inspect exact-revision Pages deployment.
- [ ] 4.2 After all source and physical gates pass, run `openspec validate the-keyboard-follows-touch-gestures --strict`, archive/sync the runtime/shell delta, commit and push. Leave incomplete tasks open.

Proof: `python3 scripts/build_site.py` and `openspec validate the-keyboard-follows-touch-gestures --strict`, followed by exact deployed revision inspection.
