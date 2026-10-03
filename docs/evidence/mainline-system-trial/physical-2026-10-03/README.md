# First ordinary mainline boot stops before root activation

Evidence class: physical serial observation and a separate camera still,
2026-10-03 UTC (October 2, America/Chicago). Root operated the single board
and UART from `~/tmp/k230-mainline-probe-integration`, branch
`integrate/mainline-probe-path`, bounded base `65578ff2`. Controller source
`2fc70b46`; no kernel build slot was used.

The prerequisite [complete read-only root trial](../../mainline-sd1-clocks/physical-no-flag-2026-10-03/README.md)
passed all mount/unmount checks and an automatic protected-normal return.
The separate ordinary trial used:

```sh
python3 tools/mainline-drm-system-trial.py begin \
  --bundle /nix/store/5yqilsfyj35jzrcqjjqilkr6sd47qlms-k230-mainline-drm-trial-boot-files \
  --manifest "$HOME/tmp/k230-mainline-system-board/candidate-manifest.json" \
  --normal-report "$HOME/tmp/k230-mainline-system-board/normal-report.json" \
  --state "$HOME/tmp/k230-mainline-system-board/state.json" \
  --log "$HOME/tmp/k230-mainline-system-board/begin-uart.log" \
  --result "$HOME/tmp/k230-mainline-system-board/begin-result.json"
```

Controller exit **1**, `recovery-required-unknown`: ordinary-init login
readiness was not observed within **180 seconds**. Normal preflight had
verified the protected identities/services/eight boot hashes and absence of
the registration marker. Exact U-Boot loads, CRCs and printed volatile
arguments passed before boot. No persistent boot-file/profile installation
was performed. The only added controls are the three qualified first-boot
controls documented in the [host preparation](../README.md); neither
`rdinit` nor `clk_ignore_unused` was used.

The candidate kernel booted, disabled unused clocks and started systemd in
the initrd. The [curated candidate excerpt](candidate-console-excerpt.txt)
shows coldplug starting and the udev manager reporting started. The last
timestamped progress is around 7.24 seconds. No sysroot mount, root activation,
stage2 login or panic is observed in the candidate capture. The silence does
**not** establish which service or kernel callback blocked.

[Structured failure result](begin-result.json) preserves the private log's
hash, size, timestamp, original preflight and exact failure. No candidate
identity readiness state was established; no touch, finish, guessed shell
input or reboot retry was sent after the readiness deadline. Recovery from
this ordinary trial is **UNVERIFIED** at this checkpoint. The user was asked
to press reset; protected normal postflight remains required afterward.
Task **5b.5 stays open**.

[Camera still](ordinary-boot-panel.jpg) was captured during this trial with:

```sh
flock -n /tmp/k230-camera.lock ffmpeg -hide_banner -loglevel error \
  -f v4l2 -input_format mjpeg -video_size 1920x1080 -i /dev/video0 \
  -frames:v 1 -update 1 -y \
  "$HOME/tmp/k230-mainline-system-board/ordinary-boot-panel.jpg"
```

Capture exited zero. The separately reviewed frame shows a lit device with
text, but glare/angle prevent reliable reading. It is not a native framebuffer
capture and does not establish that mainline rendered a new frame, correct
rotation, coordinate mapping or a deliberate glass interaction. Raw UART,
private state and runtime configuration remain outside the repository.

## Operator reset returns the protected normal shell

The user subsequently pressed reset. The first 45-second fresh-prompt wait
ended before the normal shell prompt appeared; no command was sent. A second
fresh check succeeded: exact original system/profile/kernel/init, all three
shell services active, eight unchanged boot hashes and a new normal boot ID.
[Protected normal recovery result](operator-reset-recovery.json) records the
operator reset explicitly. This clears the recovery blocker for host diagnosis;
it does not establish automatic recovery or ordinary mainline acceptance.

After that protected identity check, a normal-session `swaymsg 'card_shell home'`
and shell overlay hide returned RC0. A separately reviewed [normal Home camera
still](normal-return-home.jpg), captured with the same camera command and a
fresh output path, shows the Home clock/icons/background. It confirms a visible
normal display return; it is not touch acceptance or a mainline frame claim.
