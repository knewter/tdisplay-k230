# Physical verbose minimal trial, 2026-10-02

This is a physical boot observation on the corrected Linux 7.3-rc5 bundle,
using controller revision `f463e88d1622f75a41fb45a55f34570d582a8407`.
It did **not** reach the diagnostic receipt and did **not** request a candidate
reboot. Shutdown, callback execution and automatic normal return remain
**UNVERIFIED**. The 180-second return deadline never started.

The protected normal preflight passed before loading the candidate. All five
U-Boot loads passed their count/CRC checks, and the volatile bootargs matched.
Linux 7.3 started. The reset-controller probe returned 0; its pinned probe
returns the managed restart-registration status, supporting registration in
this boot, but not callback execution. The private capture ends during boot
initcall output at uptime 4.036685. No shell-init, receipt, true, or candidate
reboot marker was captured. All 624 observed initcall entries have matching
returns. That does not establish completion of later initialization.

The controller begins eight one-second receipt attempts at the early Linux
banner. About 100 KiB of candidate output requires over eight seconds at
115200 8N1, so the receipt window is inadequate for this verbose boot. The
uncapped raw log is 130,995 bytes, below the 131,072-byte parser buffer limit;
there is no evidence that a hidden receipt was discarded. A subsequent
15-second receive-only capture and a separate 90-second receive-only capture
both obtained zero bytes. No extra diagnostic input, exit or reboot was sent.
This does not distinguish a later kernel stall from console loss or another
boot problem.

A root-owned webcam recording and a fresh still were reviewed before requesting
operator recovery. The [panel photograph](boot-panel.jpg) shows boot text
rather than normal Home. The panel is angled and reflective; the photograph
cannot establish the exact final serial line. No real-finger acceptance was
performed. [Camera provenance](camera.json) records the source and crop.

## Invocation

The private directory is mode 0700 and logs/configuration mode 0600. Raw UART
and the full camera recording remain outside Git. The root operator held the
board/serial reservation and separately recorded the webcam under its lock.
No persistent boot selection, default profile, or flashed image was changed.

```sh
python3 tools/mainline-drm-initrd-shell-trial.py \
  --mode minimal --debug-shutdown \
  --bundle /nix/store/asj7l4zj5jrjkgng4nrcx3y72p7jf7aa-k230-mainline-drm-trial-boot-files \
  --manifest "$HOME/tmp/k230-mainline-restart-board/candidate-manifest.json" \
  --normal-report "$HOME/tmp/k230-mainline-restart-board/normal-report.json" \
  --log "$HOME/tmp/k230-mainline-restart-board/shutdown-debug-uart.log" \
  --result "$HOME/tmp/k230-mainline-restart-board/shutdown-debug-result.json"
```

Exit status was 1: `initrd minimal protocol did not complete at reception`.
The current minimal-mode failure path did not write the result JSON; the
coordinator's [observation record](observation.json) preserves that limitation,
controller identity, exact artifacts, preflight and raw-capture hash. The
[console excerpt](console-excerpt.txt) is a curated subset, not the raw log.

## Recovery and next gate

Operator power-cycle recovery and a fresh protected normal postflight are
pending at the time of this record. The earlier trial's recovered Home must
not be reused as recovery proof for this boot. Do not send commands into an
unidentified initrd/PID-1 shell.

Correct the debug readiness gate before another trial: observe the exact late
shell-init marker within a bounded wait before attempting receipts, and write
a structured recovery-required result if readiness/receipt fails. Then require
actual candidate reboot and fresh normal identities before proceeding to the
root-label/read-only-mount diagnostics. See the [shutdown source audit](../shutdown-path-audit-2026-10-02.md)
for the limits of interpreting device-shutdown traces. Tasks 5d.4 and 5b.5 remain
open.
