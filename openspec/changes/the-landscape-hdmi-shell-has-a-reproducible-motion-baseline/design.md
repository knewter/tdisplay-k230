## Context

See proposal.md. The installed source is 221bbcf34a276a939356e5a6af9bfb124af9896a;
the observed output is HDMI-A-1, 1280×800 normal, scale 1, about 59.91 Hz.
The portrait capture/parser deliberately require 1920×1080 transform 90.
This change lives in userspace diagnostic tooling only.

## Goals / Non-Goals

Measure the current mode without replacing the portrait acceptance profile.
Retain exact executable/Pixman hashes, input class, collector hash, workload
pacing, timestamps and bounded numeric logs. Do not classify dispatch timing
as contact timing, or presentation feedback as visible photons.

## Decisions

Add an explicit capture profile; keep portrait as the default. Landscape gets
its own manifest schema and report command. Reuse strict per-input/frame join
validation through an explicit geometry argument, while the existing portrait
comparison keeps its original geometry and schema checks. Reject mixed runtime,
geometry and input provenance rather than silently combining traces.

Capture at least 24 alternating center drags each with one and two ordinary
Foot windows. Use the existing paced compositor-IPC injection and label it
literally; IPC adds time to nominal pacing and is not native/uinput input.
Report actual dispatch-to-presentation p95/max and build CPU p95/max without
performance PASS/FAIL budgets. A completed diagnostic is not feature acceptance.
Keep existing user windows, create only a named temporary Foot if needed, and
restore normal Home, benchmark off and the original output state in cleanup.
Do not collect extra board diagnostics during timed gestures.

Rejected: loosening portrait geometry or relabelling landscape as portrait;
changing orientation or resolution for this baseline; optimizing from the old
portrait timing instead of measuring the current mode.

## Risks / Trade-offs

- Missing/truncated records → fail the strict report and retain the failed run.
- IPC pacing depends on compositor load → retain actual timestamps and disclose
  the limit; no cross-input performance claim.
- User state or output changes → stop and preserve their change, never force a
  saved output configuration over concurrent input.
- A temporary app survives interruption → bounded app lifetime plus explicit
  cleanup of only its owned process/window; inspect normal state before release.

## Migration Plan

Land the plan first, then the host-tested profile and report. Under the exclusive
board lock capture the existing installed runtime, restore the normal UI, and
commit evidence. Push master and verify CI plus the exact published revision.
No image deployment, output change or reboot is required for this tooling change.
The portrait proposal remains open with all its outstanding gates.
