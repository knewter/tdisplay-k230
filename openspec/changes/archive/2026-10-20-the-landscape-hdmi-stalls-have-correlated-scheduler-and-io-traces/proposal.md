## Why

The landscape shell still records roughly 180–230 ms response stalls after
DEBUG logging is removed, while frame-build CPU work remains about 5 ms.
The operator needs the delayed boundary identified before choosing a fix;
coarse input/frame timing does not distinguish journal writes, DRM commits
and scheduler waits.

## What Changes

- Capture bounded, correlated scheduler and write/ioctl events for the live
  compositor's main thread in an isolated kernel tracing instance.
- Compare the same installed runtime/workload without and with tracing, record
  tracing overhead, and join complete late input/frame intervals to syscall
  spans and off-CPU/runnable waits on the same monotonic clock.
- Reject dropped/overwritten traces or incomplete clock/frame coverage; keep
  raw trace provenance private and export only numeric diagnostic fields.
- Restore normal Home and remove only the owned tracing instance/timer, leaving
  the existing global tracer, logging level, image and landscape output intact.

Non-goals: a renderer/kernel/image/default change, tracing arbitrary user
programs, claiming real-contact/optical latency, or closing portrait gates.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None: diagnostic tooling and evidence (`skip_specs: true`). No accepted shell
requirement or deferred physical proof is changed.

## Impact

Userspace trace-control/parser tooling and committed
`docs/evidence/landscape-hdmi-stall-trace/` records. The physical board and its
existing tracepoints are required. Host parser/guard tests need no hardware.
No Nix/kernel rebuild, new profiling package or permanent service change.
