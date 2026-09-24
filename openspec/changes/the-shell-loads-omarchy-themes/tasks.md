All tasks are initially open. Commands naming new tools, tests or flake outputs
below are **planned interfaces**, to be added by that task before invocation;
they are not claims that those interfaces exist or have passed today. Host,
cross-build and physical proof are separate. Store committed results under
`docs/evidence/omarchy-themes/` with revisions, commands and limitations.

## 1. Reuse upstream helpers and unchanged source fixtures

- [x] 1.1 Pin and package the upstream palette, template, legacy-palette and OSC helpers plus relevant templates and licenses; carry the narrow staging/template-path patch and verify its output parity, then verify the closure with `nix build .#omarchy-theme-tools` and record the output. Reserve the sole build slot.
- [x] 1.2 Add exact-revision fixture acquisition for built-in light/dark themes and the community section-override sample; include `.git` directory clones, `.git` file worktrees and source directories without Git metadata. Record source hashes/licenses and prove no checkout changes with `python3 tests/test_omarchy_theme_sources.py`.
- [x] 1.3 Add helper compatibility tests for aliases, explicit ANSI/selection/custom colors, mode fallbacks, mix/gradient substitutions, full-file and section replacement precedence; compare upstream outputs with `python3 tests/test_omarchy_theme_resolution.py`.

Proof: `nix build .#omarchy-theme-tools` is a package cross-build; the two Python invocations are host checks only. No device claim.

## 2. Adapt the swap coordinator and shell notification

- [ ] 2.1 Implement compatible `omarchy-theme-set NAME` and paths plus direct source/collection selection, using upstream helpers and a narrow coordinator; test clone preservation, legacy scratch conversion, path boundaries and unknown-key reporting with `python3 tests/test_omarchy_theme_activation.py`.
- [ ] 2.2 Bridge upstream palette/shell/background payloads to our clients and replace desktop-only reload commands; test generation ordering, concurrent swaps, failed acknowledgement, rollback, update invalidation and removal of a source with `python3 tests/test_omarchy_theme_activation.py`.
- [ ] 2.3 Provide the pinned Nix default, fresh-home startup and persistent optional selections; build `nix build .#handheld-theme-service` and record its output and source revision.

Proof: `python3 tests/test_omarchy_theme_activation.py` and `nix build .#handheld-theme-service`. Host failure injection and package construction do not prove physical rollback or reboot behavior.

## 3. Apply all corresponding surface colors and icons

- [ ] 3.1 Build the generated-token consumer and coverage inventory for all upstream fields; verify real gradient stops/alpha, per-side widths, references, control states and font/spacing adaptations with `python3 tests/test_handheld_theme_rendering.py` and reviewed host captures.
- [ ] 3.2 Integrate drawer and card chrome with the shared generation and selected icon theme; verify actual source icon inheritance/cache invalidation plus dark/light captures with `python3 tests/test_handheld_theme_rendering.py --surface drawer-card`. Coordinate with existing icon/card worktrees.
- [ ] 3.3 Integrate Settings, notifications, chooser and keyboard as those sibling clients land; verify every corresponding role and explicit absent-surface report with `python3 tests/test_handheld_theme_rendering.py --surface system`. Do not tick this while consumers are only mockups.
- [ ] 3.4 Inventory and implement installed app appearance adapters, reusing Foot config/OSC; verify safe session-scoped reload and per-app limitations with `python3 tests/test_handheld_app_themes.py`.

Proof: the named host rendering and app-adapter tests plus reviewed capture hashes. Build each changed derivation separately before image integration; these tests alone do not establish panel readability or touch correctness.

## 4. Expose all backgrounds and theme choices by touch

- [ ] 4.1 Add lazy bounded still-image previews, upstream format discovery, user overlays, crop/fit/fill/center/solid choices and per-theme selection memory; verify decode errors, deleted images, cache limits and no per-drag redecodes with `python3 tests/test_handheld_theme_backgrounds.py`.
- [ ] 4.2 Integrate scroll/swipe/tap theme and wallpaper previews with cancel/apply and the existing motion contract; verify selection, cancellation, reduced motion and recovery state with `python3 tests/test_handheld_theme_chooser.py` and reviewed host captures.
- [ ] 4.3 Add bounded muted video backgrounds with format diagnostics, visibility pause, still fallback and reduced-motion behavior; verify lifecycle/failure cases with `python3 tests/test_handheld_theme_backgrounds.py --video` and build the isolated `nix build .#handheld-wallpaper` output. Performance remains a physical gate.

Proof: the named host tests and narrow wallpaper build. Video suffix recognition or a first frame is not playback/performance acceptance.

## 5. Integrate and prove the actual handheld

- [ ] 5.1 Build changed client outputs individually using the existing `nix build .#touch-launcher` and `nix build .#card-shell`, then build `nix build .#nixosConfigurations.k230.config.system.build.toplevel`; record exact closure and default source identities. Serialize cross-builds.
- [ ] 5.2 Add a reserved-board theme trial/operator procedure with normal-session restoration, fixed nonsensitive results and baseline-versus-themed workload identity; verify its failure recovery protocol on the host with `python3 tests/test_handheld_theme_trial.py` before using it.
- [ ] 5.3 Run `python3 tools/handheld-theme-trial.py --candidate-manifest CANDIDATE --output NEW_EVIDENCE_DIR` on the reserved board, using the exact manifest produced in 5.1/5.2. Commit console observations, native screenshots and focused real-finger chooser/gesture video for a built-in dark theme, light theme and unchanged community theme. Observe cancel, rollback, icon changes and all applicable surface roles; retain unmet gates.
- [ ] 5.4 Run that trial's `--workload backgrounds` mode with paired static and supported video backgrounds; record combined CPU, RSS, decode/presentation and card input/frame budgets, covered-media pause and restoration. Pass the existing card budgets before enabling animated defaults; do not relabel fallback-only results as full playback.
- [ ] 5.5 Run that trial's `--workload reboot` procedure to record boot identities and observe remembered theme/wallpaper, fresh-home default and unavailable-source recovery. Physical console plus panel observations are required; a persistence unit test does not prove reboot behavior.

Proof: the exact recorded build invocations and reserved-board commands above, with source/candidate identities and restored normal session. `CANDIDATE` and `NEW_EVIDENCE_DIR` must be replaced with concrete paths in the committed operator record. No flash or full-image readback is inherently required by a userspace theme trial.

## 6. Publish evidence and close deliberately

- [ ] 6.1 Publish feature screenshots/video, source/license attribution, complete compatibility matrix and measured limitations; verify site links with `python3 scripts/build_site.py` and inspect the deployment for the exact landed revision.
- [ ] 6.2 After every required task and physical gate passes, validate, archive/sync and push the change; verify `openspec validate --all --strict`, then inspect the resulting master/CI/Pages revision. Keep this change open if any required consumer or hardware proof is missing.

Proof: `openspec validate --all --strict` and `python3 scripts/build_site.py`, followed by exact-revision CI and published URL inspection. Planning publication alone is not a shipped capability.
