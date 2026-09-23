# Card shell benchmark and provisional budget contract

Declared 2026-09-23, before product board acceptance, for
`the-shell-manages-apps-as-cards` task 4.1. The parser and its synthetic self-tests
are host evidence. **No board measurements are recorded by this document.**
The default acceptance path is Sway/Pixman at the actual 568×1232 RGB565 output.
RGB565 describes the observed 16-bit buffer format; Sway's `render_bit_depth 6`
is a per-channel selector and is not a six-bit framebuffer.

The accepted UX contract in `docs/research/handheld-ux/interaction-contract.md`
requires continuously visible finger tracking, separate release measurement,
recovery, and preserved core behavior with reduced motion. The previous
200ms launcher release result is a design reference, not evidence that live
cards meet it. These thresholds are provisional product targets; measurements
may reject them, but a failed measurement must not silently loosen a budget or
remove live cards, direct tracking, expansion, close recovery or button routes.

## Budgets fixed before measuring the board

All times begin at compositor input dispatch in `CLOCK_MONOTONIC`. They exclude
unknown device/transport latency before dispatch. Percentiles use nearest rank;
limits are inclusive, and both p95 and maximum limits apply where listed.

| Metric | p95 | Maximum | Rationale and boundary |
| --- | ---: | ---: | --- |
| Scene update plus render/commit CPU | 16.667ms | 33.334ms | A provisional 30 updates/s target leaves roughly half its 33.334ms interval for non-render work at p95. Measure charged input-handler CPU plus successful repaint CPU once per output commit. This is CPU time, not presentation latency. |
| Motion dispatch to commit submission | 50ms | 100ms | Keeps ordinary tracking within roughly one to two 30Hz intervals and explicitly bounds outliers. This is submission, not visible pixels. |
| Motion dispatch to actual presentation feedback | 66.667ms | 133.334ms | Two 30Hz intervals at p95 and four for outliers; requires a matching successfully presented commit. This is the electrical/backend proxy for input-to-visible change, with optical acceptance still separate. |
| Presented update interval during continuous input | 33.334ms | 100ms | Targets 30 visibly presented updates/s and rejects long stalls. The parser uses actual presentation times; callbacks cannot replace them. |
| Release to final stable commit submission | — | 200ms | Carries the accepted UX release bound into the live-card implementation as a new, unproved target. |
| Release to final actual presentation | — | 266.667ms | The release submission target plus two 30Hz presentation intervals. |
| Incremental isolated-session memory, sampled peak | — | 64MiB | Keeps extra composition cost bounded on a nominal 1GiB device, separately from existing app workload. A 568×1232 XRGB8888 surface is 2,799,104 bytes; 64MiB allows roughly 24 such full-frame buffers before other overhead. This is a budget, not a claim about buffer copies or available RAM. |

The memory baseline uses the **same mapped applications and same isolated
session cgroup**, before entry. Compare peak sampled active `memory.current`
against median baseline `memory.current`. Do not compare an empty shell with a
busy card workload, change app count between baseline and active measurement,
or substitute compositor RSS for total session memory. Compositor RSS and CPU
are useful separate observations. Restored memory delta is reported, but it is
not automatically a leak: allocators can retain arenas. Sampling does not rule
out shorter memory spikes.

A run needs at least 60 motion inputs, 60 unique measured output commits,
30 continuous presented-frame intervals, and three completed releases. Each
baseline/active/restored session resource phase needs at least three samples
spanning two seconds. These minima make an isolated fast frame insufficient to
pass. The board report requires independent **one-card and multiple-card**
workloads; each must satisfy its gates. More populated decks may be measured
without imposing a fixed product card limit.

## Producer contract agreed with the Sway adapter owner

The adapter emits one line per event, with only the following fields. Every
line begins `K230_CARD_BENCH`; `v=1` and a run token are present on every row.
The parser accepts equivalent JSON objects for stored records. It copies no
window titles, app text, keys, network information, arbitrary journal text or
unrecognized metadata into its report.

