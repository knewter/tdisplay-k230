## Context

See [proposal](proposal.md) and the committed HDMI board trial. The active
userspace stack is Sway/wlroots/Pixman, logical 1080×1920 on a 1920×1080
monitor with transform 90. Median frame-build CPU time is 441.84 ms in
ARGB8888; normal-transform ARGB8888 is 15.29 ms. RGB565 alone does not fix
the rotated case. The existing scaled mirror cache requires RGB565 and a
normal output transform, so the ARGB8888 comparison avoids that confound.
Orientation still changes scene geometry/damage; the comparison is not a
pixel-identical microbenchmark.

## Goals / Non-Goals

Goals: remove repeated expensive quarter-turn sampling, preserve real client
updates and portrait layout, and demonstrate physical gesture responsiveness.
Changes belong in userspace rendering/input and Nix selection. Kernel changes
are not assumed. Unsupported formats/transforms retain the existing correct
fallback, with a reason in bounded telemetry.

Non-goals: assuming the earlier full-scene GPU rejection also rejects a narrow
rotation operation, or assuming a narrow GPU operation will win. The winning
path must meet pixel, lifetime, performance and recovery gates.

## Decisions

### Profile before selecting the fast path

Capture renderer stacks and subdivision timings during the existing paired
gesture workload. If `perf` sampling is unavailable, use bounded stage counters
and an on-board quarter-turn microbenchmark. Record CPU frequency/governor,
format, transform, renderer identity, dimensions and app count. Avoid attributing
all frame-build time to a routine from the existing coarse trace alone.

The first software candidate is tiled quarter-turn copying in the Pixman
renderer: pre-rotate a source image, then scale/composite without a quarter-turn
affine sampler. Copying on each relevant draw is initially acceptable if measured
cost wins; reuse must explicitly invalidate on texture damage/updates and never
retain stale shared-memory client pixels. If profiling instead favors composing
an unrotated logical frame and rotating once, use that bounded alternative and
document memory/damage costs. Preserve sampling coordinates, clipping and alpha.

A GPU candidate is limited to the expensive copy/rotation boundary and must
count upload, download, synchronization and fallback costs. Prefer the simplest
candidate that passes the measured budget. Do not bypass the existing device
access/isolation rules. If all candidates fail, keep the change open with traces.

### Preserve correctness and client lifecycle

Compare baseline and candidate pixels for asymmetric images, crop, scale,
quarter turns, opacity, rounded clips, damage and both relevant output formats.
Use live changing clients as well as static Foot windows: frame callbacks,
presentation feedback, buffer release and texture updates must remain correct.
Do not quietly hide wallpaper, remove rounded corners or freeze cards to win.

### Treat physical gesture failure separately

The injected bottom-edge swipe succeeded; this does not prove glass input.
Capture contact origin, normalized/output coordinates, event timestamps and the
route rejection reason while an ordinary app is open. Check stale output geometry,
touch-to-pointer ownership and edge-band scaling before changing recognition.
Fix only the proved boundary, then verify top/bottom gestures, app touches and
keyboard/shade coexistence with a real finger. Absolute-touch and opt-in trackpad
input are distinct modes; this change does not complete the trackpad proposal.

### Keep performance claims bounded

For one and two ordinary Foot cards at full portrait HDMI resolution, require
p95 frame-build CPU time at most 33.3 ms and p95 contact-to-present time at most
100 ms, using at least 24 drags per workload. These are proposed acceptance
targets, currently UNVERIFIED. Preserve event clock provenance and per-run
thermal/frequency context; an injected trace proves only injected latency.

## Risks / Trade-offs

- Pre-rotation changes sampling order → exact or explicitly justified pixel
  comparisons before enabling the candidate.
- Cached client memory changes without a new allocation → invalidate on actual
  updates, or keep copying rather than introduce unproved cache reuse.
- Intermediate full-resolution buffers consume memory/bandwidth → record peak
  buffer bytes and include rotation/copy work in total frame cost.
- Faster rendering masks a separate gesture bug → keep the real-glass gate
  independent and record route decisions rather than infer recognition.
- A GPU operation introduces hangs or color differences → bounded timeout,
  correct fallback, reviewed colors and ordinary-service restore proof.

## Migration Plan

Land the proposal early. Add an opt-in candidate compositor build; run host
pixel/lifecycle tests, then a reserved board comparison against the exact baseline.
Only after those pass, select the candidate through repository Nix defaults,
build/install the integrated image and repeat representative app/gesture checks.
Preserve normal panel boot and verify a reboot into it. Commit public evidence,
push master and inspect the exact Pages deployment before archival.
