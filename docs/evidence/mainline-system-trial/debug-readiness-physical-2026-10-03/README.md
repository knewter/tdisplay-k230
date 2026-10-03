# Mainline initrd debug shell appears; readiness check needs correction

Physical serial observation, 2026-10-03 UTC. Root reserved the board/UART from
`~/tmp/k230-mainline-probe-integration`, branch `integrate/mainline-probe-path`,
bounded base `65578ff2`. Controller source `3f07e8ef`; no build or flash.
Exact candidate identities and wire-log hash are in [the result](trial-result.json).

```sh
python3 tools/mainline-drm-initrd-debug-trial.py \
  --bundle /nix/store/5yqilsfyj35jzrcqjjqilkr6sd47qlms-k230-mainline-drm-trial-boot-files \
  --manifest "$HOME/tmp/k230-mainline-initrd-debug-board/candidate-manifest.json" \
  --normal-report "$HOME/tmp/k230-mainline-initrd-debug-board/normal-report.json" \
  --blkid-result "$HOME/tmp/k230-mainline-blkid-board/trial-result.json" \
  --log "$HOME/tmp/k230-mainline-initrd-debug-board/trial-uart.log" \
  --result "$HOME/tmp/k230-mainline-initrd-debug-board/trial-result.json"
```

Exit **2**, `recovery-required-unknown`. Protected normal preflight and the
candidate's verified loads/CRCs/exact volatile arguments completed. The fresh
Linux 7.3.0-rc5 banner, initrd systemd 261.2 and primary `sh-5.3# ` prompt appeared.
Subsequent asynchronous systemd messages began immediately after that prompt
on the same line, then continued for twelve lines. The last-tail-only readiness
check did not accept this observed prompt; it expired without sending even the
first diagnostic receipt. No IDBG commands, root activation, touch or automatic
reboot were attempted. Raw serial output remains private.

The safe prompt boundary that motivates a host regression is:

```text
<CR><LF><ESC>[?2004hsh-5.3# [<ESC>[0;32m  OK  <ESC>[0m] Finished ...
```

This is a controller readiness limitation, not evidence that systemd or udev
completed or proof of any kernel hang. The initial receipt, shell ownership and
root-boundary guards were not reached. Their physical status remains UNVERIFIED.
A narrow correction must recognize a fresh observed prompt after the candidate
banner/systemd observation while retaining all subsequent receipt/identity/
ownership guards; it must not strip arbitrary kernel text or infer completed jobs.

The user pressed reset after the controller stopped. The first 15-second fresh normal
prompt wait expired without commands; one subsequent bounded fresh check passed.
[Protected recovery](operator-reset-recovery.json) confirms a different boot ID,
exact original system/profile/kernel/init, three active shell services, absence
of the registration marker and eight unchanged boot hashes. Qualified normal
Home IPC then returned RC0. No second reset was needed. Board/UART released.

Task 5b.5 remains open: ordinary usable mainline root, panel observation,
deliberate glass touch and protected return are still required. No new accepted
capability, photograph proof or physical finger interaction is claimed here.
