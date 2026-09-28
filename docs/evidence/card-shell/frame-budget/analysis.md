# Why ~57.48ms: a desk-check from existing evidence, then a board plan

For `openspec/changes/the-card-deck-still-misses-its-frame-budget` (staged,
not authorized). This is investigation only: kernel/driver source reading,
a re-analysis of telemetry already committed to this repo, and a new
read-only board tool. It changes no source-of-record behavior and proposes
no fix.

## 0. The number is already explained by data this repo already has

Before touching the board: `docs/evidence/card-shell/board-cost/long-trace/
telemetry.log` is raw `K230_CARD_BENCH` output from a real board run and
contains 1,660 `event=present` rows with real hardware presentation
timestamps. Computing the plain frame-to-frame presentation interval over
**all** of them (not just the subset `tools/card-shell-benchmark.py`'s
`tracking_present_interval_ms` metric keeps -- see its filter at
`tools/card-shell-benchmark.py:246-281`) gives:

```
n=1659  min=19.093ms  p50=19.161ms  p90=38.321ms  p95=57.477ms  max=383.194ms
```

`docs/evidence/card-shell/board-cost/long-trace/README.md` reports the
metric's own p95 as **57.482ms**. These agree to within 0.005ms. The
filtered, gated metric is not a different phenomenon from the raw
presentation cadence -- it *is* the raw presentation cadence, restricted to
frames a gesture happened to touch.

The panel's programmed timing (`nix/dts/display-rm69a10-568x1232.dtsi`:
`clock-frequency = 49500000`, `htotal = 748` computed from
100+40+40+568, `vtotal = 1268` from 4+16+16+1232) gives an exact period:

```
period = htotal * vtotal / clock = 748 * 1268 / 49_500_000 = 19.16094 ms
1x = 19.161ms   2x = 38.322ms   3x = 57.483ms   4x = 76.644ms
```

Every one of the percentile buckets above lands on an exact integer
multiple of that period, to three significant figures. **This is
quantization to the vblank grid, not evidence of a divide-by-3 anywhere in
particular.** A frame that cannot be presented at the very next vblank
(because its render, submission, or commit is still in flight) is
necessarily presented at *some* later vblank -- 2 periods late, 3 periods
late, or more -- and a percentile taken over a mix of on-time and late
frames will sit on whichever bucket boundary the tail distribution happens
to cross at that percentile. The proposal's own framing ("57.48ms ...
unchanged by ... every independently tested variable") is the framing of a
*fixed* structural interval; what the data actually shows is a *quantized*
one that tracks workload:

| Source | Workload | Frame-update CPU p95 | Tracking-interval p95 | Nearest multiple |
| --- | --- | --- | --- | --- |
| `board-cost/short-trace/README.md` | 1 card | 17.11 ms | 57.48 ms | 3x (57.48) |
| `board-cost/short-trace/README.md` | 2 cards | 24.05 ms | 76.63 ms | 4x (76.64) |
| `board-cost/long-trace/README.md` | 1 card | 17.218 ms | 57.482 ms | 3x |
| `board-cost/long-trace/README.md` | 2 cards | 24.174 ms | 57.485 ms | 3x |

The 2-card short-trace run lands in the **4x bucket**, not 3x. A fixed
hardware or driver cadence of "one presentable frame every 3 vblanks"
predicts the *same* number regardless of card count; the data instead shows
the bucket shifting up with heavier workload. That is inconsistent with any
hypothesis where the panel, DSI link, or VO hardware itself can only ever
produce a new frame once every 3 refreshes. It is exactly what a
non-pipelined render->submit->commit path produces under a growing tail of
slow frames.

