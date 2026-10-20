## Context

See proposal.md for the reported problem. `docs/evidence/interaction-jank/notification-shade/README.md` pins the installed source and bounded F/G comparison. `ServiceWorker` already coalesces and bounds Settings requests; changing its scheduling or schema is unnecessary. `device_settings.py status` reads only carrier, the unique panel backlight, same-user keyboard process availability and the inherited motion preference.

## Goals / Non-Goals

Retain fresh per-request capability reads, labels, unavailable values, ties-to-even brightness rounding, process ownership and action semantics. Avoid adding a resident service or cache. No new performance contract or broader optimization is introduced.

## Decisions

- **Layer: userspace native read-only helper.** Compile a small C executable with the pinned cross compiler and libc only. The existing `k230-settings` wrapper execs it only for the ordinary single-argument `status` operation. Every action, help/invalid invocation and compatibility argument still reaches the unchanged Python implementation. This avoids changing the Rust client, compositor, service protocol or action authority.
- **Parity before speed.** Read the same bounded integer data and first 64 sorted network entries, reject ambiguous backlights and invalid ranges, preserve `access(W_OK)` behavior and round brightness as Python does. Use the existing configured `pgrep -u <real uid> -x wvkbd-mobintl` command with discarded output and a three-second deadline. Its inexpensive native subprocess preserves discovery semantics; no new `/proc` parser is needed. Read motion from the inherited environment. Emit only the existing fixed schema/labels and capability values, never paths or identifiers.
- **Keep existing request lifecycle.** The unchanged worker still provides its four-second deadline, error handling, pending-request coalescing, action follow-up refresh and first-open loading state. No state cache, warmup race or priority adjustment is needed.
- **Qualification.** Compare every native fixture result with the existing Python `Settings.status()` oracle, including malformed/absent capability values, mixed carriers, multiple backlights, permissions and rounding boundaries. Also test real keyboard-child failure/timeout cleanup. On the board compare exact same installed UI/kernel/output, workload and recorder before/after; measure status process cost separately from presentation. Retain every tail and failed capture. A result that does not improve the reported bottleneck is not a performance pass.
- **Alternatives rejected.** Permanent nice 19 can defer fresh state and interact with service deadlines. Gesture-delayed refresh changes freshness and can still compete with a later gesture. Persistent Python adds lifecycle/memory/recovery complexity. Native reads inside the UI worker would duplicate routing/injection behavior; a wrapper-selected helper preserves the existing service boundary.

## Risks / Trade-offs

- Native/Python behavior drift → use Python-oracle fixtures; keep action implementation untouched and document status ownership in both sources.
- Helper still forks native `pgrep` → retain the current bounded availability semantics and measure its actual cost; do not claim zero subprocesses.
- Existing sysfs/process discovery can fail or change during reads → preserve unavailable states and read fresh each request.
- Board root has no unprivileged free bytes → inspect under the exclusive lease before transfer; preserve rollback and unrelated files. Use RAM for temporary traces. No broad GC is part of this change; report a concrete storage blocker if owned disposable data cannot provide space.
- Software trace perturbation → same bounded recorder/workload in each condition, preserve observer cost/limits and keep physical acceptance separate.

## Migration Plan

Validate and land this plan promptly. Implement and prove host parity, cross-build the helper/wrapper and coherent landscape userspace system with the same kernel/compositor/Rust. Acquire board only for storage/preflight and qualification. Preserve the installed persistent system and rollback roots. Transfer only after adequate space is established; record candidate selection separately from installation. Collect bounded before/after proof over protected SSH, restore normal controls, then request the operator's real shade pull. Promote accepted userspace normally, verify exact installed paths and ordinary startup, retain rollback, release reservations and inspect matching CI/Pages. Keep hardware tasks open until the named proof exists.
