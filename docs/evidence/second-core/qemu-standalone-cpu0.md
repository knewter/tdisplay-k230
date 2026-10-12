# QEMU `k230` machine and standalone CPU0 payloads (tasks 1.3 and 3.2)

**Evidence class: QEMU only, run 2026-10-12 on the host (QEMU 11.1.0). No
board, no serial port, no reset or vector write.** Nothing here shows what
CPU0 does on silicon.

## Task 1.3 answer

**Yes, with `-bios none` and a `loader` device; no with `-kernel`.**

| Invocation | Result |
| --- | --- |
| `qemu-system-riscv64 -M k230 -bios none -device loader,file=BIN,addr=0x7000000,cpu-num=0` | Runs. The loader device sets hart 0's PC to `0x07000000`; both `heartbeat.bin` and `echo.bin` execute in M-mode. |
| `-M k230 -bios none -kernel BIN` | Refused: `K230 direct boot requires OpenSBI firmware; omit -bios none or pass OpenSBI with -bios` |
| `-M k230 -kernel BIN` | Refused: `K230 direct boot requires -dtb` |
| `-M k230` with no image | Hart 0 starts at the modeled boot ROM, `pc 0x91200000`. |

What the model covers (from `info cpus`, `info mtree`, `info registers`):

- **One hart**: `CPU #0 model=thead-c908`, `mhartid 0`. It is described as
  the small core, but there is no second CPU and no way to start one.
- RAM is `0x0`-`0x7fffffff` (2 GiB; the board has 1 GiB), so `0x07000000`
  is ordinary RAM. `misa` reads `0x800000000094112d`; the board's CPU0 read
  `0x800000000094112f` (bit 1, B, differs), so the model is not the same ISA
  string as the silicon.
- The system-control blocks `cmu`, `rmu` (`0x91101000`), `boot`
  (`0x91102000`), `pwr` and `ipcm` (`0x91104000`, the TRM mailbox block) are
  listed as `prio -1000` i/o regions, i.e. placeholder windows. This
  project did not test them, and nothing implies they model CPU release,
  the vector register or the mailbox. The CPU0 release sequence cannot be
  rehearsed here.
- `l2cache.ciall` (`0x0170000b`) executes without a trap. QEMU has no cache
  model, so it is a no-op here; every cache-contract question stays a
  board question.
- Timing is host time under TCG and says nothing about the board's ~2.5 s
  uncached loop.

## Harness

`tools/small-core-qemu-probe.py` starts QEMU with the loader device, then
reads and writes guest RAM through QEMU's gdbstub (`m`/`M` packets, the VM is
halted around each access) and prints `info cpus`, `info registers` and `xp`
through QMP. It exits non-zero on failure.

## Heartbeat (existing payload, 80 bytes, SHA-256 `11d675ac...ba133`)

```text
$ python3 tools/small-core-qemu-probe.py heartbeat heartbeat.bin
# command: qemu-system-riscv64 -M k230 -bios none -display none ... -device loader,file=heartbeat.bin,addr=0x7000000,cpu-num=0
# qemu version / cpus:
11.1.0
* CPU #0: thread_id=1404405 model=thead-c908
   priv          M
   pc            7000044
   misa          800000000094112d
   mhartid       0000000000000000
# xp /8wx 0x7002000 (initial)
07002000: 0x00000053 0x00000000 0x00000000 0x00000000
07002010: 0x0094112d 0x80000000 0x00000000 0x00000000
counter @0x7002000 = 123
counter @0x7002000 = 161
counter @0x7002000 = 200
mhartid word = 0x0, misa word = 0x800000000094112d
RESULT: PASS counters strictly increase
```

## Echo payload (task 3.2)

`echo.bin`: 224 bytes, SHA-256
`2ec68316e7d66a9380701c2011cd02c663ef945826afb30736c44b42017e46cc`, CRC32
`7492e46f` (built by `bash tools/test-small-core-coprocessor-echo.sh`).
Slot layout: [../../../tools/small-core-echo.S](../../../tools/small-core-echo.S).

```text
$ python3 tools/small-core-qemu-probe.py echo echo.bin
# command: qemu-system-riscv64 -M k230 -bios none -display none ... -device loader,file=echo.bin,addr=0x7000000,cpu-num=0
# qemu version / cpus:
11.1.0
* CPU #0: thread_id=1404235 model=thead-c908
   priv          M
   pc            7000064
   misa          800000000094112d
   mhartid       0000000000000000
# xp /8wx 0x7002000 (initial)
07002000: 0x00000000 0x00000000 0x00000000 0x00000000
07002010: 0x00000000 0x00000000 0x00000000 0x00000000
magic = 0x4f484345 (expect 0x4f484345), mhartid = 0, misa = 0x800000000094112d
req seq=1 value=0x11111111 -> rsp_seq=1 value=0x11111112 inv=0xeeeeeeee served=1  (0.021s poll) ok
req seq=2 value=0xdeadbeef -> rsp_seq=2 value=0xdeadbef0 inv=0x21524110 served=2  (0.020s poll) ok
req seq=3 value=0xffffffff -> rsp_seq=3 value=0x00000000 inv=0x00000000 served=3  (0.020s poll) ok
req seq=9 value=0x00000000 -> rsp_seq=9 value=0x00000001 inv=0xffffffff served=4  (0.020s poll) ok
req seq=4 value=0x12345678 -> rsp_seq=4 value=0x12345679 inv=0xedcba987 served=5  (0.021s poll) ok
re-sent seq=4 with new value: served stays 5 -> ignored (ok)
heartbeat words: [483, 620]
# xp: request line, then status line
07002000: 0x00000004 0x55555555 0x00000000 0x00000000
07002010: 0x00000000 0x00000000 0x00000000 0x00000000
07002040: 0x0000026c 0x00000000 0x00000000 0x00000000
07002050: 0x0094112d 0x80000000 0x4f484345 0x00000005
RESULT: PASS
```

The final `xp` lines show the request line (`req_seq=4`, `req_value=0x55555555`
left by the resend that was correctly ignored) and the status line
(heartbeat `0x28d`, magic `0x4f484345`, served count 5 at `+0x5c`).

## What this proves and does not

Proves, in QEMU: the poll/serve state machine (a new `req_seq` is answered
once with `value+1`, `~value` and a served count; `rsp_seq` is written last;
32-bit wrap works; a resent sequence number is ignored; `seq & 7` selects
distinct response lines, seq 9 reusing seq 1's line); the heartbeat advances
independently of requests; the slot layout decodes with `xp`.

Does not prove: anything about silicon, cache behavior, CPU1-visible
freshness, the 2.5 s-per-8M-loop uncached speed, release via `boot_baremetal`,
or the latency of a poll with `l2cache.ciall` on the real core. The
latency column above is the harness's polling interval, not a CPU0 figure.
Board task 3.3 stays open: [echo-runbook.md](echo-runbook.md).
