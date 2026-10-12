# Physical CPU0 echo/ping runbook (board task 3.3)

**Run on 2026-10-12: PASS with the `--evict` cache workaround ([echo-physical-2026-10-12/README.md](echo-physical-2026-10-12/README.md)).** It follows
[heartbeat-runbook.md](heartbeat-runbook.md), which was run on 2026-10-12
([heartbeat-physical-2026-10-12/README.md](heartbeat-physical-2026-10-12/README.md)).
The operator needs `/dev/ttyACM0` (under `flock -n /tmp/k230-board.lock`) and
the user's explicit authorization for this session, because
`boot_baremetal 0` writes CPU0's vector and reset registers. The 2026-09-28
waiver applies: run on the normal card; recovery is the U-Boot one-shot from
`boot-prev` or `ums`/reimaging, no spare card.

Payload: `tools/small-core-echo.{S,ld}`, 224 bytes (`0xe0`), loaded at
`0x07000000` (`PAYLOAD_BASE`, single linker constant), entry = load address.
Slot page `0x07002000`; layout below and in the `.S` header. Host proof:
`bash tools/test-small-core-coprocessor-echo.sh`. QEMU proof:
[qemu-standalone-cpu0.md](qemu-standalone-cpu0.md). The expected hash/CRC come
from the host build; recompute them and stop if they differ:

| | |
| --- | --- |
| size | 224 bytes (`filesize=e0`) |
| SHA-256 | `2ec68316e7d66a9380701c2011cd02c663ef945826afb30736c44b42017e46cc` |
| CRC32 (`zlib.crc32`, U-Boot `crc32`) | `7492e46f` |

## Slot layout (u32 little-endian unless noted; one 64-byte line each)

| Address | Field | Notes |
| --- | --- | --- |
| `0x07002000` | `req_seq` | nonzero, different from the last served; write it **last** |
| `0x07002004` | `req_value` | write first |
| `0x07002040` | `heartbeat` (u64) | slow counter, advances roughly every 2^19 polls |
| `0x07002048` / `0x07002050` | `mhartid` / `misa` (u64) | `0x0` / `0x800000000094112f` on silicon (QEMU reads `...2d`) |
| `0x07002058` | `magic` | `0x4f484345` |
| `0x0700205c` / `0x07002060` | `served` / `last_seq` | |
| `0x07002100 + 0x40*(seq & 7)` | `rsp_seq`, `rsp_value`, `rsp_inv`, `rsp_served` | `rsp_seq == req_seq` written last; `rsp_value = req_value + 1`; `rsp_inv = ~req_value` |

Response line addresses: seq 1 `0x07002140`, 2 `0x07002180`, 3 `0x070021c0`,
4 `0x07002200`, 5 `0x07002240` (not requested: negative control).

## Why the timing differs from the heartbeat

The heartbeat's 8M-iteration delay (about 2.5 s per count on silicon,
consistent with CPU0 running uncached from reset, not measured) is absent
from the request path. The poll loop is about ten instructions plus an
`l2cache.ciall`; at the heartbeat's measured rate (about 6.4 M instructions
per second) that is a response latency of roughly a millisecond, not
seconds. The `sleep 1` after each request below is generous. If a response
is absent after `sleep 1`, wait a further 3 s once and read again before
calling it a failure. The separate heartbeat (about 2^19 polls per count) is
expected to move on a seconds scale and is read only as a liveness extra.

## Cache caution (unverified, check at the prompt)

CPU1's U-Boot may cache the slot page. A cached CPU1 write may not reach
DRAM, and a cached read may hide CPU0's write. Mitigations in this
procedure: each request has its own response line (first read of every line
happens after it is written), and U-Boot's data cache is checked and, if on,
turned off before use. The vendor `boot_baremetal` also flushes the image
range. On 2026-10-12 this U-Boot had **no** `dcache` command; reading 32 MiB
of unrelated DRAM (`crc32 0x10000000 0x2000000`) after each request write
and before each read evicts CPU1's caches and was required for a result
(`tools/small-core-echo-session.py --evict`). Earlier text: if no
cache-control command exists, record that and treat a wrong or missing
response as inconclusive, not as a CPU0 failure.

## Steps

1. Build and hash on the host; copy to the normal card as
   `/boot/small-core-echo.bin` (as the heartbeat file was); confirm the
   card's `sha256sum` matches the table above.

   ```sh
   SMALL_CORE_OUTPUT_DIR=/tmp/k230-small-core-echo-host bash tools/test-small-core-coprocessor-echo.sh
   ```

