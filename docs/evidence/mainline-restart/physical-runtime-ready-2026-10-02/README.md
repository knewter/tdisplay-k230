# Runtime tracing reaches the MMC shutdown boundary

The reviewed `3e6941d7` controller was physically run with the exact `asj…`
restart bundle after independently verified user reset-button recovery.
The new passive readiness gate passed. Fresh reception, `/bin/true`, proc
setup and uptime passed, followed by all six runtime tracing stages with
returned RC 0 / MATCH 1. The exact `initcall_debug` parameter's prior N,
write and Y readback were independently returned. Runtime tracing is now
physically observed; this does not establish product acceptance.

The single `/bin/reboot -ff` request returned its fresh receipt and
`Rebooting.`. Seven device-shutdown entry messages followed, ending at:

```text
[    5.600764] mmcblk mmc1:59b4: shutdown
```

The full 180-second normal-return deadline expired without a later kernel
`Restarting system`, SPL or normal login. The controller exited 1. No
additional recovery input was sent. Automatic mainline restart, usable root
and deliberate touch remain **UNVERIFIED**; tasks 5d.4 and 5b.5 stay open.

An entry message proves that checkpoint was reached, not that its callback
completed or caused the stop. The next device's locks/PM barrier precede its
own entry print. The source audit must distinguish the card shutdown path
from that later boundary before choosing a bounded comparison.

```sh
python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal --runtime-shutdown-trace \
  --bundle /nix/store/asj7l4zj5jrjkgng4nrcx3y72p7jf7aa-k230-mainline-drm-trial-boot-files \
  --manifest "$HOME/tmp/k230-mainline-restart-board/candidate-manifest.json" \
  --normal-report "$HOME/tmp/k230-mainline-restart-board/normal-report.json" \
  --log "$HOME/tmp/k230-mainline-restart-board/runtime-ready-trace-uart.log" \
  --result "$HOME/tmp/k230-mainline-restart-board/runtime-ready-trace-result.json"
```

[Observation](observation.json) is a coordinator reconstruction using the
production fresh-marker parsers against the complete private log. This
controller revision did not persist a result on normal-return timeout;
the requested result file was absent. The record preserves that limit,
exact selected bundle/system/artifact identities, raw-log hash/timestamp,
protected preflight and returned stages. [Excerpt](console-excerpt.txt)
redacts protocol nonces and labels its timeout curation; normal-system raw
output remains private.

The separately [reviewed camera still](boot-panel.jpg) shows panel boot text,
with glare/angle limits recorded in [provenance](camera.json). No new finger
acceptance or native capture was obtained. Root held the board/UART/camera in
`~/tmp/k230-mainline-probe-integration`, branch `integrate/mainline-probe-path`,
bounded base `3e6941d7`. No kernel rebuild, protected boot-file/profile change
or persistent boot-selection write was performed. Manual recovery from this
latest attempt is pending.


The subsequent [MMC source audit](../../../research/mainline-mmc-shutdown-boundary-2026-10-02.md)
traces callback/next-device waits and the missing clock consumers. The
[reviewed clock-comparison preparation](../minimal-clock-comparison-host-2026-10-02.md)
passes 96 host tests and gives the exact fresh-path operator command after
protected recovery. It additionally preserves returned tracing facts in a
structured normal-timeout result. The comparison is physically unperformed;
it tests global clock-cleanup dependence, not a particular gate or culprit.
