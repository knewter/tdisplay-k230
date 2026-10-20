# Current landscape HDMI motion baseline

Operator decision 2026-10-19: “keep the landscape for now.” HDMI stayed at
1280×800 @ 59.91 Hz, normal transform, scale 1. No renderer flag, input mode,
image/default, resolution or orientation was changed; no reboot was performed.
The separate portrait proposal remains 3/12 complete, with all nine gates open.

## Source and commands

Installed compositor source: `221bbcf34a276a939356e5a6af9bfb124af9896a`.
Collection/report source checkpoint: `1c8de3c1578b06180dd1159bc065ef9f4aa92ccb`.
The running and persistent system, executable and Pixman hashes are recorded
in `board/preflight.json`, both capture contexts and `board/final-normal.json`.
The output format is DRM ARGB8888 (`34325241`). The manifest's `candidate`
label describes the existing opt-in runtime; no before/after comparison ran.

Under the exclusive board lock the local collector ran once per workload:

```
python3 hdmi-shell-capture-board.py --profile landscape-1280x800 --variant candidate --input injected --seconds 180 --drags 24 --source-revision 221bbcf34a276a939356e5a6af9bfb124af9896a --output <new-one-or-two-directory>
```

Reproduce the strict report from the repository root:

```
python3 tools/landscape-hdmi-baseline.py --one docs/evidence/landscape-hdmi-baseline/board/one --two docs/evidence/landscape-hdmi-baseline/board/two --output /tmp/k230-landscape-baseline-report.json
```

Each run has 24 alternating drags,35 motion steps, nominal 0.7 s motion and 1.6 s
rest. IPC handling adds time; actual input timestamps and collector SHA256 are
retained. No extra board diagnostics ran during either timed workload. The
one-card run used the existing terminal. The two-card run added one temporary
Foot with fixed diagnostic text, then removed only that owned PID.

## Results

| Ordinary Foot cards | Complete drags | Input samples | Presented build samples | Build CPU p95 / max | Dispatch→present p95 / max |
| --- | --- | --- | --- | --- | --- |
| 1 | 24 | 864 | 855 | 4.897 / 5.276 ms | 27.255 / 276.520 ms |
| 2 | 24 | 864 | 737 | 6.577 / 8.407 ms | 47.038 / 192.037 ms |

All accepted inputs join exactly one submission and successful presentation,
and every correlated frame has build CPU evidence. Coalesced inputs can share
a frame; sample counts therefore differ. The strict diagnostic result is
`MEASURED`, with performance acceptance explicitly `NOT_EVALUATED`.

The worst one-card motion had 4.956 ms build CPU but 276.520 ms dispatch→present;
that trace alone does not locate the rest of its delay. Tail spikes remain
observable and deserve a separately grounded investigation. Do not describe
these results as uniformly smooth or a newly accepted physical latency budget.

## Failed attempts and cleanup

`rejected-a/` preserves the first run: journald suppressed 61 shell messages,
input IDs 609–612 disappeared, and only 23 drags were complete. The collector
correctly rejected it. Increasing rest from0.8to1.6 s reduced log pressure;
no motion samples were removed. That failed run is excluded from the baseline.

`board/first-wrapper.log` preserves the next attempt's successful one-card
capture and failure to map the second terminal through the standalone process
launcher. Cleanup restored the original one app/output. The subsequent
`board/two-card-wrapper.py.txt` used the compositor's established `exec foot`
launch path; its matching capture and cleanup completed. The precise standalone
launch failure was not diagnosed and no compositor defect is claimed from it.

Final checks at the timestamp in `board/final-normal.json`: normal motion,
benchmark-stop and Home commands succeeded, Overview inactive/mode 0, original
one terminal retained, both shell services active, no virtual test devices or
owned profiling/motion overrides, running/persistent system unchanged, and
HDMI 1280×800 normal unchanged. The board lease was then released.

## Evidence limits

Direct `card_shell down/motion/up` IPC exercises injected policy input. It does
not traverse a native/uinput device, authenticate a real finger, measure contact
delivery or establish optical visibility. The separate `test-touch` device is
headless-only and was not used on DRM. No camera/glass claim, performance
waiver, new default, panel regression proof or portrait acceptance is implied.
