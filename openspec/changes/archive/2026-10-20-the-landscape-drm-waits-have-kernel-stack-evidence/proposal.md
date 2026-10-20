## Why

Landscape gestures occasionally pause for about 200 ms. The prior correlated
trace located four reproduced stalls in sleeping DRM ioctls, but did not show
which kernel wait held them. Identify that wait before changing the shell or
hotplug behavior.

## What Changes

- Add bounded userspace tooling for isolated scheduler-triggered kernel stacks,
  with numeric syscall/scheduler correlation, strict source/clock/loss guards,
  address-free symbol export and independent cleanup.
- Qualify the controller on a harmless sleeping process, then run paired
  untraced/stack-traced 24-drag hardware diagnostics; retain an inconclusive
  result if the bounded attempts do not reproduce the wait.
- Commit commands, hashes, safe records, interpretation and verified restoration.

Non-goals: performance/default fixes, poll-disable experiments, a new kernel or
image, renderer changes, portrait geometry, native/glass/optical acceptance.
The physical board is required for stack and workload proof; host fixtures
prove parsing and ownership only.

## Capabilities

### New Capabilities

None. Diagnostic tooling only (`skip_specs: true`).

### Modified Capabilities

None. No accepted shell/display/kernel requirement changes.

## Impact

Userspace tools and evidence, using the running kernel's existing per-instance
tracepoints/stack trigger. Own `tools/landscape-drm-wait.py`,
`docs/evidence/landscape-drm-wait/`, this OpenSpec change, and only necessary
inventory rows for its compressed data. Keep source221/j30, DEBUG, normal
1280×800 HDMI and ordinary Foot unchanged. Preserve all portrait gates.
