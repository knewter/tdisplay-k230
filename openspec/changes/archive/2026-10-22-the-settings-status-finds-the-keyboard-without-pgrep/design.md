## Context

`k230-settings status` routes to the native helper (`nix/settings-status.c`,
userspace). Its keyboard check forked
`pgrep -u UID -x wvkbd-mobintl` with a 3 s deadline. A board profile of 10
injected shade pulls attributed 789 ms of sampled CPU to `pgrep`, against
282 ms for the helper itself.

## Goals / Non-Goals

- **Goal:** the same keyboard capability answer, without a child process.
- **Non-goal:** raising the shade's presented frame rate. Measurement shows
  that rate is bound by sway's full-screen repaint plus the client draw on the
  one CPU.

## Decisions

- **Scan `/proc` in the helper.**
  - It reads `comm`, then the second `Uid:` field of `status` for a name match.
  - That matches `pgrep -x` (the whole process name) and `pgrep -u` (the
    effective UID).
  - A process that exits mid-scan is skipped.
  - An unreadable `/proc` reports the keyboard as unavailable, as a failed
    `pgrep` did.
- **The deadline goes.** There is no child left to time out.
- **Rejected options:**
  - lowering `pgrep`'s priority: it still costs the CPU;
  - caching the answer: status reads are fresh by contract;
  - keeping `pgrep` but passing a literal pattern: the regex setup and the
    full `/proc` read remain.

## Risks / Trade-offs

- If wvkbd ever renamed its process, both the old and the new check would miss
  it. The Python oracle keeps using `pgrep` for actions, and the conformance
  test still compares the two through the shared JSON.
