The new profile collector/test commands below are deliverables, not existing
proof. Every board command requires the sole board reservation; build commands
require the build slot. No physical gate can be ticked from a host check.

## 1. Attribute the installed landscape cost

- [ ] 1.1 Add bounded numeric-only profile collection/analysis, then capture the
  installed three-card workload with exact runtime identity and observer limits.
  Commit draw/rotation/build/commit attribution and choose the measured boundary.
  Proof: `python3 tools/panel-paint-profile.py --log docs/evidence/panel-paint/baseline/profile.log --output docs/evidence/panel-paint/baseline/profile.json`, plus the committed reserved-board collection command and telemetry. The parser is a new deliverable; its host self-test alone is not board proof.

## 2. Implement and prove the selected fix

- [ ] 2.1 Implement only the profile-selected paint/copy optimization. Prove
  pixels, changing contents, clips/alpha/crops/transforms, damage across frames,
  fallback and affected ownership with the native pixel/lifecycle fixture.
  Proof: `python3 tests/test_panel_paint.py` (new deliverable, host only), plus
  existing `python3 tests/test_pixman_quarter_turn.py` and
  `python3 tests/test_card_rounded_clip.py` where relevant.
- [ ] 2.2 Build the exact candidate userspace/landscape boot bundle and preserve
  source/store identities. Proof: `nix build .#kernelMainlineDrmShellLandscapeHdmiBootFiles`
  at the committed source revision under the build lock; build success is not installation proof.

## 3. Qualify the candidate on the board

- [ ] 3.1 Install the exact candidate recoverably and repeat the same paired
  full/reduced workload and cost attribution. Verify changing live content,
  callbacks and buffer release, native pixels and concurrent camera movement.
  Commit source/system IDs, workload, clocks and camera limits. Proof:
  `python3 tools/shell-motion-trace.py --board --log docs/evidence/panel-paint/candidate/telemetry.log --provenance injected --compare-motion --output docs/evidence/panel-paint/candidate/motion.json`,
  plus `python3 tools/panel-paint-profile.py --log docs/evidence/panel-paint/candidate/profile.log --output docs/evidence/panel-paint/candidate/profile.json`.
  Keep open on any pixel/lifetime regression or missed acceptance gate; report all failed budgets.
- [ ] 3.2 Select the qualified default in repository source and restore normal
  motion/Home. Record installed source/system, absent owned overrides, active
  shell/UI and no test devices. Proof: the committed protected-SSH/console
  restoration check and `python3 tools/console.py /dev/ttyACM0 --wait=3 'systemctl is-active shell shell-ui'` if serial is used. No reboot/image claim without one.

## 4. Publish and close deliberately

- [ ] 4.1 Validate, commit and land tested source/evidence promptly, inspect CI
  and the exact published revision. Proof:
  `openspec validate the-landscape-panel-spends-less-time-painting-cards --strict`
  and `python3 tools/blob-scan.py --no-vendor`; retain unchecked hardware gates.
- [ ] 4.2 Archive/sync only when all named correctness/budget/physical gates
  pass and evidence is committed, or an explicit new user decision preserves
  remaining work. Proof: strict validation immediately before `openspec archive`,
  then matching pushed revision and Pages deployment.
