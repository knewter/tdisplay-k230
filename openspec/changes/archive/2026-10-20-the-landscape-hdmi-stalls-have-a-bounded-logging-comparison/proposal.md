## Why

The current landscape HDMI diagnostic recorded five 185–277 ms response
samples despite only about 4–5 ms of frame-build CPU work. Debug logging is
currently enabled and a prior capture lost journal messages, so selecting a
rendering optimization now would risk fixing the wrong boundary.

## What Changes

- Add a bounded comparison of the same installed compositor with diagnostic
  logging controlled, preserving 1280×800 normal HDMI and the input workload.
- Keep complete input/submission/presentation joins and report latency tails,
  CPU timing, log volume and collection limits for each run.
- Restore the original service, logging, output and normal Home after the trial;
  retain failed runs and a precise measured conclusion, including inconclusive
  results. Change no permanent compositor or image defaults in this diagnostic.

Non-goals: redesigning rendering, changing geometry, lowering quality or budgets,
claiming optical/finger latency, closing portrait gates, unconditionally starting
all deferred drawer/keyboard measurements, or tuning from an unproved cause.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None: diagnostic tooling/evidence only (`skip_specs: true`). The accepted
shell behavior and the separate portrait proposal remain unchanged.

## Impact

Host/board diagnostic tooling and committed evidence under
`docs/evidence/landscape-hdmi-logging/`. This needs the reserved physical board
for comparison, with independent timed restoration before any temporary logging
change. Host parser/guard tests need no board. No kernel, stage-1, Nix image
rebuild or persistent default change is planned.
