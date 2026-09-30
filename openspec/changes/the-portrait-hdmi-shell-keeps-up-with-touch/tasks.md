New harness and test commands below are implementation deliverables, not
already-existing proof. Every physical command requires the sole board
reservation. Public traces must omit network/device secrets.

## 1. Repeatable trace and precise attribution

- [x] 1.1 Add `tools/hdmi-shell-performance.py` with strict trace parsing,
  explicit injected/physical labels, output-state restoration and bounded board
  capture. Verify fixtures reject missing frames and mixed identities with
  `python3 tools/hdmi-shell-performance.py --self-test` (host-only).
  Eleven parser/dispatch fixtures and nine mocked capture fixtures pass; see
  `docs/evidence/hdmi-shell-performance/recovered-harness-check.txt`. Physical
  execution remains in the unchecked board tasks below.
- [ ] 1.2 Reproduce rotated/unrotated, ARGB8888/RGB565 baselines, then capture
  renderer stacks or subdivision timings, frequency and temperature. Commit a
  precise offending-stage analysis with limits. Verify on the physical board:
  `python3 tools/hdmi-shell-performance.py --capture --variant baseline --output docs/evidence/hdmi-shell-performance/baseline`.

## 2. Correct, opt-in portrait rendering candidate

- [ ] 2.1 Implement the profile-selected software rotation candidate and its
  host reference tests for asymmetric pixels, crop/scale, alpha, rounded clips,
  damage, format and texture updates. If considering hardware rotation, include
  transfer/synchronization/failure cost in the comparison and record the selection.
  Verify `python3 tests/test_pixman_quarter_turn.py` (new host test deliverable).
- [x] 2.2 Expose `card-shell-hdmi-trial` through the pinned board package graph,
  leaving the existing default available. Verify `nix build .#card-shell-hdmi-trial`
  (cross-build proof only). Result and exact store paths:
  `docs/evidence/hdmi-shell-performance/cross-build.json`.
- [ ] 2.3 Exercise the real candidate scene with changing clients and confirm
  pixels, callbacks, buffer release and fallback. Verify
  `python3 tools/hdmi-shell-performance.py --check-scene --variant candidate --output docs/evidence/hdmi-shell-performance/scene`
  (new host/headless harness mode; explicitly not physical acceptance).

## 3. Physical app-edge gesture diagnosis

- [ ] 3.1 Capture actual bottom-edge downs from an ordinary app, mapped/output
  coordinates, source times and route rejection reasons. Fix only the proved
  geometry/ownership/edge-band boundary, retaining interior app input. Verify
  `python3 tools/hdmi-shell-performance.py --capture --input physical --variant candidate --output docs/evidence/hdmi-shell-performance/physical-routing`
  with operator-confirmed contact during the capture.
- [ ] 3.2 Confirm real-glass app-to-overview, selecting the app again, keyboard
  dismissal and shade dismissal. Commit exact observations and native captures;
  an injected run cannot tick this task. Verify the same physical capture command
  plus the operator's named gesture sequence recorded in its README.

## 4. Board budget, default selection and regression proof

- [ ] 4.1 Compare baseline/candidate at unchanged 1920×1080 transform 90, with
  one and two Foot cards and at least 24 drags each. Include all rotation/copy
  work; require p95 build CPU ≤33.3 ms and physical contact-to-present ≤100 ms.
  Verify `python3 tools/hdmi-shell-performance.py --compare --baseline docs/evidence/hdmi-shell-performance/baseline --candidate docs/evidence/hdmi-shell-performance/candidate`.
- [ ] 4.2 After gates pass, select the winner in Nix defaults, build the integrated
  system and commit store/image provenance. Verify
  `nix build .#nixosConfigurations.k230.config.system.build.toplevel` (build proof).
- [ ] 4.3 Install the exact integrated system in a recoverable board trial, repeat
  real app gestures, and reboot into normal panel mode. Confirm panel app/keyboard
  behavior and unchanged recovery assets. Verify
  `python3 tools/console.py /dev/ttyACM0 --wait=3 'systemctl is-active shell shell-ui'`
  together with the committed HDMI/panel physical observation and image identity.

## 5. Land and close only proven work

- [ ] 5.1 Review, commit, merge and push source/evidence promptly; inspect the
  exact published work card and media. Verify strict OpenSpec validation and
  `python3 tools/blob-scan.py --no-vendor`, then the matching Pages deployment.
- [ ] 5.2 Archive only after every physical/correctness/budget gate above passes;
  retain unfinished neighboring changes. Verify
  `openspec validate the-portrait-hdmi-shell-keeps-up-with-touch --strict`
  immediately before syncing/archive, then inspect the deployed revision.