This reframes the investigation: the open question is not "does the panel
refresh at 1/3 rate" (the existing data already argues no), but **why does
a large enough fraction of frames miss more than one vblank that the p95
lands 2-3 buckets out, and is that fraction fixed by something upstream of
render cost** (which is why RVV/cache changes, which target render cost,
didn't move it). The board tool below still answers this properly instead
of by inference, per `design.md`'s "measure directly, don't infer" mandate
-- but it should be aimed at the commit/serialization path and the raw
vblank rate, not treated as a search for a hidden 3x panel divider.

## 1. Ranked hypotheses

### H1 (leading, evidence-grounded): vblank-grid quantization from a non-pipelined atomic commit path

`drivers/gpu/drm/canaan/canaan_crtc.c:90-108` (pinned tree,
`nix/kernel-src.nix`, confirmed still unpatched in `nix/kernel.nix` --
the one patch that would have changed this ordering,
`canaan-drm-defer-reg-load-to-vblank.patch`, is "deliberately NOT applied"
per `nix/kernel.nix`'s own comment, because it caused a separate boot
panic):

```c
static void canaan_crtc_atomic_flush(...)
{
    ...
    canaan_vo_flush_config(vo);                      // synchronous register write
    if (event) {
        WARN_ON(drm_crtc_vblank_get(crtc) != 0);
        ...
        drm_crtc_arm_vblank_event(crtc, event);       // completion armed for the NEXT hw vblank
    }
}
```

Every atomic commit that carries a completion event (every real compositor
commit) is only ever completed at *a* vblank -- there is no partial credit
for "almost in time." Combined with the already-documented render-cost
tail (`docs/evidence/card-shell/bottom-band-flicker/kernel-vblank-latch.md`:
"Renders are occasionally slow. Median 1.4ms, p90 31.7ms, p99 41.9ms, max
81.2ms; 15% of frames took over 19.16ms") and this driver's synchronous,
non-deferred commit (no evidence anywhere in `canaan_crtc.c` or
`canaan_vo.c` of a pipelined/nonblocking commit queue -- one commit's
register write happens inline in `atomic_flush`, before the next commit can
begin), a render or commit that overruns by even a little rounds up to the
*next whole vblank*, and the amount of overrun (which vblank it lands on)
depends on total pipeline latency: render time, submission/serialization
overhead, and any scheduling jitter for the atomic-commit-tail worker --
not render time alone. This is consistent with every fact on hand:
CPU-only changes (RVV, scaled-cache) don't move the p95 bucket because the
tail that determines it is not purely render-time; and the bucket does
shift with card count (57ms at 1 card, 77ms at 2 cards) because the
underlying overrun distribution shifts even though median render cost
stays well under budget.

**What would confirm or refute this on the board:** correlate DRM vblank
*sequence numbers* with presented `frame_id`s (via
`tools/measure-panel-refresh.sh`'s vblank probe run concurrently with
`tools/card-shell-benchmark.py --board`) -- if presented-frame vblank
sequence deltas track render/submission latency in whole-period steps, H1
is confirmed and the actionable target becomes the commit-path
serialization (pipelining commits, or reducing the specific tail source),
not the panel.

### H2 (real, grounded, but separate): VO shadow-register commit is not synchronized to the blanking window

Same code as H1, `docs/evidence/card-shell/bottom-band-flicker/
kernel-vblank-latch.md`'s own finding: `canaan_vo_flush_config()` (the
`VO_REG_LOAD_CTL = 0x11` write, `canaan_vo.c:712-715`) fires at whatever
arbitrary point in the current scan the atomic-commit worker happens to
run, not during the driver's own IRQ-line blanking window
(`VO_DISP_IRQ1_CTL`, computed in `canaan_vo_set_timing()`,
`canaan_vo.c:649-650`). This is a genuine, unresolved defect (its fix,
`canaan-drm-defer-reg-load-to-vblank.patch`, exists but is not applied
because it caused an unrelated boot panic -- see
`docs/evidence/card-shell/bottom-band-flicker/kernel-patch-boot-panic.md`).
It explains the *bottom-band flicker* symptom (a torn/incorrect last few
scanlines on a late-applied frame) but has no natural mechanism to produce
a clean *3x interval*; a mistimed shadow-register latch changes what a
frame looks like, not how many vblanks pass before the next one is armed
(`drm_crtc_arm_vblank_event`/`drm_crtc_vblank_get`, unaffected by this
bug, per the same document). Rank below H1 for explaining the *interval*
specifically; still worth fixing on its own merits, separately from this
change's budget question.

### H3 (low likelihood, code-ruled-out): DSI command-mode/TE handshake blocking the flip

The panel is driven over **continuous burst-mode video DSI**, not command
mode (`nix/dts/display-rm69a10-568x1232.dtsi`: "pclk 39600 kHz, phyclk
475200 kHz, 2 lanes, burst mode"; `canaan_dsi_clk_cfg()` derives the PHY
bit clock directly from pixel clock with no slack, i.e. this link streams
continuously rather than waiting for command triggers). There is no
"waiting for TE to send the next command" step to gate on in a
video-mode link. Independently, `docs/evidence/
flicker-after-headroom-revert.md` already established that "nothing in the
driver consumes the TE signal" at all -- `35 00` (SET_TEAR_ON) is sent in
the init sequence but nothing ever reads the TE line back, so no software
path can be blocked waiting on it. That document's own TE finding is a
*slow positional roll* (a free-running GRAM-write/scan phase drift), not a
frame-rate divisor -- a different, already-tracked, unrelated bug. Rank
low.

### H4 (unlikely as stated, testable in one command): VO_DISP_IRQ1_CTL fires the vblank IRQ at 1/3 rate

`canaan_vo_set_timing()` (`canaan_vo.c:598-651`) writes
`VO_DISP_IRQ1_CTL = 32 - __builtin_clz(vtotal) - 1` -- i.e.
`floor(log2(vtotal))` -- which for `vtotal=1268` is **10**, a value with no
obvious relationship to the actual frame length (also note: the device
tree's own `vth_line = <10>` property on `&vo`, added in
`nix/dts/display-rm69a10-568x1232.dtsi`, is **dead** -- `canaan_vo.h`
declares a `vth_line` struct field but nothing in `canaan_vo.c` ever calls
`of_property_read_u32` for it; the driver always recomputes the same
formula from `vtotal` regardless of what the device tree says). This
formula is unmistakably vendor cruft and worth flagging on its own, but the
hypothesis that it makes the vblank IRQ fire at 1/3 the true rate is
**directly contradicted by data already in this repo**: the same
`long-trace/telemetry.log` used in section 0 shows a **p50 presentation
interval of 19.161ms** -- i.e. the *median* frame is presented within one
refresh period, which could not happen if the hardware only raised the
vblank IRQ (and hence only ever called `drm_crtc_handle_vblank()`,
`canaan_vo_irq_handler()`, `canaan_vo.c:486-498`) once every three
refreshes. `tools/measure-panel-refresh.sh`'s IRQ-rate section still gives
a clean, independent, board-measured confirmation for the record (expect
~52.2 Hz, not ~17.4 Hz), but this hypothesis should be considered
pre-refuted rather than open.

### H5 (contributing factor, not primary cause): `max_render_time 8` interacting with a missed deadline

`docs/evidence/card-shell/bottom-band-flicker/max-render-time-fix.md`:
`swaymsg output DSI-1 max_render_time 8` is live in `nix/shell.nix`'s Sway
output line, trading up to 8ms of added input-to-photon latency to move
render work away from the end-of-scan DDR contention window. This is a
believable contributor to *additive* latency (pushing a borderline frame
from "just barely on time" to "one period late") but has no natural
mechanism to produce a stable *3x* multiplier on its own -- it is a
bounded, roughly-constant addition, not a multiplier. Its effect should
show up as part of H1's overrun budget, not as an independent cause. The
board tool's idle-vs-drag comparison (section 2) captures whether this
setting changes the *shape* of the interval distribution, not just shifts
it.

### H6 (confirmed structure, non-explanatory): injected-harness input bursts

Directly visible in `board-cost/long-trace/telemetry.log`'s `event=input`
rows: injected motion samples arrive in tight bursts of 3 (sub-millisecond
to a few ms apart) separated by 25-50ms gaps, and each burst is coalesced
into a single submitted `frame_id` (`tools/card-shell-benchmark.py`'s own
comment at line 276: "Many coalesced events can bridge a stalled frame").
This confirms `tracking_present_interval_ms` only ever samples "frames a
motion input actually reached," which is why its filtered p95 tracks the
*raw* presentation p95 so closely (section 0) -- but it is downstream of,
not competing with, H1: the burst structure explains which frames get
counted, not why the counted frames' presentations are 2-4 periods apart.
Real-finger acceptance data (`kernel-vblank-latch.md`'s 7,598-frame trace,
different UI, real touch input) shows a *clean* p50=19.2ms/p90=38.3ms
distribution with no 57ms tail reported -- consistent with a touchscreen's
much higher native sampling rate feeding the same underlying
render/commit pipeline far more continuously than the synthetic harness
does, and *not* evidence against H1 (that trace did not filter to
motion-carrying frames the way `tracking_present_interval_ms` does).

## 2. Board commands

Read-only throughout; see `tools/measure-panel-refresh.sh` and
`nix/panel-refresh-probe.c` for exactly which ioctls/files are touched.

```sh
# Build and stage the vblank probe (once; libdrm is already cached for
# riscv64 in this tree's nix store from other probes).
nix build .#panel-refresh-probe
python3 tools/push-file.py --src result/bin/panel-refresh-probe \
  --dest /tmp/panel-refresh-probe
# push-file.py does not chmod +x; do it over the console once pushed:
python3 tools/capture-boot.py --out /tmp/chmod.txt --seconds 10 --kick \
  --expect 'root@nixos' --send 'chmod +x /tmp/panel-refresh-probe'

# Stage the measurement script itself the same way (or run it inline via
# --send if the operator prefers not to push a second file):
python3 tools/push-file.py --src tools/measure-panel-refresh.sh \
  --dest /tmp/measure-panel-refresh.sh

# 2a. IDLE capture: desktop up, no gesture running. Confirms H4 (IRQ rate)
# and gives the baseline vblank interval distribution with nothing else
# competing for the pipeline.
python3 tools/capture-boot.py --out docs/evidence/card-shell/frame-budget/idle-capture.txt \
  --seconds 30 --kick --expect 'root@nixos' \
  --send 'sh /tmp/measure-panel-refresh.sh'
python3 tools/parse-panel-refresh.py --input docs/evidence/card-shell/frame-budget/idle-capture.txt

# 2b. DRAG capture: run the existing card-shell benchmark's injected drag
# harness (H1/H6's actual workload), then this script immediately after,
# so the IRQ-rate window and the existing benchmark's own numbers describe
# the same general system state (one serial link cannot run both at once):
python3 tools/card-shell-benchmark.py --board \
  --input <telemetry from the board run> --output /tmp/card-drag-report.json
python3 tools/capture-boot.py --out docs/evidence/card-shell/frame-budget/drag-capture.txt \
  --seconds 30 --kick --expect 'root@nixos' \
  --send 'sh /tmp/measure-panel-refresh.sh'
python3 tools/parse-panel-refresh.py --input docs/evidence/card-shell/frame-budget/drag-capture.txt
```

## 3. Decision table: what each result means

| Result | Supports | Decision |
| --- | --- | --- |
| Idle VO IRQ rate ~52.2Hz, idle vblank interval p50 about 19.16ms with no 3x tail | H1/H4-refuted (hardware/IRQ is fine at idle) | Expected; proceed to 2b |
| Idle VO IRQ rate ~17.4Hz (1/3 of expected), or idle vblank interval itself quantized to ~57ms with nothing rendering | H4 confirmed after all (would contradict section 0's desk-check and needs to be reconciled -- re-check the IRQ line match in `/proc/interrupts` first) | Reopen H4; likely (b) accept or (c) driver fix depending on whether it is IRQ-generation or IRQ-delivery |
| Drag-window vblank probe (run just after the benchmark) still shows clean ~19.16ms samples even though the benchmark's own presentation feedback shows 57ms gaps for the same run | H1 strongly confirmed: raw hardware vblank is fine; the *compositor's own commit cadence* is what's quantized | (c) targeted fix: pipeline/queue atomic commits in the card-shell path (or in `canaan_crtc_atomic_flush`) so a slow render doesn't serialize the next commit behind a full extra vblank; re-measure, do not accept yet |
| `frame_update_cpu` stays under budget (as it already does, 17-24ms p95) but presentation p95 still lands 3-4 buckets out regardless of workload changes | H1, tail source is NOT render cost (something else in the pipeline -- scheduling, lock contention, DDR contention per `max-render-time-fix.md`) | (a)/(c): profile the commit path itself (workqueue latency for `atomic_commit_tail`, or `canaan_vo_flush_config`'s lock/timing) rather than more Pixman tuning |
| Card-count scaling (57ms at 1-card vs 77ms at 2-card, as short-trace already shows) reproduces cleanly and correlates with render-cost p95 crossing each period boundary | H1 fully confirmed, mechanism is exactly "render/commit overrun rounds up to the next vblank" | (b) can be recorded as measured-and-accepted only if the coordinator decides the *overrun rate*, not a hidden panel limit, is what's being accepted -- state that distinction explicitly in the acceptance record, since it is a different (and more fixable-sounding) claim than "the panel can't go faster" |
| DSI PHY or `canaan_vo_flush_config` timing shows measurable correlation with the *slow* frames specifically (H2) | H2 as a contributing/quality issue, separate from H1 | File as its own follow-up (the flicker fix, already scoped in `kernel-vblank-latch.md`), does not by itself resolve the budget question |

## 4. What this does not claim

- It does not prove H1 outright; section 0's math is consistent with it and
  rules out a fixed 3x hardware divisor, but only the board vblank-sequence
  correlation (section 2b) confirms *where in the pipeline* the extra
  vblanks are spent.
- It does not re-open the GPU/VGLite decision
  (`docs/evidence/card-shell/renderer-decision.md`) or propose a specific
  code fix for H1/H2; that is exactly the "(c) continue targeted
  optimization" branch the parent proposal reserves for the coordinator
  once a real, addressable target is identified.
- `tools/measure-panel-refresh.sh` and `nix/panel-refresh-probe.c` are
  read-only diagnostics; they were exercised on a host DRM node during this
  investigation only to confirm the tool doesn't crash and its mode/vblank
  parsing is correct (`DRM_IOCTL_WAIT_VBLANK` itself returned `ENOTSUP` in
  that sandboxed host environment, which is expected and unrelated to the
  board). No board access occurred as part of this investigation.
