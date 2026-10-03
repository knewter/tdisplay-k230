# Serial-only observer comparison: physical pre-init boundary

Evidence class: physical board UART runtime. Integration branch
`integrate/mainline-probe-path`, bounded base `65578ff2`, source revision
`33242719c08d38cf0758e8181088fd57c5dfcd6e`. The coordinator reserved the
board and serial port; no build or camera reservation was needed for this run.
Task 5b.5 remains open; ordinary usable mainline root and deliberate glass
touch are **UNVERIFIED**.

## Controlled comparison

The [previous dual-console trial](../uart-observer-physical-2026-10-03/README.md)
ended after one READY frame. The user reset, and its protected normal postflight
and Home IPC passed; a private camera frame visually showed Home. This new
trial used the same `16cpjji…` bundle, `k1zjqdn…` system, `9vdk79…` kernel,
initrd/helper and staged artifacts. Exact immutable paths/digests are in
[result.json](result.json). Nothing was flashed or rebuilt.

Only the sole `console=tty0` token was removed from the volatile arguments.
`consoleblank=0`, `console=ttyS0,115200n8`, the sole immutable init, five
diagnostic controls and three fresh identity arguments were retained. Host
preparation verified the untouched original bootargs/DTB, archive, closure,
helper bytes/source, Image and hardware DT. U-Boot imported the original
checked environment text, replaced only that base argument value and appended
the existing controls; exact printed arguments were verified before boot.
The normal profile, protected boot files and persistent environment selection
were unchanged. The independent reviewer inspected this path; all 32 focused
tests passed on the integrated source (8.533 seconds), strict validation passed
and actual controller preparation with this option passed before serial opened.
See [host commands/tests](../../mainline-uart-observer-trial/serial-console-only-host-2026-10-03.md)
and [source limits](../../../research/mainline-uart-ready-printk-boundary-2026-10-03.md).

The exact operator command from the integration worktree:

```sh
nix shell --inputs-from . nixpkgs#dtc --command \
  python3 tools/mainline-drm-uart-observer-trial.py \
  --serial-console-only \
  --bundle /nix/store/16cpjjiifxgwyb6bndhi39vfmlvcdw6h-k230-mainline-uart-observer-boot-files \
  --manifest "$HOME/tmp/k230-mainline-uart-observer-board/candidate-manifest.json" \
  --normal-report "$HOME/tmp/k230-mainline-uart-observer-board/normal-report.json" \
  --blkid-result "$HOME/tmp/k230-mainline-blkid-board/trial-result.json" \
  --log "$HOME/tmp/k230-mainline-uart-observer-board/serial-console-uart.log" \
  --result "$HOME/tmp/k230-mainline-uart-observer-board/serial-console-result.json"
```

## Observations and limit

Protected normal preflight and all U-Boot loads/CRCs passed. A fresh Linux
7.3.0-rc5 banner appeared. Display registration and Goodix input registration
were logged. The last safe kernel milestones were:

```text
2.810421 Goodix Berlin Capacitive TouchScreen registered as input0
2.811995 clk: Disabling unused clocks
2.812201 PM: genpd: Disabling unused power domains
2.812254 ALSA device list:
2.812261 No soundcards found.
```

No `Freeing unused kernel memory`, init launch, systemd banner, observer frame,
primary prompt, receipt or automatic return was observed. These milestone
messages do not establish completion of asynchronous power-domain work or
identify any clock, power-domain, UART or console cause. The original run
reached READY; this comparison stopped earlier, so no counter/RX comparison
was obtained and removing the VT console did not improve observed progress.

The controller sent **zero receipt commands**, waited its 180-second passive
readiness/recovery bound and exited 2 with `recovery-required-unknown`. No
candidate input or reboot retry followed. Last UART write timestamp:
`2026-10-03T06:39:54.249351+00:00`; result written `2026-10-03T06:42:50.528031+00:00`. Private UART: 47,035
bytes, SHA256 `3446fdaaa2e524d05026409d66a6744c60878b66bd86c51a2fbe11e3f4492d24`. Raw logs, volatile nonce/boot IDs
and transfer addresses remain private.

The user pressed reset. [Protected normal postflight](operator-reset-recovery.json)
passed with a fresh boot ID, exact system/profile/kernel/init/uname, three
active shell services, all eight unchanged protected boot hashes and absent
registration marker. Qualified normal Home IPC returned RC=0; a separately
reserved private camera frame visually showed Home icons, clock and background.
Glare limits detail; the frame is not published and is not mainline/touch proof.
The checks use
the committed `mainline-drm-system-trial.py` normal-check function and
`mainline-drm-normal-state.py` helper against the private preflight identity.
Exact recovery commands:

```sh
python3 "$HOME/tmp/k230-mainline-uart-observer-board/serial-console-reset-normal-check.py"
python3 "$HOME/tmp/k230-reset-recovery/serial-op.py" \
  "$HOME/tmp/k230-mainline-system-board/return-home.command.private" \
  "$HOME/tmp/k230-mainline-uart-observer-board/serial-console-return-home-uart.log" 45
```

The reset checker returned 0; its timestamp and raw-log digest/size are in
the recovery JSON. This qualifies operator-reset recovery; the original
diagnostic still failed and automatic return remains **UNVERIFIED**.
No further boot trial was performed. This failed comparison does not satisfy
mainline usable-root/panel/touch task 5b.5.