```text
K230_CARD_BENCH v=1 run=1 event=session t_ns=N clock=monotonic backend=drm renderer=pixman width=568 height=1232 output_format=RGB565 input=injected cards=2
K230_CARD_BENCH v=1 run=1 event=input input_id=N gesture_id=N kind=motion source=injected t_ns=N
K230_CARD_BENCH v=1 run=1 event=input input_id=N gesture_id=N kind=release source=injected t_ns=N
K230_CARD_BENCH v=1 run=1 event=submit input_id=N frame_id=N t_ns=N update_cpu_ns=N final=0
K230_CARD_BENCH v=1 run=1 event=present frame_id=N t_ns=N presented=1 clock=monotonic
K230_CARD_BENCH v=1 run=1 event=resource phase=baseline t_ns=N cpu_ns=N memory_bytes=N scope=session
```

These are grammar examples; `N` is an integer placeholder, **not telemetry**.
Allowed fields and meanings:

- `session`: exactly one header per run. `t_ns` is the entry boundary; baseline
  rows may be emitted before this header. `cards` is the measured source-card
  workload, not a hard-coded allowance. Width, height, renderer, backend and
  output format must describe the actual output, not requested settings.
  A headless backend can produce a host report but cannot pass board acceptance.
- `input`: a unique per-run input ID and gesture ID, `motion` or `release`, with
  the actual dispatch timestamp. `source` is `physical`, `injected` or `host`
  and must match the run. The native input path alone cannot authenticate a
  human finger; physical input remains an operator-attested provenance claim.
- `submit`: one mapping for each measured motion input; release may have
  initial `final=0` feedback followed by exactly one later `final=1` mapping.
  Each `(input_id, frame_id)` is unique. Rows are emitted only
  after the output commit succeeds. `frame_id` is that output's `commit_seq`.
  Record the successful commit's monotonic submission boundary as `t_ns` and
  elapsed charged update/repaint CPU as `update_cpu_ns`. `final=1` on a release
  means the submitted scene has reached its final stable policy result; a
  merely scheduled damage operation is not a final submission. A stable card
  and visible Closing state can be final visual settlement even while the
  graceful-close protocol deadline remains pending. If the visual result itself
  waits for that deadline, the measured delay remains in the release budget.
  First release feedback is reported separately from final visual settlement.
- Multiple inputs can map to the same frame. Emit a submit row for **each**
  pending input, with identical time and CPU cost for that frame. The parser
  deduplicates frame CPU and retains every input latency. This does not claim
  every intermediate finger position appeared: coalesced input counts are
  reported explicitly.
- `present`: the actual `wlr_output_event_present.commit_seq`, `when` timestamp
  and `presented` flag, not an invented time at callback handling. The producer
  must establish the pinned backend presentation clock before labelling it
  monotonic. A discarded frame (`presented=0`), missing feedback, mismatched
  clock or missing input/submit correlation cannot pass a visible-update gate.
- `resource`: phase is `baseline`, `active` or `restored`; timestamps are
  monotonic; CPU is a cumulative nanosecond counter. `scope=compositor` reads
  process CPU and resident bytes; `scope=session` reads isolated cgroup-v2
  `cpu.stat` usage (converted from microseconds) and `memory.current`.
  Session data is enabled only with `SWAY_K230_CARD_BENCH_CGROUP=1` after the
  coordinator verifies the service cgroup contains exactly the workload.
  A general desktop/user cgroup is not an acceptable substitute.

Every rendered change associated with measured input must be accounted for.
Keep release submission/presentation logging active after deck restoration so
exit-to-app latency remains measurable. Missing records after overflow or a
render error must stay missing; the parser returns `INCOMPLETE` rather than
manufacturing timestamps. A run with incompatible clocks, duplicate identities,
conflicting frame rows, regressing CPU counters or impossible ordering is
rejected as invalid evidence.

Continuous cadence is measured only within one gesture. The parser excludes
and counts actual gaps over 50ms in the original motion event stream. It does
**not** mistake a long frame gap bridged by many coalesced motion events for an
idle finger: that gap remains in the frame-interval metric and may fail it.

