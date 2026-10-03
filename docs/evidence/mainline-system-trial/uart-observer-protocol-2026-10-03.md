# Opt-in autonomous UART observer protocol (host preparation only)

Worktree `/home/jadams/tmp/k230-mainline-uart-observer`, branch
`mainline-uart-observer`, base `9854479615d2800d53e79cf14939397a93e3fe1f`.
No board/build reservation. Source/host preparation for existing mainline 5b.5;
physical observation and automatic return remain **UNVERIFIED**.

Build output names: `mainline-uart-observer`,
`nixosConfigurations.k230-mainline-uart-observer`,
`toplevel-mainline-uart-observer`, `kernelMainlineUartObserverBootFiles`.
Helper source `nix/mainline-uart-observer/observer.c`, executable
`bin/k230-uart-observer`. Existing/default outputs and controllers stay unchanged.

Retain exact bundle arguments and five qualified controls from the debug plan.
Append precisely three unique volatile identity tokens:
`k230.uobs.nonce=<32 lower hex>`, `k230.uobs.from=<normal boot UUID>`,
`k230.uobs.init=<selected immutable system/init>`. No persistent boot argument,
rdinit, clock bypass or root activation. Missing/duplicate/unsafe identity,
service/PID1/TTY/initrd/mount/root-job guard or unknown completion forbids return.

The optional debug-shell drop-in replaces only ExecStart and Restart=no, preserving
TTYReset/TTYVHangup and the original shell. The helper forks an autonomous observer
then execs `/bin/sh` in the original service PID with PPID1 and inherited TTY.
Observer uses inherited TTY descriptors only for getters: no read, reopen, flush,
termios setting or MMIO. `/dev/kmsg` output at KERN_INFO uses kernel console TX
rather than the TTY buffered TX path; existing final loglevel7 makes it eligible
for console output. Emission does not prove host reception or kernel progress.

Wire record (one newline-terminated write, total below 900 bytes):

```
K230_UOBS_V1 nonce seq stage payload_byte_length crc32_8lowerhex payload_lowerhex
```

Payload is ASCII `key=value\n`, at most 384 bytes. CRC is standard reflected
CRC32 (Python zlib.crc32 compatible), over decoded payload. No truncation. Permit
only an optional leading kernel timestamp `[digits.fraction] ` with console
padding spaces. Each helper write begins `<6>\n` to establish a fresh console
line even after an unterminated shell prompt. Permit no arbitrary text or inserted printk inside a frame. Fresh
nonce, exact sequence/stage, complete fields, length and CRC are mandatory. Raw
wire output is always retained privately. Do not strip general kernel output.

Sequence and exact payload keys:

- 0 `ready`: boot_id, shell_pid, guards=1, window_ms=12000.
- 1 `before`, 2 `after`: sample (before/after), iflag/oflag/cflag/lflag (eight
  lower hex digits), ispeed_code/ospeed_code (encoded termios speed constants),
  ldisc, rx, tx, frame, overrun, parity, brk, buf_overrun, irq, irq_available,
  irq_total (unsigned decimal), runtime (active/suspended/unknown).
- 3 `return`: same boot_id/shell_pid, guards=1, reboot=1. It acknowledges one
  prearranged `/bin/reboot -ff` attempt, not its successful hardware completion.
- At the next expected sequence, `failed`: phase (initial/observe/renew),
  reason (guard/snapshot/fork/clock). No later return follows failure.

IRQ is derived by cached TIOCGSERIAL. irq_available=0/irq_total=0 explicitly
means the targeted row was unavailable, not measured zero interrupts. Only
that IRQ's aggregate count is retained. RX increments before delivery and is
not proof of exact receipt bytes or per-byte IRQ attribution.

Initial and renewed guards each have an absolute 20-second child deadline;
each snapshot getter child has a separate 20-second bound (initial readiness
up to 40s; window+after snapshot+renewed guard up to 52s).
individual systemctl queries have three-second limits and bounded reap. Observe
for 12000ms after READY, then renew all guards before return. Unknown guard,
snapshot/output/child or identity change stops the sequence. A userspace timer
cannot guarantee recovery during a kernel/D-state stall.

Host continuously monitors from boot, including early SPL/normal output. Only
after fresh candidate banner, ready+before and a fresh primary shell prompt,
send once: `printf '\nK230_UOBS_RX <nonce>\n'`. Receipt success is a separate
factual field; no second input is required for snapshots or return. Missing
receipt with completed observer and protected return is a recovered diagnostic
failure, not successful input. Allow 180s boot readiness, 60s autonomous window
after READY, then 180s protected return after ack. Early return before READY is
failed diagnosis; still perform protected postflight after fresh SPL/vendor
kernel/login. No input on candidate unknown. Require fresh normal boot ID,
exact profile/kernel/services/eight hashes before claiming recovery.

Bundle `observer.json`, schema `k230-uart-observer-artifact-v1`, contains protocol,
helper/helper_sha256/helper_source_sha256, system/init/kernel/base_kernel,
dtb_sha256/base_dtb_sha256, base_bundle, dtb_bootargs_only=true,
window_ms=12000, payload_max=384. SHA256SUMS covers metadata too. Build and host
preflight must independently compare base/new Image and kernel identity, matching
initrd wrapper/system, helper/source hashes, and normalized DTBs with only
/chosen/bootargs removed. A boolean alone is not artifact-equivalence proof.
