The new profile collector/test commands below are deliverables, not existing
proof. Every board command requires the sole board reservation; build commands
require the build slot. No physical gate can be ticked from a host check.

## 1. Attribute the installed landscape cost

- [x] 1.1 Add bounded numeric-only profile collection/analysis, then capture the
  installed three-card workload with exact runtime identity and observer limits.
  Commit draw/rotation/build/commit attribution and choose the measured boundary.
  Proof: `python3 tools/panel-paint-profile.py --log docs/evidence/panel-paint/baseline/profile.log --output docs/evidence/panel-paint/baseline/profile.json`, plus the committed reserved-board collection command and telemetry. The parser is a new deliverable; its host self-test alone is not board proof.

## 2. Implement and prove the selected fix

- [x] 2.1 Implement only the profile-selected paint/copy optimization. Prove
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

Progress2026-10-19: baseline installed-source29fe458c has actual RGB565 final
rotation mean10.755ms (65 gesture-window rows). Texture logging hits cap512;
only44 complete observed passes are grouped. The selected boundary is the
rotation copy. The candidate packs four fresh16-bit source pixels into an
aligned64-bit destination write within source tiles and retains the32-bit
path. Native tests pass288 guarded multi-frame cases,1152 affine-reference
comparisons and288 rounded-clip comparisons. A separate board microbenchmark
with unattached DRM dumb buffers measures10.130→4.109ms for rotation1, with
exact pixels; this is not integrated frame/latency proof. Hardware tasks2.2/3.x
and archival remain open. See docs/evidence/panel-paint/README.md.

Follow-up after integrated trial: source08cf4516 built and was activated with
baseline boot/profile preserved. It reduced full-run build CPU to16.506ms
mean/17.521ms p95, but full/reduced still failed motion budgets at26Hz, so
the baseline was restored. A full-precision landscape opaque cache now avoids
repeated scaling while preserving every source commit and the8ms anti-flicker
window. Native tests cover64 rounded/partial/output-rotation cases across
XRGB8888/RGB565 sources and three changed frames each. Exact-source build and
board/live-content/camera/default/archive gates remain open for this follow-up.

Sourcef1c70977 exact build and trial passed native pixel tests but still failed
board budgets. Cache counters were zero; actual Foot SHM isARGB8888. The next
source preserves alpha in anARGB8888 cache and passes96 native cached-pixel
cases. Baseline restored; new build/board/live/camera gates remain open.

After sourceed45dc69, actual wallpaper opacity lowers build mean9.970ms but
motion still fails. A buffer-owned logical image and damage-aware final copy
now remove forced whole-frame work. The named native command passes16
three-buffer cases/352 exact compositions, lifecycle/failure injection,768
conversion cases,160 live cache cases and288 guarded full copies; existing
1152 affine/288 rounded comparisons also pass. No new hardware result yet;
exact build2.2 and qualification/default/archive tasks remain unchecked.
