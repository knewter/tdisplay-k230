# Landscape shell motion measurements — 2026-10-19

Both injected-input runs fail the declared latency and frame-interval budgets.
The full and reduced runs each captured **216 accepted input IDs, all five
stages, and no unresolved traces**. Reduced motion shortened median release
settling from **294.035 ms to 155.655 ms**. Rendering still presented at about
**26.095 Hz** in both modes.

The CPU subdivision identifies a useful lead: scene building/painting costs
about **22–23 ms of CPU per submitted-input frame**, already above the nominal
19.16 ms panel interval. It accounts for about 97% of render CPU, while the
input handler averages about 0.5 ms. This points the next performance
investigation at the build/paint path; it is not proof of one particular
Pixman operation or a claimed performance fix.

These original runs are actual-board software timestamps and native `grim`
captures after injected uinput events. At their collection time the camera
framed another device. Later, the operator aimed it at the K230 and **new**
concurrent full/reduced runs completed the separate camera-visible gate:
[camera/README.md](camera/README.md). The original runs are not retroactively
claimed as optical evidence. No real-finger latency, every-refresh blanking,
HDMI, performance improvement, or new reboot is claimed.

## Identity and workload

- Branch: `side-edge-back`, base `6620bf5c71840812800f293b1409dc5765c8b0c9`.
- Installed compositor source: `29fe458cc4044cb5095e6aeb5fc84b4fdfb3d931`.
- Analysis and exporter source: `f45bbeba` (consumer hash in
  [sources/input-hashes.json](sources/input-hashes.json)).
- Exact-source build:

  ```sh
  flock /tmp/k230-nix-build.lock nix build \
    "git+file://$PWD?rev=29fe458cc4044cb5095e6aeb5fc84b4fdfb3d931#kernelMainlineDrmShellLandscapeHdmiBootFiles" \
    --max-jobs 4 --cores 8 --option substituters https://cache.nixos.org --fallback
  ```

- Built bundle: `/nix/store/7lp9mc2z5l9yq0x34pyb8vq2isz5aaza-k230-coherent-shell-boot-files`.
- Installed and running system:
  `/nix/store/48afqvxz6i15rz9q4if3b1c08j6l3n37-nixos-system-nixos-26.11.20260919.20b1ddd`.
  Boot files were installed and verified and userspace was activated. No new
  reboot was performed; this change touches userspace only.
- Output: `DSI-1`, transform `270`, logical 1232×568, physical mode 568×1232
  advertising 52190 mHz; renderer `pixman`, format `RGB565`.
- Each session reported **three open cards**: an existing Terminal and two
  temporary Foot clients labeled `Motion-one` and `Motion-two`.
- Each run held a three-second resource baseline, entered Overview, then
  injected six horizontal gestures. Each gesture starts at (616,280), moves
  in 35 steps over 700 ms to (366,280) or (866,280), alternating directions,
  then releases and waits 800 ms. A three-second resource tail follows.
- The named `K230 injected touchscreen` was a temporary uinput clone of the
  actual controller, with direct-input properties and its measured axis
  ranges. Logical coordinates map to native normalized `(y/567, 1-x/1231)`.
  It was destroyed after each run. This reaches the real libinput/Sway/native
  touch path; it is software input.
- `grim` ran before and after the qualifying gesture loops, with no held
  capture interrupting those loops.
- Full run: `82570247133503`, started **21:52:07 UTC**; reduced run:
  `82650784426941`, started **21:53:28 UTC**. The per-run metadata records
  each contact's monotonic down/up times and the actual output mode:
  [full-metadata.json](full-metadata.json),
  [reduced-metadata.json](reduced-metadata.json).

## Results

Budgets were retained from the existing tool: p95 within two nominal panel
intervals (**38.3215 ms**), p99 within three (**57.4823 ms**), and compositor
RSS growth at most **64 MiB**. No CPU budget is declared.

| Measurement | Full | Reduced |
| --- | ---: | ---: |
| Accepted input IDs | 216 | 216 |
| Motion / release inputs | 210 / 6 | 210 / 6 |
| Missing stage chains / unresolved traces | 0 / 0 | 0 / 0 |
| Input-to-present p50 | 49.651 ms | 49.080 ms |
| Input-to-present p95 | **70.327 ms — FAIL** | **69.231 ms — FAIL** |
| Input-to-present p99 | **76.192 ms — FAIL** | **83.860 ms — FAIL** |
| Frame interval p50 | 38.321 ms | 38.322 ms |
| Frame interval p95 | **57.482 ms — FAIL** | **57.444 ms — FAIL** |
| Frame interval p99 | **57.486 ms — FAIL** | **57.483 ms — FAIL** |
| Median output presentation cadence | 26.095 Hz | 26.095 Hz |
| Inferred extra nominal refresh intervals | 153 | 134 |
| Unpresented output events | 0 | 0 |
| Release-to-settled-present p50 | 294.035 ms | 155.655 ms |
| Compositor CPU, one core = 100% | 28.318% | 27.478% |
| Peak compositor RSS | 48,156,672 bytes | 45,400,064 bytes |
| Compositor RSS growth | 8,101,888 bytes | 10,973,184 bytes |

The p99 interval overruns are retained even where they exceed the threshold
by only a few microseconds. The latency and p95 interval overruns are much
larger. Both run statuses in [../motion.json](../motion.json) are `FAIL`;
the analysis command exits **1**, as expected for failed budgets. The
reduced-motion stage/parity check succeeds, with the same stage shape and a
shorter measured settle. No threshold was changed after measurement.

## CPU lead

