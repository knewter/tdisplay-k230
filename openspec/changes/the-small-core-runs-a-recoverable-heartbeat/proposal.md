## Why

**2026-09-28 scope decision — the underlying goal changed, this change
stays open, un-archived, and un-implemented.** The user has now formally
decided the second-core project is a coprocessor (AMP), not Linux SMP; see
`the-small-core-runs-as-a-coprocessor/proposal.md`. That decision makes the
2026-09-26 suspension's *reason* moot — Linux SMP is no longer the target
of any change, so "this proposal doesn't deliver Linux SMP" is no longer a
reason to hold it — but it does **not** by itself un-suspend, implement, or
archive this proposal: per AGENTS.md, only the user's explicit confirmation
does that, and no task below is ticked or run by this note. What actually
happens is that this proposal's ready, physically-proved foundation (its
host-built payload, `tools/small-core-heartbeat.{S,ld}`, and its board-gated
tasks 3.1 then 3.2) is resequenced as `the-small-core-runs-as-a-coprocessor`'s
own stage-1 (recovery rehearsal) and stage-2/3 (echo/ping firmware) tasks,
in that same order — recovery rehearsal first, then the board release. This
proposal's coexistence stage (task family 4: patch the CPU0 SPL parking
loop to run the heartbeat unconditionally after every boot) is **not**
reused as designed: the new change's design.md explains why a
remoteproc-shaped Linux driver that starts and stops CPU0 on demand, once
booted, is simpler and lower-risk than making CPU0 run unconditionally on
every boot via a stage-1/SPL patch. Task family 4 is recorded as superseded
by that change's own reserved-memory/runtime-start-stop stages, not deleted
and not ticked here.

**Suspended 2026-09-26 after user scope correction.** The requested feature
is Linux SMP with both physical cores addressable by one kernel and ordinary
processes schedulable on either. A CPU0 heartbeat or AMP payload does not
meet that request. This proposal and its unchecked tasks remain for history;
do not implement or treat them as a substitute for
`the-system-runs-on-both-cores`.

The handheld currently runs all Linux work on the large physical core, so no
background work can use the small core. Before promising shared Linux
scheduling, an operator needs a recoverable proof that the small core can
execute an independently loaded program while the large core remains under
stage-1 control. The pinned U-Boot source supplies a physical CPU0 reset
vector/release path, while first-hand K230 developer reports say both cores
may report `mhartid` 0; the ordinary two-hart Linux path is therefore unsafe
to assume.

## What Changes

- Prepare a tiny position-independent, scalar CPU0 heartbeat payload and a
  host check of its instructions and memory footprint.
- Ground an exact payload/load/output memory reservation and readback method
  in the pinned stage-1 source before executing the payload.
- On a disposable rollback card, use U-Boot's existing `boot_baremetal 0`
  release with the large core at the U-Boot prompt, then observe a changing
  heartbeat from the small core. Capture the console transcript and restore
  the normal boot path.
- Only after that first physical proof, change the CPU0 SPL parking loop in a
  disposable stage-1 build so CPU0 updates a reserved heartbeat while CPU1
  boots Linux; observe it from the running system and prove normal UI/console
  function and rollback. This is a separate, gated coexistence requirement.
- Treat mailbox IPC, useful background offload, and general peripheral
  ownership as later work. Neither heartbeat is Linux SMP or video
  acceleration.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `system/second-core-readiness`: add a recoverable, explicitly bounded
  physical CPU0 execution proof and distinguish it from shared Linux SMP.

## Impact

The first stage covers a standalone test payload, host inspection tool, narrow
operator runbook and committed board evidence. The second stage changes SPL
and reserves an observation region in the experimental device tree; it does
not alter the normal installed image until physically proved. Both stages
need the physical board, the exclusive console, a disposable rollback card,
and a rehearsed recovery path. Host preparation does not need the board.
