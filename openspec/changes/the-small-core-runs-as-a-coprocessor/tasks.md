## 1. Source and register grounding (host/documentation only, no board)

- [x] 1.1 Read K230 TRM's mailbox description (originally cited as section 2.4; it is section 2.9) into a register
  map (base address, per-direction data/status/IRQ offsets) or record that
  the TRM does not publish one. Do not write a mailbox driver against a
  guess. Verify with a new section in `docs/research/second-core-feasibility.md`
  citing the exact TRM page/section, reviewed against the existing
  `th1520-mailbox.c` layout only as a naming cross-check, not a register
  source (source/document proof, no board or code).
  DONE 2026-10-12 (document proof). The TRM does publish the map, in
  **section 2.9 Mailbox** (not 2.4, which is the interrupt table): base
  `0x9110_4000`, interrupt-count groups, 128 interlock registers, sources
  93-96. Recorded in `docs/research/second-core-feasibility.md` ("TRM
  mailbox register map"), with the file hash, PDF pages and the UNVERIFIED
  items (group-to-line routing, lock semantics, CPU0 PLIC wiring). No driver
  written against it.
- [x] 1.2 Record, in one place, the exact reset-controller consumer binding
  this change will use: `resets = <&sysctl_reset 0x4 0 12 0>;` against
  `sysctl_reset@91101000` (`canaan,k230-sysctl-reset`,
  `include/dt-bindings/reset/canaan-k230-reset.h`
  `K230_RESET_CPU0_*` macros), and decide whether the CPU0 vector register
  at `sysctl_boot@91102000` offset `0x100` gets its own small syscon node or
  a private `ioremap` in the new driver, citing the precedent
  (`drivers/reset/reset-k230.c`'s own `ioremap` of the same block for its
  restart path) either way. Verify with a committed decision note under
  `docs/evidence/second-core/` and `openspec validate
  the-small-core-runs-as-a-coprocessor --strict` (document proof, no board
  or code).
  DONE 2026-10-12 (document proof). Superseded for the mainline kernel: the
  vendor-tree binding named above does not exist there. Decision:
  `resets = <&rst RST_CPU0>`, `.reset`-only (pulse; assert/deassert are
  `-EOPNOTSUPP`), vector at `0x91102100` mapped privately from the node's
  own `reg` (no syscon), never request `RST_CPU1`. Note and citations:
  `docs/evidence/second-core/mainline-reset-binding-decision.md`. Verified
  with `openspec validate the-small-core-runs-as-a-coprocessor --strict`.
- [x] 1.3 Confirm whether QEMU's `k230` machine (single modeled core,
  described as "the little core (c908)") can boot a standalone,
  Linux-free CPU0 firmware image directly, without the normal boot chain,
  as a possible QEMU evidence class for step 2. Record the exact invocation
  tried and its result, including a firm "no" if the machine cannot be
  targeted that way. Verify with the committed transcript under
  `docs/evidence/second-core/` (host/QEMU proof only; this task makes no
  board claim).
  DONE 2026-10-12 (QEMU proof only). A standalone image boots with
  `-M k230 -bios none -device loader,...,cpu-num=0`; `-kernel` paths are
  refused. One modeled hart; no CPU release or cache model. Transcript:
  `docs/evidence/second-core/qemu-standalone-cpu0.md`.

## 2. Recovery route (rehearsal waived; fallback confirmed)

- [x] 2.1 WAIVED, NOT PERFORMED: the external SD-card-reader recovery
  rehearsal originally specified here and in
  `docs/closeout/second-core-plan.md`'s step 1, and left open by
  `the-system-runs-on-both-cores` tasks 2.1/2.2, is waived by the operator's
  2026-09-28 decision: "we can easily fix the sd card damn. don't worry
  about recovery we've literally done that fine already before. i don't
  want to do a heartbeat test on a spare card." No disposable/spare card is
  required for any heartbeat or coprocessor board step in this change or
  either parent; every board step runs on the normal card. The fallback
  recovery route for a failed or hung release is the already-proven U-Boot
  one-shot boot from `boot-prev`
  (`docs/evidence/card-shell/bottom-band-flicker/kernel-patch-boot-panic.md`)
  or `ums`/flash reimaging (`docs/uboot-ums.md`) — not a rehearsed
  external-reader restore. This does not waive per-write authorization:
  each board step that writes a CPU0 reset, vector, or reset-controller
  register still needs the user's explicit authorization at the time it
  runs (see tasks 3.3, 5.1, 6.2 below).

