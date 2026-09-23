# Board repeat after source-timestamp fix

The actual DSI-1 568x1232 RGB565 Pixman session ran package
`/nix/store/iyxcmrirznbl45ggzx6y4i42kp1wybzv-k230-card-shell`, source
`b88c4cc65af9274ea5ed0fb43619eefbf6a65396`, with the same 24-drag-per-count
native injected acceptance harness as `../../board-cost/long-trace/`.
The archive transferred over Wi-Fi with matching SHA256 before extraction.

All thirteen interaction checks were **OBSERVED**, including upward throw,
client refusal, separate timeout, accepted close and existing shell controls.
`interaction-checks.json` preserves those check rows; its raw collection status
remains `CAPTURED_REQUIRES_REVIEW`. This one successful repeat supports the fixed
path but is not proof that every real-finger throw is reliable. New screenshots
are not separately accepted here; prior reviewed native visual evidence remains
in `../../injected/`. The old failed throw and old-clock negative control remain
committed and are not superseded with passing claims.

Cost reproduction (expected exit 1, `FAIL`):

```sh
python3 tools/card-shell-benchmark.py --board \
  --input docs/evidence/card-shell/touch-timestamps/board/telemetry.log \
  --manifest docs/evidence/card-shell/touch-timestamps/board/manifest.json \
  --output /tmp/card-source-time-cost.json
```

One/two-card coverage is 143/138 submitted frames and 90/90 tracking intervals,
above the fixed 60/30 minima. There are no unresolved correlations or missing
provenance fields. This is not a performance pass or an established speedup.

| Metric | 1 card | 2 cards | Limit |
| --- | --- | --- | --- |
| Frame-update CPU, p95 | 16.963 ms | 24.546 ms | 16.667 ms |
| Frame-update CPU, max | 49.391 ms | 26.189 ms | 33.334 ms |
| Motion to submit, p95 | 38.867 ms | 53.088 ms | 50 ms |
| Motion to presentation, p95 | 51.421 ms | 66.971 ms | 66.667 ms |
| Tracking presentation interval, p95 | 57.565 ms | 57.559 ms | 33.334 ms |
| Release to final presentation, max | 51.298 ms | 78.970 ms | 266.667 ms |
| Incremental session memory | 483,328 bytes | 393,216 bytes | 67,108,864 bytes |

The experiment restored the original shell and seatd services. No image flash or
reboot occurred. Independent normal-control verification is in `restoration.json`.
Task 4.2 remains open: rendering/update work must improve independently of this
recognition fix. The existing dispatch-based telemetry and all cost thresholds
are unchanged. Backend presentation is not optical visibility, sampled memory
cannot rule out between-sample peaks, and injected input is not physical-finger
acceptance. Default image integration remains gated.
