# Physical CPU0 identity diagnostic and restoration

On 2026-09-27 UTC, the board operator used the exclusive `/dev/ttyACM0`
console to run the default-off SPL diagnostic described in
[`cpu0-identity-trial.md`](cpu0-identity-trial.md). This was a physical
M-mode identity measurement for the Linux SMP investigation, not a second
Linux CPU or an AMP feature. The full serial captures are retained as
protected host files at `/tmp/k230-second-core-trial-boot.private` and
`/tmp/k230-second-core-restored-boot.private`; only selected, non-secret
lines are reproduced here. The host capture file modification times after
the respective boots were `2026-09-27T04:39:17Z` and
`2026-09-27T04:42:10Z`. They are host file times, not board RTC readings.

## Card and recovery bytes

Before writing, Linux identified `/boot` as `/dev/mmcblk1p1` on whole card
`/dev/mmcblk1`, model `SD128`, with 249872384 sectors of 512 bytes. The
SPL slots were the 512 KiB regions at offsets 1 MiB and 1.5 MiB (sectors
2048 and 3072); partition 1 begins at sector 8192. The operator read each
slot with `dd if=/dev/mmcblk1 bs=524288 skip=2` (then `skip=3`),
`count=1`, and verified each backup by a fresh byte comparison and a direct
I/O SHA-256 readback. Both original slots were 524288 bytes and had SHA-256
`25521b917baf3c62d03cb84fe283e47042ca88bde614695c13d4c860fed36241`.

Independent copies were kept on board under
`/var/lib/k230/second-core-identity-20260927/slot-{a,b}.bin` and
off board under `/tmp/k230-second-core-backup.private/slot-{a,b}.bin`.
Both host copies were verified as 524288 bytes with the same SHA-256;
their exact bytes were not committed. The off-board transfer used gzip
and base64 over the serial console, then verified the decoded bytes.
The user confirmed an external microSD reader was available as a fallback,
but no reader-based restoration was performed or claimed.

The diagnostic package was
`/nix/store/6y6v6vyg37r04jjj5057j8yfisxayf69-k230-stage1-packaging/fn_u-boot-spl.bin`:
223412 bytes, SHA-256
`a4c1ae6a038bb3e7326b375f15431c498db5c185dd192cdb4391bd3b265d1cc9`.
The operator transferred it to the board and verified that hash there.
Padding it to one 524288-byte slot produced SHA-256
`e1126e1e3f2da6fdcce4c8307668bda2832a812effdb9811476165366635b0e1`.
Only the two raw SPL slots were written, using `dd bs=524288 seek=2/3
count=1 oflag=direct conv=notrunc,fsync`; each direct readback matched
that padded trial hash. U-Boot proper, environment, OpenSBI, DT, kernel,
rootfs, and partition files were not written by this diagnostic.

## Trial boot and normal restoration

The trial was rebooted and captured with:

```sh
python3 tools/capture-boot.py --dev /dev/ttyACM0 --out /tmp/k230-second-core-trial-boot.private --seconds 180 --kick --expect 'root@nixos' --send reboot --settle 0.30
```

Selected first-hand serial lines:

```text
CPU0_SPL_IDENTITY mhartid=0x0 misa=0x800000000094112f
Platform HART Count       : 1
Boot HART ID              : 0
[    0.015717] smp: Brought up 1 node, 1 CPU
<<< Welcome to NixOS 26.11.20260919.20b1ddd (riscv64) - ttyS0 >>>
```

Linux then reached its root prompt. The normal installed system remained
`/nix/store/7hhr1fp722cq147svn5ni67ar1i66mys-nixos-system-nixos-26.11.20260919.20b1ddd`;
`/sys/devices/system/cpu/online` was `0`, the four `shell`, `shell-ui`,
`shell-session-bus`, and `shell-notifications` services were active, and
`systemctl --failed --no-legend --plain` returned no units.

The operator then restored **both** original slots from the on-board
backups with `dd bs=524288 seek=2/3 count=1 oflag=direct
conv=notrunc,fsync`. Direct I/O readback of each slot again gave SHA-256
`25521b917baf3c62d03cb84fe283e47042ca88bde614695c13d4c860fed36241`.
The restored reboot used the same capture command with output
`/tmp/k230-second-core-restored-boot.private` and produced:

```text
U-Boot SPL 2022.10 (Oct 03 2022 - 19:25:32 +0000)
Platform HART Count       : 1
Boot HART ID              : 0
[    0.015726] smp: Brought up 1 node, 1 CPU
<<< Welcome to NixOS 26.11.20260919.20b1ddd (riscv64) - ttyS0 >>>
```

The restored boot reached its root prompt with **no**
`CPU0_SPL_IDENTITY` line. Afterward the same installed system path, CPU
online mask `0`, four active shell services, zero failed units, and both
original slot SHA-256 values were checked again through the live console.
The protected verification output is
`/tmp/k230-second-core-restored-verification.private`.

The physical CPU0 SPL sampled `CSR.MHARTID=0` and
`CSR.MISA=0x800000000094112f`. The current CPU1-side OpenSBI reports one
logical HART numbered 0, but this experiment did **not** read physical
CPU1's `mhartid` CSR. It does not establish a unique two-hart mapping,
physical CPU0 interrupts/timers, shared cached-memory/atomic coherence,
or Linux SMP operation. Those gates remain open.

As a separate read-only observation on the restored image, `perf` was
absent from `PATH` and `/run/current-system/sw/bin/perf`, while
`/proc/config.gz` reported `CONFIG_PERF_EVENTS=y`,
`CONFIG_FRAME_POINTER=y`, `CONFIG_RISCV_PMU=y`, and `CONFIG_FTRACE=y`.
`/sys/bus/event_source/devices` listed `cpu`, `kprobe`, `software`,
`tracepoint`, and `uprobe`. The protected raw output is
`/tmp/k230-second-core-perf-readonly.private`; no sampling was run.