2. Warm-reboot Linux, stop autoboot, and at the CPU1 U-Boot prompt run the
   pre-release checks (all read-only):

   ```text
   help boot_baremetal
   help dcache
   dcache
   bdinfo
   printenv mmc_boot_dev_num
   ```

   Stop if `boot_baremetal` is absent or `0x07000000`..`0x07004fff` is not
   clear of U-Boot (`0x3fb35920`..`0x3fffffff` on 2026-10-12). If `dcache`
   reports the data cache ON, run `dcache off`. Record what you did. If the
   data cache cannot be turned off, drop the repeated reads of the status
   line (step 4's second view and step 5's final `md.l 0x7002058 3`) from the
   pass criteria; the four response lines remain valid because each is read
   once, after it is written.

3. Load and verify the payload:

   ```text
   ext4load mmc 1:1 0x7000000 /small-core-echo.bin
   printenv fileaddr filesize
   crc32 0x7000000 0xe0
   ```

   Require `fileaddr=7000000`, `filesize=e0`, CRC `7492e46f`. Never release
   on a mismatch. (Use the `mmc` device and partition the heartbeat session
   used, `1:1`, after confirming `mmc_boot_dev_num`.)

4. Release CPU0 (needs the user's authorization at this moment):

   ```text
   boot_baremetal 0 0x7000000 0x5000
   sleep 1
   md.l 0x7002040 12
   ```

   Expect `magic` `4f484345` at `0x7002058`, `mhartid` `0` at `0x7002048`,
   `misa` `0x800000000094112f` (cells `0094112f 80000000` at `0x7002050`),
   `served` 0. This status line has now been read once; do not rely on a
   second read of it unless the data cache is off.

5. Send four distinct requests, value first and sequence last, with a read of
   the matching response line after each:

   ```text
   mw.l 0x7002004 0x11111111 1
   mw.l 0x7002000 0x1 1
   sleep 1
   md.l 0x7002140 4

   mw.l 0x7002004 0xdeadbeef 1
   mw.l 0x7002000 0x2 1
   sleep 1
   md.l 0x7002180 4

   mw.l 0x7002004 0xffffffff 1
   mw.l 0x7002000 0x3 1
   sleep 1
   md.l 0x70021c0 4

   mw.l 0x7002004 0x12345678 1
   mw.l 0x7002000 0x4 1
   sleep 1
   md.l 0x7002200 4
   ```

   Required `md.l` cells (`rsp_seq rsp_value rsp_inv rsp_served`):

   | Request | Response line |
   | --- | --- |
   | seq 1, `0x11111111` | `00000001 11111112 eeeeeeee 00000001` |
   | seq 2, `0xdeadbeef` | `00000002 deadbef0 21524110 00000002` |
   | seq 3, `0xffffffff` | `00000003 00000000 00000000 00000003` |
   | seq 4, `0x12345678` | `00000004 12345679 edcba987 00000004` |

   Each value is derived from a request written moments earlier and differs
   from every other, so a stale or static line cannot match. Then the
   negative control and final status:

   ```text
   md.l 0x7002240 4
   md.l 0x7002058 3
   echo CPU1_UBOOT_PROMPT_ALIVE
   ```

   The control line's first word (`rsp_seq`) must read `00000000` (never
   answered); its other words are not initialized by the payload. The status cells
   at `0x7002058` must read `4f484345 00000004 00000004` (`magic`, `served`,
   `last_seq`).

6. Optional liveness extra, only with the data cache off: read
   `md.l 0x7002040 2` twice, at least 5 s apart; the 64-bit counter should
   increase. Skip it if the cache is on.

7. Stop: `reset` at the prompt (this halts CPU0 along with everything). Do
   **not** run `boot` while CPU0 executes: it loads `bootargs.txt` at
   `0x7000000`, over the running payload. After the reset, capture the
   restored Linux separately (`nproc`, system store path, UI services), and
   remove `/boot/small-core-echo.bin` only if the operator wants it gone.

## Pass and fail

- **Pass**: step 3 checks match; step 4 identity/magic cells match; all four
  step 5 lines match exactly; the control line's `rsp_seq` is zero; the prompt stays
  alive; Linux restores. The transcript with timestamps goes under
  `docs/evidence/second-core/`, with raw console lines carrying IP
  addresses kept private (as for the heartbeat).
- **Fail**: any wrong value, any line equal to a previous request's, a
  static or zero response with the data cache confirmed off, a hang, or a
  reset. Record the failure as its own run.
- **Inconclusive**: no cache-control command, and responses absent or
  wrong. Do not tick 3.3; say what blocked a conclusion.

## Limits

Proves at most that CPU0 can read a request written by CPU1's U-Boot and that
CPU1's U-Boot can read a fresh response, with Linux not running. It does not
exercise Linux, a non-cacheable Linux mapping, a reserved-memory region,
interrupts, the TRM mailbox, or CPU0 stop/restart.