## Reserved-board collection procedure

This is a procedure for the board coordinator; the parser never opens UART,
starts a compositor, flashes an image, injects input or captures a camera.
The adapter package, its safe session harness, and the architecture capability
proof must be reviewed before running this procedure.

1. Record the installed card-shell store path, source revision, board model,
   collection timestamp, input provenance and coordinator reservation. Start
   the opt-in package as the sole compositor with the required existing apps
   in one isolated service cgroup. Set `SWAY_K230_CARD_BENCH_CGROUP=1` only after
   checking that ownership. No default renderer substitution is allowed.
2. From that session's `swaymsg`, arm `card_shell benchmark injected` (or
   `card_shell benchmark physical` for the separately recorded real-finger run).
   Leave the same apps in normal mode for at least three seconds to collect
   baseline samples. No gesture is generated by arming the benchmark.
3. Enter cards and exercise continuous horizontal motion and at least three
   releases. Continue long enough to meet the sample minima. Keep the same
   mapped app workload during that measured interval. Include an actual
   rendered release/return path, not only queued input.
4. Use Back to restore normal mode. Wait at least three seconds for restored
   memory samples and pending release presentation; then issue
   `card_shell benchmark-stop`. Preserve the actual service journal invocation,
   not a mix of separate compositor sessions. Repeat with one and multiple
   source cards, using separate run IDs. Do not use full journal text as shared
   evidence: retain only `K230_CARD_BENCH` records in the telemetry artifact.
5. On the host, place the captured rows in
   `docs/evidence/card-shell/telemetry.log` and the operator manifest in
   `docs/evidence/card-shell/manifest.json`. The manifest schema is:

```json
{
  "schema": 1,
  "environment": "board",
  "board_model": "LILYGO T-Display-K230",
  "ownership": "coordinator-reserved",
  "source_revision": "ACTUAL_40_HEX_REVISION",
  "package_store_path": "/nix/store/ACTUAL_STORE_HASH-k230-card-shell",
  "evidence_class": "board-injected",
  "collected_at": "ACTUAL_TIME_WITH_TIMEZONE"
}
```

The placeholders deliberately fail validation. Record actual values;
`board-real-touch` is a separate evidence class and requires its own input
provenance. The parser validates structure and consistency; it cannot attest
that a person, camera or physical board was actually present.

```sh
python3 tools/card-shell-benchmark.py --board \
  --output docs/evidence/card-shell/pixman.json
```

Use `--input` and `--manifest` to select separately captured evidence. An
optional VGLite workload uses `--renderer vglite` and must actually report that
renderer; requesting the flag does not convert Pixman results. The optional
optimization does not replace the default Pixman gate.

Exit 0 means all available report gates pass with the required coverage;
exit 1 writes a valid report with `FAIL` or `INCOMPLETE`; exit 2 means missing or
invalid evidence and writes no new report. A host report always has
`board_budget_gate=NOT_BOARD_EVIDENCE`. The top-level report and every run
retain sample counts, missing correlations, resource phases, telemetry digest,
limits and status. Optical visibility and real-finger acceptance remain
`UNVERIFIED` even when a board telemetry budget passes.

## Host proof and handoff

```sh
python3 tools/card-shell-benchmark.py --self-test
```

The self-test exercises synthetic inputs only and cannot create a board report.
Its cases cover complete one/multiple workload parsing, absent presentation,
callback-only rejection, scope-correct memory and failed budgets, coalesced
inputs, continuous-input stalls, missing mappings, duplicate identities,
conflicting timestamps, provenance, renderer/backend mismatch, resource phase
ordering, nonfinal release, discarded presentation, missing input files and
private journal-text exclusion.

This task does not close product task 4.2, physical motion acceptance, optical
latency/readability or source eligibility. If the measured Pixman budgets fail,
record the measurements and retain the open requirement. Any optimization or
reduced-refresh decision must preserve the complete live-card interaction and
be measured independently; do not lower these limits after seeing a failure.
