## 1. wlroots fork and opt-in package

- [x] 1.1 Fork pinned wlroots 0.20.2 and add a serialized VG-Lite `wlr_renderer_impl`, texture implementation, and record/replay `wlr_render_pass_impl`; build an opt-in Sway against that fork while normal Sway remains Pixman.
- [x] 1.2 In `begin_buffer_pass`, accept only the output `wlr_buffer` supplied by the existing DRM backend; implement checked dma-buf import and prove no renderer code opens DRM, becomes master, modesets or commits.
- [x] 1.3 Record `add_rect` and `add_texture` options without GPU submission, then choose all-VG-Lite or full-Pixman replay at `submit`; verify failures do not commit a partial frame.

Host proof for group 1: `nix build .#shell-compositor-vglite --no-link --print-out-paths`
and `WLROOTS_SOURCE=<pinned-wlroots-0.20.2> VGLITE_SOURCE=<pinned-sdk-vg_lite> tools/test-vglite-renderer.sh`.
Source/host evidence: `docs/evidence/vglite-renderer-host.md`. No physical claim.

## 2. Operation and synchronization gates

- [ ] 2.1 Establish target format, plane, stride and modifier handling. Start with demonstrated DRM RGB565 / `VG_LITE_BGR565`; reject every unproved format or modifier.
- [ ] 2.2 Establish `wlr_texture_from_buffer` source ownership and exact `WL_SHM` XRGB/ARGB conversion/upload. Add sampled texture, nearest-scale, source-box and bounds tests; route arbitrary dma-buf, YUV and unproved input formats to full-pass Pixman replay.
- [ ] 2.3 Implement and test premultiplied `SRC_OVER`, `NONE`, pixman clip translation, and damage behavior against pinned wlroots render-pass fields. Use Pixman for unsupported clip, transform, filter, color or partial-damage cases until proven.
- [ ] 2.4 Serialize VG-Lite submission, call `vg_lite_finish`, prove C908 cache ownership in each CPU/GPU direction, and determine whether wlroots timeline fields can be honored. Reject timeline operations until then.

- [ ] 2.5 Establish compositor-only VG-Lite device access for the normal `shell` service without exposing the vendor API to ordinary clients sharing its UID. The separate root scene diagnostic does not satisfy this gate. Source implementation and host tests: `docs/research/vglite-service-access.md` and `docs/evidence/vglite-service-access-host.md`; actual privileged broker/service and board device proof remain open.

Host operation proof: the same sanitizer-backed renderer test above, comparing
against the pinned wlroots Pixman pass. Physical format/cache proof remains a
separate board gate, recorded in `docs/evidence/vglite-renderer-host.md`.

## 3. Board-only trial and decision

- [ ] 3.1 Verify opt-in Sway uses the forked renderer for a real scene render pass while the same Sway/wlroots DRM backend keeps master and scanout ownership. Capture selection, fallback and output evidence. Hardware proof only.
- [ ] 3.2 Compare repeated full-panel scenes with the same Pixman scene, recording wall, process CPU and available system/interrupt metrics. Cite committed CPU-validation evidence and state its limits. Hardware proof only.
- [ ] 3.3 Run touch, keyboard, Apps, Back/Home, Terminal, Monitor and system controls under GPU and forced-Pixman frames; capture recovery without a second DRM owner or display takeover. Hardware proof only.
- [ ] 3.4 Record target/source formats, clip/blend/damage behavior, completion/cache behavior, fallback rate and benchmark results. Run `openspec validate the-shell-trials-vglite-composition --strict` and `./tools/blob-scan.py --no-vendor`.
- [x] 3.5 Retain Pixman by default unless every gate passes and a separate default-change proposal is accepted; otherwise remove or keep the opt-in experiment as an explicitly unsupported diagnostic.

Diagnostic access analysis and bounded harness: `docs/research/vglite-diagnostic-access.md`. Host lifecycle check: `python3 tests/vglite/test_root_trial.py`. Actual privileged credential isolation is a separate prerequisite: `python3 tests/vglite/check_root_trial_credentials.py --user shell` as root; exit 77 is not proof.

Board scene trials and fixed-schema decisions: `docs/evidence/vglite-scene-board/README.md`.
The instrumented trial produced zero GPU frames and 224 Pixman replays; normal
shell recovery passed. Ordinary color metadata and 1136-byte target stride
were observed rejection reasons. Source/host default-color handling is now
tested separately; actual GPU submission, format/cache correctness, normal-service
access, and matched performance/interaction gates remain open.