## 3. Step zero: echo/ping over a polling shared-memory ring

- [x] 3.1 Extend `tools/small-core-heartbeat.{S,ld}` (or a sibling file
  under `tools/`) into a scalar RV64 payload that polls a request slot in
  its scratch pages, echoes it into a response slot, and issues the pinned
  `l2cache.ciall` encoding after every write, with a host check for entry
  point, footprint, absence of V instructions, and the new poll/echo
  instruction sequence. Verify with a new
  `bash tools/test-small-core-coprocessor-echo.sh` (host binary proof, no
  board), following the existing `test-small-core-heartbeat.sh` method.
  DONE 2026-10-12 (host binary proof, no board). `tools/small-core-echo.{S,ld}`
  (224 bytes, load address a single linker constant, slot layout in the `.S`
  header) and `bash tools/test-small-core-coprocessor-echo.sh`: PASS.
- [x] 3.2 If task 1.3 found a usable standalone QEMU boot path, boot this
  firmware there and drive the request/response ring from the QEMU monitor
  or a companion harness to prove the poll/echo state machine logically,
  independent of any board-only coherency question. Skip with a recorded
  reason if 1.3 found no usable path; do not treat a skip as a task
  failure. Verify with a committed transcript (QEMU proof only; not a
  substitute for task 3.3).
  DONE 2026-10-12 (QEMU proof only; not a substitute for 3.3). Five requests
  answered correctly, a resent sequence number ignored, heartbeat independent:
  `docs/evidence/second-core/qemu-standalone-cpu0.md`
  (`tools/small-core-qemu-probe.py`).
- [x] 3.3 **BOARD-GATED. AUTHORIZATION-REQUIRED.** Load the
  inspected payload via the pinned `boot_baremetal 0` sequence exactly as
  the heartbeat runbook already does, write at least three distinct request
  values from the U-Boot prompt, and read back three correct, freshly
  produced responses (not a stale cached value), then restore normal boot.
  Runs on the normal card; recovery, if needed, is by the fallback routes
  named in task 2.1 (no disposable card). Verify with a timestamped board
  transcript committed under `docs/evidence/second-core/` (physical CPU0
  execution proof; any hang, static response, or wrong echo fails this task).
  Procedure, expected cells and payload hash/CRC: `docs/evidence/second-core/echo-runbook.md`.
  DONE 2026-10-12 (physical board, serial transcripts; operator "Yes, go"):
  four distinct requests answered correctly by CPU0 (`11111112/eeeeeeee`,
  `deadbef0/21524110`, `00000000/00000000`, `12345679/edcba987`), each line
  read once after its request, never-requested line's `rsp_seq` 0, counters
  `served=4 last_seq=4`, CPU1 prompt alive, Linux restored. Required the
  `--evict` cache workaround (U-Boot has no `dcache` command; without it
  release 2 was 0/4, inconclusive). Evidence:
  `docs/evidence/second-core/echo-physical-2026-10-12/README.md`.

## 4. Reserved memory and a read-only remoteproc driver skeleton

- [x] 4.1 Add a `reserved-memory`/`no-map` node for the CPU0 firmware image
  and its shared ring to the experimental device tree, sized and placed to
  avoid the live 1 GiB DRAM window's existing framebuffer reservation and
  to formally reserve the heartbeat/echo scratch range from ordinary Linux
  allocation, following the precedent at `nix/dts/k230-tdisplay.dts:47-57`.
  Verify with `nix build .#deviceTree` and a decompiled `reserved-memory`
  node check (DT build proof, not board).
  DONE 2026-10-12 (DT build proof): on the mainline tree, not the vendor
  `.#deviceTree` (per the binding decision): opt-in
  `.#deviceTreeMainlineDrmHotplugCpu0` carries `cpu0-firmware@7000000`
  (1 MiB, `no-map`) and `remoteproc@91102100`; decompiled and checked; the
  daily tree's derivation is unchanged. Evidence: `docs/evidence/second-core/remoteproc-skeleton-build.md`.
