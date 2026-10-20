# Fresh Settings status without Python startup during shade reveal

The native candidate reduces median per-call status CPU from814.089ms to85.922ms (89.45%), and median elapsed time from891.300ms to102.016ms. The three paired pulls have smaller median presentation gaps, but the second candidate pull has a134.129ms tail versus114.973ms baseline worst. This is a bounded improvement in the identified bottleneck, not a universal smoothness result. Physical acceptance and persistent promotion remain **PENDING**.

[Host parity/builds](host/README.md), [safe owned-storage cleanup](storage/README.md), [paired comparison](board/comparison.json), [capability/action result](board/capability-result.json), and [candidate selected for physical pull](board/physical-ready.json) retain separate evidence classes. The native C helper and Nix wrapper are built from sourceffa19e381de7151708ad339846660ec19d16ebda. Kernel/compositor/Rust binaries are unchanged. Source and evidence are landing incrementally; the OpenSpec change stays open4/7.

| Pull | Original median gap | Native median gap | Original maximum | Native maximum | Presented frames original/native |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 76.625ms | 38.4085ms | 114.973ms | 114.967ms | 14 / 19 |
| 2 | 57.490ms | 38.327ms | 114.968ms | 134.129ms | 15 / 20 |
| 3 | 67.060ms | 38.330ms | 114.972ms | 114.970ms | 15 / 20 |

## Bounded paired method

Each condition restarts the same installed Rust client with its existing20s numeric recorder, waits3s, then sends three synthetic shade reveal streams: begin,60updates at nominal60Hz over1.04s, finish closed,0.5s settle and0.5s pause. The private route socket bypasses actual contact and compositor gesture recognition. Both runs use the same [recorder source](board/paired-driver.py.txt), fixed trace ID and sampler. Keep PID/monotonic intervals distinct; do not merge span IDs across runs. A90s owned systemd timer can restore the original UI if the recorder fails; each completed run removed its trace override/timer and restored normal controls.

The UI wrapper differs by exactly the Settings executable path. The native wrapper still starts the existing bounded `pgrep` query; this is not a zero-subprocess claim. No priorities change. Both conditions retain boot69e90426, current/booted/persistent hpmz, actual accepted kernel notes/build7a61, Sway1046 with SHA9464072a, Rust SHA32c8c445, CPU0 only, unchanged boot files/root tracing controls and DSI-1 logical1232×568/transform270/scale1 at52.19Hz. The actual candidate [system/build identities](host/build.json) are transferred and rooted separately; no system/profile/boot selection changed during the test.

The baseline ran from `2026-10-20T20:42:13.968167+00:00` to `2026-10-20T20:42:49.384455+00:00`; the native pass from `2026-10-20T20:43:15.393200+00:00` to `2026-10-20T20:43:50.742744+00:00`. Exact manifest timestamps, settings-wrapper paths/hashes, before/during/after controls and every raw numeric event are retained in [baseline-a](board/baseline-a/manifest.json) and [candidate-a](board/candidate-a/manifest.json). There are2364/3014events, zero recorder/phase loss, and every committed frame ends in a recorded presentation or discard. Presentation gaps use actual CLOCK_MONOTONIC feedback timestamps within each pull; delivery delay is not presentation time. All discards/tails remain in the replay. The10Hz observer itself used10.60%/10.15% CPU over sampled intervals, so these are instrumented diagnostics, not native/optical frame-rate acceptance. No camera or finger timing is inferred.

The combined host log has a systemd timer launcher prefix before its one-line JSON result. A whole-file JSON summary parse therefore failed, although the actual board driver completed0. [Disposition](board/log-parser-disposition.json) preserves this host framing correction; the copied raw manifests and traces independently replay successfully. This did not fabricate an absent capture/control file.

## Fresh state and action boundary

[Capability proof](board/capability-result.json) records three alternating fresh-process calls per old/native wrapper as the shell user, with page/source caches potentially warm. All status JSON values match. A real external panel-brightness change100→99percent is read freshly by both implementations and restored exactly to the original raw value/100percent. Invalid brightness101 takes the unchanged Python failure route. A real reboot confirmation request is cancelled; no power action executes and confirmation contents are discarded. Host tests separately cover confirmed-action behavior; no hardware keyboard-toggle or actual power confirmation is claimed here.

## Commands and replay

Protected SSH configuration and runtime contents stay outside Git. Exact remote source is committed alongside each result; the operator's explicit SSH preference replaces a UART requirement.

```sh
# After transfer and guarded preflight, under the exclusive board lease:
ssh -F "$PROTECTED_SSH_CONFIG" k230 "$BOARD_PYTHON /run/pane23-shade-status/shade-status-paired-driver.py"
ssh -F "$PROTECTED_SSH_CONFIG" k230 "$BOARD_PYTHON /run/pane23-shade-status/shade-status-paired-driver.py --candidate"
ssh -F "$PROTECTED_SSH_CONFIG" k230 "$BOARD_PYTHON /run/pane23-shade-status/shade-status-capability-check.py"
python3 docs/evidence/shade-status/board/analyze.py.txt docs/evidence/shade-status/board/baseline-a
python3 docs/evidence/shade-status/board/analyze.py.txt docs/evidence/shade-status/board/candidate-a
```

## Physical trial and remaining gate

After both recorders restored the original UI, [guarded trial selection](board/enable-trial.py.txt) selected the same candidate UI wrapper normally, without any trace environment or priority change. The candidate became ready at20:46:14Z, RustPID3724, with landscape and normal services preserved. The operator was asked to pull the top drawer a few times; [the exact request](board/physical-request.json) remains unanswered in this record. This is a temporary runtime UI selection; ordinary reboot still selects accepted hpmz until separately accepted persistent promotion. The candidate closure has its own GC root, and known-good rollback remains preserved. Do not infer physical acceptance from the comparison.

Other drawer/keyboard/card quantitative work and portrait hardware gates remain open in their own proposals. This change introduces no main-spec delta and will archive only after its remaining physical, persistent-startup/cleanup and publication tasks pass.
