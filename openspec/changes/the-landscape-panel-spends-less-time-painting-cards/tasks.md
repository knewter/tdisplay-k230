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
- [x] 2.2 Build the exact candidate userspace/landscape boot bundle and preserve
  source/store identities. Proof: `nix build .#kernelMainlineDrmShellLandscapeHdmiBootFiles`
  at the committed source revision under the build lock; build success is not installation proof.

## 3. Qualify the candidate on the board

- [x] 3.1 Install the exact candidate recoverably and repeat the same paired
  full/reduced workload and cost attribution. Verify changing live content,
  callbacks and buffer release, native pixels and concurrent camera movement.
  Commit source/system IDs, workload, clocks and camera limits. Proof:
  `python3 tools/shell-motion-trace.py --board --log docs/evidence/panel-paint/candidate-scene-coalescing/camera/telemetry.log --provenance injected --compare-motion --output /tmp/panel-paint-camera-motion.json`,
  plus `python3 tools/panel-paint-profile.py --log docs/evidence/panel-paint/candidate-scene-coalescing/profile.log --workload docs/evidence/panel-paint/candidate-scene-coalescing/profile-workload.json --output /tmp/panel-paint-profile.json`.
  Keep open on any pixel/lifetime regression or missed acceptance gate; report all failed budgets.
- [x] 3.2 Select the qualified default in repository source and restore normal
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

Source9 adds optional immutableRGB565 interiors, within the same8MiB app cache,
while preserving full precision under every mask. The named native command
passes512 extra guarded oracle cases,64 selected paths,32 sensitivity cases
that reject quantized corners, and reuse/budget/allocation/registration/free
checks; all earlier pixel/lifecycle commands pass. Synthetic on-board copies
are faster, with setup costs separately recorded. Exact-source build and all
paired timing/live/camera/default/archive gates remain open for this candidate.

Source37be9567 exact build9b succeeded and live counters/callbacks/releases
advance. Two earlier full PASS / reduced FAIL pairs used asynchronously
ordered terminals; the corrected middle-card pair11 fails both modes. Full
build6.243ms mean/6.722ms p95, reduced6.178ms/6.861ms, do not meet all end-to-end
budgets. All runs/limits are committed under candidate-opaque-interior/.
Mostly transparent title margins select the next exact paint omission.
Camera/default/archive remain open; no full-only pass qualifies the pair.

The next source crops immutable header painting to actual nonzero texels,
retaining full authored Pango layout/cache keys,1:1 pixels and policy hit tests.
1104 native cropped/full pixel comparisons pass (real glyphs, ellipsis,
Unicode, alpha, clips and offscreen motion), plus all earlier native commands.
Header visibility preserves clipping so offscreen ink cannot reappear at a
stale position. This candidate still requires its own exact build and board,
live-content, camera, default-selection and archive proof.

Source895e753d exact build/live/native checks pass. Final collector also waits
for the late startup Terminal, confirms focus/app set and actual selected card.
Comparable pair13 has byte-identical setup captures: reduced passes software
budgets, full still fails latency51.738ms p95/66.006ms p99. Full build mean5.246ms,
measured title0.059ms; rotation is largest remaining stage. Baseline restored;
all trial failures and fixture limits are committed in candidate-label-ink/.
No paired/camera/default/archive qualification is claimed.

The remaining rotation stage selects eight-pixel gather/store batches within
unchanged16×16 tiles. Isolated unattached-DRM trials lower full-copy CPU11–12%
and representative-region CPU16%; rectangular tiles/loop reordering/32-bit
stores are rejected. Complete source/commands/results are in rotation-batches/.
Native6 tests plus1152 affine/288 rounded pass; eight distinct overlap pairs
are rejected before the restricted helper's full/partial calls. This new
source still needs exact build and all integrated/physical/default gates.

Source1bc9243f exact build/CI/native proof passes. Controlled pair14 passes
both modes, but stability repeat15 fails fullp95=39.326ms and reducedp95=46.078ms/
p99=65.078ms; all four setup images are identical. Build mean4.8–4.9ms is not
stable latency qualification. Per-input scene synchronization remains0.53ms,
then timer/render prepare repeats it. That duplication is the next measured
boundary; every presented frame, policy/ownership and structural changes must
remain current. Baseline restored and board released; camera/default/archive
still open. Complete evidence is in candidate-rotation-batches/.

The next checkpoint coalesces plain moving redraws at render preparation only
for rotatedRGB565, retaining immediate policy/chrome, structural changes and
idle/bilinear restoration.41 policy cases pass; the new actual-compositor
rotated/full/reduced/normal regression test remains unperformed until the exact
build is available. The old chrome mock also fails unchanged baseline due to
fixture drift, with both logs retained in scene-coalescing/. No new board,
physical/default/archive proof is claimed at this checkpoint.

Checkpoint221bbcf3 exact build and actual-compositor integration pass after
correcting unsupported fixture app IDs (first failure preserved). RotatedRGB565
full/reduced exercise coalesced redraw/timer calls and latest-pose rendering;
normal output leaves those counters zero. Live main/child frames, structural
maps, immediate expansion chrome and restored bilinear counts pass. The host
test fix changes no compiled adapter source. Board timing/current live/camera,
qualified default and archive remain unverified for this checkpoint.

Exact candidate221bbcf3 build12 succeeds with committed source/bundle/system
identities. Controlled pairs16 and17 both pass full/reduced frozen software
budgets, with verified identical setup frames and positive coalescing counters.
Build p95<=5.458ms; input CPUmean about0.19ms, all stages retained. Current
board live main/child content/callbacks/releases advance; separate profile
captures53 complete grouped passes. All evidence/commands/limits are committed
under candidate-scene-coalescing/. Baseline restored normal/Home, own91/92
absent and no test devices; board released. Task3.1 stays open for **current
camera** proof:02:57:54UTC camera still shows the other Ladybird display, no
qualifying video. No persistent qualified selection or archive is claimed.

2026-10-20 camera completion: new current-source full/reduced40s videos cover
all six gestures;48 samples/mode visibly show movement. Both associated traces
PASS (fullp95/p9931.423/34.793ms; reduced34.447/38.113ms). Camera sampling and
1.881s/1.255s correlation bounds remain explicit; no optical-latency/every-
refresh claim. Qualified source221bbcf3/build12 systemj30 is now running and
persistently selected, with verified boot hashes and baseline48 backup.
Normal/Home, shell/UI, profiling off, owned91/92 absent and no injected devices
are checked under reservation. No reboot or full-image flash. All proof and
executed protocol are in candidate-scene-coalescing/camera/. Publication and
archive follow only after this evidence is committed and strict checks pass.
