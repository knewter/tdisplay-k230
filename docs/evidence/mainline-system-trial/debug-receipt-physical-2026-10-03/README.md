# Mainline debug prompt recognized; first receipt has no reply

Physical serial observation on 2026-10-03 UTC. Root exclusively reserved the
board/UART in `~/tmp/k230-mainline-probe-integration`, branch
`integrate/mainline-probe-path`, bounded base `65578ff2`. Corrected controller
source `b2e219e2`; no rebuild or flash. Matching physical standalone blkid and
protected normal return remained prerequisites. Exact identities and private
wire-log hash are in [the structured result](trial-result.json).

```sh
python3 tools/mainline-drm-initrd-debug-trial.py \
  --bundle /nix/store/5yqilsfyj35jzrcqjjqilkr6sd47qlms-k230-mainline-drm-trial-boot-files \
  --manifest "$HOME/tmp/k230-mainline-initrd-debug-board/candidate-manifest.json" \
  --normal-report "$HOME/tmp/k230-mainline-initrd-debug-board/normal-report.json" \
  --blkid-result "$HOME/tmp/k230-mainline-blkid-board/trial-result.json" \
  --log "$HOME/tmp/k230-mainline-initrd-debug-board/retry-uart.log" \
  --result "$HOME/tmp/k230-mainline-initrd-debug-board/retry-result.json"
```

Exit **2**, `recovery-required-unknown`. Fresh protected normal preflight,
verified candidate loads/CRCs/exact volatile arguments and corrected readiness
recognition completed. Linux 7.3.0-rc5, initrd systemd 261.2 and the initial
primary shell prompt were observed. The controller sent exactly one fresh framed
receipt command. There was no echo of that command, receipt output or returned
frame during its ten-second bound. It stopped with no further input or reboot.
No snapshot or identity/ownership/root guard was reached. Raw UART stays private.

This proves prompt recognition, not command reception or diagnostic readiness.
It does not establish a UART hardware, IRQ, clock, terminal-setting or kernel
fault. The next investigation must compare the exact debug-terminal setup and
UART receive driver/configuration with the working minimal initrd console before
another speculative physical retry. Ordinary usable root, display/touch
acceptance and mainline task 5b.5 remain open.

The user pressed reset after the receipt timeout. A bounded fresh normal prompt
check and [protected postflight](operator-reset-recovery.json) passed: different
boot ID, exact original system/profile/kernel/init, three active services,
registration-marker absence and eight unchanged boot hashes. Qualified normal
Home IPC returned RC0. This operator reset is separate from automatic restart;
no automatic return is claimed. Board/UART released with normal Home selected.
