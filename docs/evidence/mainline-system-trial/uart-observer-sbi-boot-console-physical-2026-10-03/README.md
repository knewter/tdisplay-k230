# Retained SBI boot console: physical pre-init boundary

Evidence class: physical board UART runtime. Root integration worktree
`/home/jadams/tmp/k230-mainline-probe-integration`, branch
`integrate/mainline-probe-path`, increment base `e38c9040`, source revision
`da19a6981dfc43a53d7711cd118562a9d2c7b68c`. Root reserved the board and UART
for one bounded trial; no build, flash or camera reservation was required.
The serial reservation was released when the controller stopped.
Task 5b.5 remains open for ordinary usable mainline root and deliberate touch.

## Controlled comparison

The [serial-only baseline](../uart-observer-serial-console-physical-2026-10-03/README.md)
had returned to protected normal through an operator reset. Its postflight,
qualified Home IPC and private Home camera observation were already recorded.
The new [reviewed controller option](../../mainline-uart-observer-trial/sbi-boot-console-host-2026-10-03.md)
passed 38 focused tests and actual selected-artifact preparation, then landed
on master. It adds only volatile `earlycon=sbi keep_bootcon` to the serial-only
argument set. The same kernel, hardware DT, initrd, helper, system closure and
staged bundle were used; exact paths/digests are in [result.json](result.json).
No persistent boot selection, normal profile or protected boot file changed.

Exact operator command, run from the integration worktree:

```sh
python3 tools/mainline-drm-uart-observer-trial.py \
  --serial-console-only --sbi-boot-console \
  --bundle /nix/store/16cpjjiifxgwyb6bndhi39vfmlvcdw6h-k230-mainline-uart-observer-boot-files \
  --manifest "$HOME/tmp/k230-mainline-uart-observer-board/candidate-manifest.json" \
  --normal-report "$HOME/tmp/k230-mainline-uart-observer-board/normal-report.json" \
  --blkid-result "$HOME/tmp/k230-mainline-blkid-board/trial-result.json" \
  --log "$HOME/tmp/k230-mainline-uart-observer-board/sbi-boot-console-uart.log" \
  --result "$HOME/tmp/k230-mainline-uart-observer-board/sbi-boot-console-result.json"
```

## Observations

Protected normal preflight, all load/CRC checks and exact printed volatile
arguments passed before boot. A fresh Linux 7.3.0-rc5 banner and the kernel's
SBI DBCN detection appeared. The additional boot console was actually enabled:

```text
[    0.000000] printk: legacy bootconsole [sbi0] enabled
[    3.788489] clk: Disabling unused clocks
[    3.810249] PM: genpd: Disabling unused power domains
[    3.838138]   No soundcards found.
```

Later lines were duplicated through the retained SBI/regular serial consoles;
both copies are preserved privately. No SBI boot-console disable message,
init-memory freeing, init launch, systemd banner, observer frame, primary
prompt, receipt or automatic return was observed. The last kernel timestamp
was 3.838138. This comparison confirms that the requested logging path was
active; it did not reveal a later boot boundary or diagnose the cause. The
last ALSA message is not evidence that an audio callback stalled. Retained
boot consoles also alter timing and can themselves block, so this does not
eliminate every possible console failure.

The controller sent **zero receipt commands**, kept strict frame parsing,
waited the 180-second passive bound and exited 2 with
`recovery-required-unknown`. No candidate input or reboot retry followed.
Private UART: 52,892 bytes, SHA256
`6c325ec006b0c09568b9535addf7b95ef0314903ee0d7a31ca0f628c332ace64`.
The result records UTC write timestamps. Raw logs, nonces and boot identities
remain private; this public packet uses an explicit field allowlist.

The user pressed reset. [Protected normal postflight](operator-reset-recovery.json)
passed with a fresh boot ID, exact system/profile/kernel/init/uname, three
active shell services, all eight unchanged protected boot hashes and absent
registration marker. Qualified Home IPC completed with return code 0. A
separately reserved private C920 camera frame visually showed Home icons,
clock and background; angle, focus and glare limit detail. The frame remains
private and is not mainline or touch proof.

Exact recovery commands, run after the confirmed user reset:

```sh
python3 "$HOME/tmp/k230-mainline-uart-observer-board/sbi-boot-console-reset-normal-check.py"
python3 "$HOME/tmp/k230-reset-recovery/serial-op.py" \
  "$HOME/tmp/k230-mainline-system-board/return-home.command.private" \
  "$HOME/tmp/k230-mainline-uart-observer-board/sbi-boot-console-return-home-uart.log" 45
```

The reset checker uses the committed system-trial normal-check function and
normal-state helper against the private preflight identity, and returned 0.
Its timestamps and private log/image digests are in the recovery JSON.
This qualifies operator-reset recovery; automatic mainline return, ordinary
usable mainline root and deliberate touch remain **UNVERIFIED**. No further
boot trial ran during recovery. Board, serial and camera reservations are
released.

## Next diagnostic

The existing-image logging comparison is complete and did not discriminate
the stall. The [source plan](../../../research/mainline-serial-only-boot-boundary-2026-10-03.md)
now calls for a separately named optional diagnostic kernel: paired markers
around basic setup, initramfs completion, root-console setup, init accessibility,
key loading, the global asynchronous-work wait, memory cleanup and init exec.
Brief nbcon emergency flushing is attempted only for each marker, on the
serial-only baseline without retained boot consoles. It must never remain
enabled across the blocking operation. Keep selected kernel/bundle identity
checks and separate host object/build and physical proof; never substitute
this failed comparison for mainline acceptance.
