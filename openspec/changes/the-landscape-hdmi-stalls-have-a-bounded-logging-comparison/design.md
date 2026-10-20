## Context

See proposal.md and `docs/evidence/landscape-hdmi-baseline/README.md`.
Preflight found the installed source 221bbcf3 compositor running with `-d`,
stdout/stderr attached to journald, and no Pixman draw/CPU-frame/touch-route
trace flags. Neither `strace` nor `perf` is installed. Sway's pinned
`common/log.c` writes stderr synchronously through stdio; `sway/main.c` selects
both Sway and wlroots log levels from `-d`/`-V`. This supports a controlled
logging-level test, not a conclusion that logging caused the recorded spikes.

## Goals / Non-Goals

Keep the same executable, configuration, output, ordinary Foot workload,
benchmark records and collector. Vary only debug versus INFO verbosity, in
A/B/B/A order, and retain honest inconclusive outcomes. Do not enable a new
renderer, change timing budgets or assert physical acceptance.

## Decisions

Userspace tooling: four runs of 24 direct-IPC drags with one standard startup
Foot, 35 moves/nominal 0.7 s motion and 1.6 s rest. A uses existing `-d`; B uses `-V`,
which retains INFO benchmark input/frame records. Each run restarts the same
shell under a fresh 30 s settling window, including both B runs, to control
startup and leave the journal burst window. Record actual flags, executable/
Pixman hashes, config hash, system identity, output geometry, temperature,
log volume and syscall-free process CPU/scheduler counters outside gestures.
Report per-run p95/p99/max, samples over 100 ms, before/after-submission spans
and complete input/presentation coverage. The 100 ms count describes tails;
it is not a newly accepted physical budget.

The comparison uses one owned runtime service drop-in to replace only the
logging argument of the existing safe Nix-store ExecStart. Preserve all other
arguments and environment. A separate 900 s systemd restore timer is armed before
writing the drop-in. Cleanup removes only its exact owned bytes, reloads and
restarts the original service, restores the recorded 1280×800 normal geometry,
requests Home and verifies services/flags/overrides. No persistent profile,
boot files, Nix defaults or kernel changes. Keep protected SSH configuration
outside the repository and never publish arbitrary journal text.

Restarting Sway replaces the startup terminal. Before any restart require only
the standard startup Foot and an idle shell with no running child workload;
abort if another app or active terminal job appears. Record that session
restart occurred. The operator's current layout and permanent system persist.
No other operator may use the board during the reserved comparison.

Rejected: a renderer change before causal evidence; disabling all INFO telemetry
(which would remove the measurements); comparing only one run per mode;
`test-touch` on DRM (headless-only); attaching unavailable profiling tools as
if they had supplied evidence; changing service-wide journal policy permanently.
If spikes persist at INFO, retain their measured boundary and identify the
remaining scheduling/output investigation rather than declare a render fix.

## Risks / Trade-offs

- Rare spikes/order effects → A/B/B/A with 24 drags each; report every run, no
  significance claim or uniform-smoothness assertion from a small sample.
- INFO telemetry still has overhead → this isolates DEBUG logging contribution,
  not all instrumentation overhead or real-contact latency.
- Restart loses app state → require only idle startup terminal and stop on any
  unexpected client/job; preserve current output and permanent image.
- Host disconnect → independently scheduled restoration; do not stop its timer
  until successful cleanup proof exists.
- Log loss → fail strict coverage, preserve rejected logs, never remove missing
  samples to make a run pass. Store only allowlisted numeric diagnostics.

## Migration Plan

Land this tooling-only plan first. Implement and host-test its guards and strict
comparison, reserve the board, capture four runs, restore normal state and
commit the measured conclusion. Publish exact source/evidence revision and
archive only after every named proof exists. No capability delta is needed.
