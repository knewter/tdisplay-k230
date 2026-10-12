# Physical CPU0 heartbeat, 2026-10-12

First execution of a program of ours on physical CPU0 (the small C908 core),
while physical CPU1 runs U-Boot. Runbook: [../heartbeat-runbook.md](../heartbeat-runbook.md).
Driver: [tools/small-core-heartbeat-session.py](../../../../tools/small-core-heartbeat-session.py).

**Evidence class:** physical board, serial console transcript. No camera,
no Linux coexistence.

**Authorization.** The operator chose "Yes, go" on 2026-10-12 when asked
whether to release CPU0 from reset on the normal card once the payload was
ready. The spare card and recovery rehearsal were already waived on
2026-09-28 (quoted in the runbook).

## Payload and card

- `tools/test-small-core-heartbeat.sh` built `heartbeat.bin`: 80 bytes,
  SHA-256 `11d675ac6a4993c5ea820603a59778993487a478d07b1e30d3e9545ae22ba133`,
  CRC32 `3db6c1eb` (identical to [../heartbeat-host.md](../heartbeat-host.md)).
- Copied over SSH to the normal card's `/boot/small-core-heartbeat.bin`
  (`/dev/mmcblk1p1`, ext4); the board's `sha256sum` matched.
- Board before the sessions: installed system `298a2bf6…`, boot
  `94fd02a1-…`.

## Sessions

All three ran under `flock -n /tmp/k230-board.lock` from the host. Each
warm-rebooted Linux, stopped autoboot, and ran the runbook's checks:
`help boot_baremetal`, `bdinfo`, `printenv mmc_boot_dev_num`,
`ext4load mmc 1:1 0x7000000 /small-core-heartbeat.bin`, `printenv fileaddr
filesize`, `crc32 0x7000000 0x50`.

The pre-release checks passed every time. `boot_baremetal` is present.
`fileaddr=7000000`, `filesize=50` (80 bytes), CRC `3db6c1eb`.
`mmc_boot_dev_num=1`. U-Boot's relocated image, malloc area and stack lie at
`0x3fb35920`–`0x3fffffff` (`lmb` reserved region, `relocaddr`
`0x3ff39000`, `sp` `0x3fb36970`), clear of the payload window
`0x07000000`–`0x07004fff`.

| Session | Command | Result |
| --- | --- | --- |
| [dry run](dry-run-uboot.txt) | checks only, then `reset` | checks PASS; no release; Linux back |
| [release 1](release-1-uboot.txt) | `boot_baremetal 0 0x7000000 0x5000`, pages read 1.2 s apart | counters 1, 1, 2: **FAIL** (not strictly increasing); prompt alive; Linux back |
| [release 2](release-2-uboot.txt) | same, pages read 5 s apart | counters 2, 4, 6: **PASS**; prompt alive; Linux back |

Release 2's first page also reads `mhartid=0x0` and
`misa=0x800000000094112f`. These are written by the payload itself on the
released core, and they match the CPU0 identity measured from CPU0 SPL in
[../cpu0-identity-physical-trial.md](../cpu0-identity-physical-trial.md).

**Why release 1 failed.** The counter advances about once every 2.5 s
(release 2: 2, 4, 6 at roughly 5 s spacing). The payload's ~8M-iteration delay
loop is far slower than the cached-core estimate. That is consistent with
CPU0 running from reset with caches off (instruction fetch from DRAM), but
cache state on CPU0 is not measured here. Readings 1.2 s apart can repeat. The
runbook only requires "at least one second apart", so release 2 used 5 s.
Release 1 stays recorded as a failure of its own run.

**Restored Linux** (SSH, 2026-10-12T20:07:46Z, after release 2's `reset`):
`possible=0`, `present=0`, `online=0`, `nproc` 1, system
`298a2bf6…`, and `shell`, `shell-ui` and `theme-helper` active.

## Limits

- Proves physical CPU0 execution while CPU1 sits at the U-Boot prompt. It
  says nothing about CPU0 running while Linux runs. That is the coexistence
  stage, which needs reserved memory and a Linux-side start.
- Each output page was read once, per the runbook's cache caution. No
  cross-core coherency claim is made.
- CPU0 was stopped by the board `reset`; no stop path was exercised.
- `/boot/small-core-heartbeat.bin` was left on the card (80 bytes) for the
  next stage.
- Raw transcripts, including the console's IP address line, stay in the
  private run directory.