- [x] 4.2 (Mainline binding per `docs/evidence/second-core/mainline-reset-binding-decision.md`: `&rst`/`RST_CPU0`, own `reg` for `0x91102100`, needs `CONFIG_REMOTEPROC`.) Write a minimal K230 remoteproc driver skeleton: it binds to a new
  DT node, requests the CPU0 line from `&sysctl_reset` via
  `devm_reset_control_get_exclusive()`, maps the reserved region from task
  4.1, and exposes read-only status (whether the reset-controller reports
  CPU0 held in reset) through the standard `remoteproc` sysfs/`state`
  interface. It performs **no** reset, vector, or power write in this task.
  Verify with a kernel module build against the pinned kernel tree and a
  host-side `checkpatch.pl`/build-log proof (cross-build proof, not board).
  DONE 2026-10-12 (cross-build proof): `nix/patches/mainline/k230_cpu0_rproc.c`
  built in-tree as a module by `.#kernelMainlineDrmRproc` (daily kernel plus
  `CONFIG_REMOTEPROC`); checkpatch `--strict` clean; refuses any reset but
  `RST_CPU0`; links no reset write. Reset "held" status is reported as
  `reset_control_status()`'s code (reset-k230.c has no `.status`). Evidence: `docs/evidence/second-core/remoteproc-skeleton-build.md`.
- [x] 4.3 Cite, in the driver's kernel-doc or a comment, why no mailbox
  hardware is used yet (task 1.1's TRM gap) and how the poll-mode
  `txdone_poll` mailbox path is expected to attach once a firmware image
  actually speaks virtio/rpmsg (design.md Decision 1/5). Verify with
  `openspec validate the-small-core-runs-as-a-coprocessor --strict`
  (document-consistency proof).

  DONE 2026-10-12: the driver's header comment; `openspec validate --strict`
  passes. Evidence: `docs/evidence/second-core/remoteproc-skeleton-build.md`.
## 5. Linux-driven runtime start/stop of CPU0

- [ ] 5.1 **BLOCKED on 3.3, 4.2. BOARD-GATED. AUTHORIZATION-REQUIRED.**
  Extend the driver from 4.2 to perform the actual release sequence
  (reset-vector write at `sysctl_boot+0x100`, then
  `reset_control_deassert()` on the CPU0 line) with the echo firmware from
  task 3 loaded into the reserved region from task 4.1, triggered from
  Linux userspace (e.g. the standard `remoteproc` `state` sysfs attribute),
  and prove a request/response round trip with Linux fully booted and the
  shell responsive. Runs on the normal card; recovery, if needed, is by the
  fallback routes named in task 2.1 (no disposable card). Verify with a
  board console transcript and Linux dmesg/sysfs capture committed under
  `docs/evidence/second-core/` (physical Linux-coexistence proof).
- [ ] 5.2 **BLOCKED on 5.1.** Extend the same driver's stop path
  (`reset_control_assert()` on the CPU0 line only) and prove CPU0 parks
  again without a board reset, with Linux still running and the shell still
  responsive throughout. Verify with the same transcript style as 5.1,
  showing the stop, a repeated start, and a final stop (physical proof of
  restart-without-reboot).
- [ ] 5.3 **BLOCKED on 5.2.** Directly test design.md's Decision 4 inference
  — that asserting/deasserting only the CPU0 reset-controller line does not
  disturb CPU1/Linux — under repeated cycles (at least three) and under a
  concurrent Linux workload (e.g. the shell compositor active), rather than
  accepting a single clean run. Verify with a board transcript recording
  Linux responsiveness and any error/hang across all repeats (physical
  proof; a single success does not close this task per this project's
  repeated-measurement standard).

## 6. First useful workload: a CPU0 liveness watchdog for Linux

- [ ] 6.1 Extend the firmware from task 3 (or a sibling image) so CPU0
  polls a Linux-incremented liveness counter in the shared ring and, if it
  stops advancing within a documented budget, writes a fault record
  (last-seen counter value and a bounded amount of context) into a second
  reserved page, then **continues polling** — it SHALL NOT itself write any
  reset, power, or vector register in this task. Verify with a host check
  of the new logic's disassembly and the absence of any reset/vector
  register address in it (host proof, no board).
- [ ] 6.2 **BLOCKED on 5.2, 6.1. BOARD-GATED. AUTHORIZATION-REQUIRED.**
  Deliberately stop the Linux-side liveness writer under a controlled test
  (not an actual system hang) and prove CPU0 detects the stall within the
  documented budget and writes a correct fault record, readable after a
  manual, operator-initiated recovery. Verify with a board transcript
  showing the deliberate stop, the recorded fault content, and the manual
  recovery, committed under `docs/evidence/second-core/` (physical
  detection proof). **Non-goal, not a task in this change:** CPU0 asserting
  any reset automatically in response to a detected stall.
