# Physical corrected minimal probe, 2026-10-02

From controller source `f9759f43c651ef8da68945f117b40f89c78649a4`, the
operator staged the inspected `asj7l4zj...` restart bundle and ran:

```sh
python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal \
  --bundle /nix/store/asj7l4zj5jrjkgng4nrcx3y72p7jf7aa-k230-mainline-drm-trial-boot-files \
  --manifest "$HOME/tmp/k230-mainline-restart-board/candidate-manifest.json" \
  --normal-report "$HOME/tmp/k230-mainline-restart-board/normal-report.json" \
  --log "$HOME/tmp/k230-mainline-restart-board/minimal-uart.log" \
  --result "$HOME/tmp/k230-mainline-restart-board/minimal-result.json"
```

The private capture was created at 17:06:46 UTC; its last received bytes were
at 17:07:14 UTC. The controller obtained live protected normal preflight,
verified all 629 candidate-system closure paths and staged metadata, then
verified five U-Boot load counts/CRCs and exact volatile bootargs. Staging
returned zero. An earlier full-closure HTTP download timed out before import;
the successful transfer exported only eight new paths against the previously
proved candidate closure. No normal boot file or persistent profile was changed.

[observation.json](observation.json) pins the artifacts, actual normal
preflight, capture SHA-256 and limits. [console-excerpt.txt](console-excerpt.txt)
contains only fresh fixed protocol output and the subsequent `Rebooting.`.
The new `/proc` setup passed: receipt, `/bin/true`, mkdir, proc mount and uptime
all completed successfully. This is physical serial-command evidence, not a
usable mainline root or deliberate touch result.

The candidate printed `Rebooting.` after `/bin/reboot -ff`; no subsequent kernel
restart announcement, U-Boot SPL or normal Linux banner was captured. The
capture's sole `reboot: Restarting system` line belongs to the **initial normal
reboot before the candidate was loaded** and is excluded from candidate proof.
Neither the request receipt nor `Rebooting.` proves the kernel callback ran.

The operator reported unplug/replug while the controller waited for normal
return, and serial disconnected. The controller exited 1 on that disconnect;
it did not obtain a completed 180-second normal-return deadline result or a
recovery postflight. The following check sent only CR, obtained an unidentified
continuation prompt, and sent no commands. A full removal of all USB/power was
requested; the operator then confirmed that the normal shell was visibly running. Based
on that observation, the coordinator cleared the interrupted console input
and obtained independent protected normal postflight. No additional power
cycle was required. The earlier unidentified prompt was not treated as proof
of either a normal or mainline system.

Task 5d.4 remains unchecked: automatic mainline restart is **UNVERIFIED**.
Task 5b.5 remains unchecked for usable root and deliberate touch. Raw UART
and transfer URLs remain private outside Git. No deliberate glass interaction
is claimed.

## Independent normal recovery

[postflight.json](postflight.json) records fresh boot ID
`08f9455a-1044-4d72-b7ae-bc70d611a8e2`, normal Linux6.6.36 and exact normal
system/profile/kernel, three active shell services and all eight protected
boot hashes. This proves manual recovery separately from the unproved
automatic restart. The exact qualified board Python helper invocation was
`python3 -I /run/k230-mainline-normal-state.py postflight FRESH_32_HEX_TOKEN`,
using the installed `/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3`.

Home was requested through compositor IPC and transient surfaces hidden.
[output-state.json](output-state.json) records powered normal DSI-1 at
568×1232,52.190Hz. The separately captured and visually reviewed
[home-panel.jpg](home-panel.jpg) shows normal Home, wallpaper, clock and icons.
[camera.json](camera.json) preserves source time/hash and the FFmpeg crop/180°
presentation transform. The original full camera frame stays private.
This is camera evidence, not new finger acceptance or mainline panel proof.
