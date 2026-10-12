# Physical CPU0 echo/ping, 2026-10-12

Coprocessor task 3.3: requests written from the CPU1 U-Boot prompt into the
slot page, answered by our payload on physical CPU0 (the small C908 core).
Runbook: [../echo-runbook.md](../echo-runbook.md). Driver:
[tools/small-core-echo-session.py](../../../../tools/small-core-echo-session.py).

**Evidence class:** physical board, serial console transcripts (host clock).
No camera, no Linux coexistence.

**Authorization.** The operator chose "Yes, go" on 2026-10-12 for releasing
CPU0 on the normal card, and asked for "the second core bring up". Spare-card
and recovery rehearsal were waived on 2026-09-28 (quoted in the runbook).

## Payload and card

- `tools/test-small-core-coprocessor-echo.sh` (on this branch, rebased onto
  `5c3c5492`) built `echo.bin`: 224 bytes, SHA-256
  `2ec68316e7d66a9380701c2011cd02c663ef945826afb30736c44b42017e46cc`, CRC32
  `7492e46f`, identical to the runbook.
- Copied over SSH to the normal card's `/boot/small-core-echo.bin`; the
  board's `sha256sum` matched.
- Board: installed system `kc3iyr4c…` (the mainline splash default).

## Sessions

All ran under `flock /tmp/k230-board.lock`; each warm-rebooted Linux and
stopped autoboot. U-Boot has **no `dcache` command** (`help dcache` and
`dcache` both print `Unknown command`), so CPU1's data cache could not be
turned off.

| Transcript | Mode | Result |
| --- | --- | --- |
| `dry-run-uboot.txt` | no release | pre-release checks PASS (`filesize=e0`, CRC32 `7492e46f`); Linux back |
| `release-1-missed-uboot.txt` | `--release` | U-Boot prompt not caught; nothing released; Linux back |
| `release-2-no-evict-uboot.txt` | `--release` | CPU0 ran: status line `mhartid=0x0`, `misa=0x800000000094112f`, magic `4f484345`. **0/4 responses**, `served=0`. Inconclusive per the runbook (no cache control): CPU1's `mw.l` stores can stay in CPU1's cache |
| `release-3-evict-uboot.txt` | `--release --evict` | **4/4 responses correct**, counters `4f484345 00000004 00000004`; the tool reported FAIL only on the control line (see below) |
| `release-4-evict-pass-uboot.txt` | `--release --evict` | **ECHO VERDICT: PASS**: 4/4, control `rsp_seq` 0, counters 4/4, prompt alive; Linux back |

`--evict` runs `crc32 0x10000000 0x2000000` (a read of 32 MiB of unrelated
DRAM) after each request's two `mw.l` and before every `md.l`, so CPU1's
caches write the request back and drop any stale copy of the slot page.
That one change took the result from 0/4 to 4/4, which is the evidence that
CPU1's cache, not CPU0, held the requests in release 2.

Release 4, responses read once each after `sleep 1` (host stamps):

| t | request | response line | read |
| --- | --- | --- | --- |
| 26.28 s | seq 1, `0x11111111` | `0x07002140` | `00000001 11111112 eeeeeeee 00000001` |
| 31.34 s | seq 2, `0xdeadbeef` | `0x07002180` | `00000002 deadbef0 21524110 00000002` |
| 36.41 s | seq 3, `0xffffffff` | `0x070021c0` | `00000003 00000000 00000000 00000003` |
| 41.48 s | seq 4, `0x12345678` | `0x07002200` | `00000004 12345679 edcba987 00000004` |

Each value is a function of a request written moments before and differs
from every other line, so no stale or static content can match.

**Negative control, corrected.** The runbook said the never-requested line 5
(`0x07002240`) must read all zeros. The payload (`small-core-echo.S`)
zeroes only each response line's `rsp_seq` word at start, so the other
three words are whatever DRAM held: releases 3 and 4 read
`00000000 ffffffff 03bca868 ffffffff`, release 2 `00000000 00000002 00000000
00000000`. "Not answered" is `rsp_seq == 0`, which holds in every run. The
driver's check was changed to that after release 3 and release 4 was run
with it; the runbook is corrected to match.

## Limits

CPU0 talks to CPU1's U-Boot through DRAM with explicit cache maintenance on
both sides, Linux not running. Not shown: a Linux-side mapping, reserved
memory, interrupts or the TRM mailbox, CPU0 stop/restart, or latency (the
heartbeat field stayed 0 within these ~25 s, consistent with the
expensive per-poll `l2cache.ciall`; not measured).