[cpu-profile.json](cpu-profile.json) uses the existing correlated CPU
analyzers and the same producer rows. It checks input/frame accounting and
subdivides only frames carrying accepted input IDs (108 full, 109 reduced).
Animation-only frames are included in the process sampler, but are not
invented as input-bearing frame-cost rows.

| Mean CPU per submitted-input frame | Full | Reduced |
| --- | ---: | ---: |
| Total charged CPU | 25.416 ms | 24.307 ms |
| Render CPU | 23.555 ms | 22.503 ms |
| Scene/output preparation | 0.532 ms | 0.469 ms |
| Build/paint | **22.760 ms** | **21.770 ms** |
| Output commit CPU | 0.263 ms | 0.264 ms |
| Build as share of render CPU | 96.623% | 96.742% |
| Input handler per input | 0.501 ms | 0.450 ms |

Build includes wlroots output-state construction, painting and any tearing
check; it is not a pure Pixman function profile. Commit CPU is not scanout
latency. The row timing/logging itself has overhead. The current data narrows
the investigation to rendering; it does not identify a single optimized
function or prove how much an optimization would save.

## Reproduce the analysis

[telemetry.log](telemetry.log) contains only fixed-grammar exported rows.
It combines the two normalized run blocks, followed by separately collected
input/frame/repaint CPU rows for those same run IDs. Original timestamps
are preserved; records are correlated by IDs, not by file order. Original
per-run input hashes and capture times are preserved in
[sources/input-hashes.json](sources/input-hashes.json).

```sh
python3 tools/shell-motion-trace.py --board \
  --log docs/evidence/coherent-shell/motion-2026-10-19/telemetry.log \
  --provenance injected --compare-motion \
  --output docs/evidence/coherent-shell/motion.json
# Expected exit: 1, with each failed budget named.

python3 docs/evidence/card-shell/input-cost-probe/analyze.py \
  --input docs/evidence/coherent-shell/motion-2026-10-19/telemetry.log \
  --output docs/evidence/coherent-shell/motion-2026-10-19/cpu-profile.json
```

Exact collection and restoration scripts are retained as `.py.txt` artifacts
under [sources](sources/collect-motion-board.py.txt). They record the original
scratch/store paths; these are collection artifacts rather than portable
installed commands. SSH used the protected configuration pathname
`~/tmp/k230-coordination/ssh_config.private`; its contents are not included.
The exporter preserves only known keys and numeric/stage/mode values.

## Timing boundaries and limits

- Input begins at the existing device monotonic-origin diagnostic where
  available, including dispatch queueing. Legacy logs fall back to handler
  dispatch. The new captures include origin diagnostics for the inputs.
- Scene damage means the first completed scene update containing a pending
  input. Coalesced inputs retain their own IDs into the next real update.
- Commit is dispatch time for the successful output commit. Presentation is
  the driver's reported timestamp. Frame done is actual surface-callback
  dispatch, which this driver can deliver **after** its presentation timestamp.
  Callback-to-presentation intervals remain signed; no timestamp is shifted
  or sorted to create a fictitious linear order.
- Release settling uses the successful output frame observed after policy
  animation completes, separately from the first frame after lift-off and
  from the motion sampler's 300 ms filter-quality hold.
- Cadence uses **all actual output presentation events** inside each gesture's
  tracking/settling window, including frames with no new input. Coalesced
  inputs are not counted as independent output frames.
- `missed_frames` estimates additional nominal refresh periods between
  presentations. It is not a count of dropped DRM events or camera frames.
- The report's legacy `blank_frames` field counts unpresented output events.
  Zero such events does **not** prove zero visible blank panel frames;
  camera-visible blank frames remain **UNVERIFIED**.
- CPU and RSS cover the compositor process, not all applications or system
  memory. Percent CPU uses the sampled interval, including baseline/tail.
- These driver/dispatch timestamps do not measure input-to-photon latency.
  There is no camera correlation for these runs.

## Earlier diagnostic and recovery

The first producer (`3c6ea3eb`) was checked with one 16-step gesture:
[diagnostic-probe/metadata.json](diagnostic-probe/metadata.json),
[diagnostic-probe/telemetry.log](diagnostic-probe/telemetry.log), and
[diagnostic-probe/held.png](diagnostic-probe/held.png). It exposed the real
callback ordering and seven coalesced IDs without scene rows. Its held
`grim` capture was intrusive and its 17 IDs are below the sample minimum.
It is diagnostic evidence only; its timings are not substituted for the
qualifying full/reduced data above.

Reduced motion was applied through one owned runtime service drop-in, with
an independent 180-second restoration timer. That override was removed,
the timer stopped, and the normal shell/UI restarted. Temporary clients
and injected devices were removed. [restored.json](restored.json) confirms
the installed system, active services, reduced-motion environment `0`, the
absent owned drop-in, zero test devices, and a successful Home command.
The board and build reservations were released.

The first CI run of the new host checks
([39330811752](https://github.com/knewter/tdisplay-k230/actions/runs/39330811752))
failed because the host-only runner imported Pillow. Owner: pane 23.
Commit `f45bbeba` makes compositor/image imports conditional; the host
checks pass with `python3 -S tests/test_shell_motion.py --case trace-order
--case reduced-motion`, and the native telemetry/exporter suite passes
30 tests. This was a CI dependency issue, separate from the measured board
budget failures.

## Camera proof completed separately

After the operator repositioned the camera, two new concurrent trace/video
runs completed the named task 2.2 gate. See [camera/README.md](camera/README.md)
for run IDs, original videos, hashes, clock bounds, frame review and limits.
Both new runs still fail the timing budgets; this change measures those
failures rather than fixing the renderer. The initial runs and report above
retain their original software-only evidence class.
