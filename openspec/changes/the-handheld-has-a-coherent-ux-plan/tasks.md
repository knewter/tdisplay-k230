## 1. Evidence inventory and journey map

- [ ] 1.1 Build the source-of-truth inventory for boot handoff, shell controls, launcher/catalog, keyboard, cards, and video; link each observation to its committed report or capture and label host/native/injected/camera/real-finger evidence. Verify with `rg -n "UNVERIFIED|injected|physical|camera|native" docs/evidence openspec/changes/touch-launcher-gestures-overview` (host proof only).
- [ ] 1.2 Write the outside-in first-use, repeat-use, keyboard-visible, video, error, and recovery flows with user goals, visible states, escape routes, and accessibility checks. Verify the delivered flow matrix covers every requirement in `specs/docs/handheld-ux-plan/spec.md` (host document review).
- [ ] 1.3 Create the severity-ranked issue ledger with evidence gap, owner, dependency, P0/P1 priority, and narrow acceptance measure; reconcile ownership with `the-shell-has-a-card-composition-plan`, `the-shell-manages-apps-as-cards`, `touch-launcher-gestures-overview`, and `the-shell-plays-network-video`. Verify no ledger row duplicates card gesture or app lifecycle implementation ownership by reviewing those proposal files (host review).

## 2. Shared visual and interaction contract

- [ ] 2.1 Define portrait visual tokens for text roles, spacing, contrast, focus/pressed/error states, minimum touch geometry, and keyboard-visible layout, with a method to record panel-pixel and camera limitations. Verify the contract includes a native screenshot check and a separate optical/real-finger gate (host document review).
- [ ] 2.2 Define navigation ownership for Apps, Windows/overview, cards, Back, Home, Keyboard, System, Stop, Help, and focus return, including empty/stale/loading/failure/EOF/cancelled states. Verify every route has a visible fallback and an owning successor proposal (host document review).
- [ ] 2.3 Define motion and accessibility acceptance: bounded Pixman transition/frame budget, immediate settle fallback, reduced-motion behavior, readable status text, and keyboard/focus semantics. Verify the checks are measurable and do not imply unsupported rotation, GPU, thumbnails, or real-finger success (host document review).

## 3. P0/P1 successor proposals and parallel ownership

- [ ] 3.1 Propose a P0 onboarding/boot-feedback and recovery change, using existing splash evidence as baseline and reserving physical first-use timing/readability for the board. Verify its proposal names the layer owner, rollback path, and board command before implementation (host OpenSpec review).
- [ ] 3.2 Propose a P0 cross-surface visual/state consistency change for loading, empty, error, cleanup, and accessibility labels; let network-video own lifecycle and the shell/card owners consume the shared contract. Verify host fixtures cover state transitions before a serialized board session (host tests/document review).
- [ ] 3.3 Coordinate P1 card composition and app-card lifecycle with the existing proposals, adding only missing visual/navigation contract work; schedule source/model work in parallel and physical gesture/readability proof serially. Verify `openspec status --change the-shell-has-a-card-composition-plan --json` and the app-card proposal status are reviewed before landing any successor (host OpenSpec review).
- [ ] 3.4 Keep rotation and advanced visual effects as explicit deferred questions until source or board evidence exists. Verify the ledger retains `UNVERIFIED` markers rather than creating an unsupported implementation task (host document review).

## 4. Acceptance and integration

- [ ] 4.1 Run host source, catalog, launcher, menu, and video-state checks relevant to the ledger; record which checks are deterministic and which do not establish physical usability. Verify with `python3 tests/test_launcher_navigation.py && python3 tests/test_touch_menu.py && python3 tests/test_window_catalog.py && python3 tests/test_desktop_catalog.py` (host proof only).
- [ ] 4.2 Run one board session for boot/first-use, optical hierarchy, real-finger reachability, keyboard/focus, and motion only after host gates pass; capture sanitized provenance and keep injected and physical results separate. Verify with the named `tools/msh.py` or board capture command recorded in the successor proposal (hardware proof; no QEMU substitution).
- [ ] 4.3 Validate and publish the complete planning change with unchecked tasks preserved for unperformed evidence. Verify with `openspec validate the-handheld-has-a-coherent-ux-plan --strict` and `python3 tools/work-status.py` (host proof).
