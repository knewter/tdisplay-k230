# Physical system controls and reboot

The [180-second camera recording](20260923T000520Z-system-controls-real-touch.mp4)
was started before the user was instructed to cancel Power off and confirm
Reboot. The host camera keeps recording when the board reboots.
[Camera review](video-audit.md) determines which finger actions and visible
states are established; intended actions alone are not evidence of completion.

The [serial capture](reboot-console.txt) used `tools/capture-boot.py` for
150 seconds without `--send`, `--kick` or injected input. It records shutdown
and boot back to the login prompt. The subsequent
[runtime check](post-reboot.txt) identifies boot
`8915db67-9428-4b87-95fa-f83f075bc7cf`, the same diagnostic system as before,
and active shell, seatd and firewall. Sway logs its initial splash seed and
removal at commit sequence 7. The [native frame](after-reboot-native.png)
records the returned shell separately from the physical camera evidence.

This is a touch-triggered reboot with host cables attached. It does not close
the separate standalone power-on check. No image flash, home restoration or
persistent configuration change was performed.

The operator subsequently confirmed the workflow as "all good". The camera
shows the control interaction and reboot but does not make each confirmation
label legible. The user declined a separate wall-supply power-on test; the
shell acceptance plan now uses this automatically returning session, with
its USB-connected warm-reboot provenance retained. This does not change the
separate boot-splash proposal's power-on evidence status.
