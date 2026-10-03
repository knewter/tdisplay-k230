# Udev root-partition metadata probe passes on mainline

Physical serial proof, 2026-10-03 UTC (October 2, America/Chicago).
Root used `~/tmp/k230-mainline-probe-integration`, branch
`integrate/mainline-probe-path`, bounded base `65578ff2`; root reserved the
single board/UART. No build slot or operator reset was used for this trial.
Controller source `79e9fdc8`; exact bundle/system identities are in the
[structured result](trial-result.json).

```sh
python3 tools/mainline-drm-blkid-trial.py \
  --bundle /nix/store/5yqilsfyj35jzrcqjjqilkr6sd47qlms-k230-mainline-drm-trial-boot-files \
  --manifest "$HOME/tmp/k230-mainline-blkid-board/candidate-manifest.json" \
  --normal-report "$HOME/tmp/k230-mainline-blkid-board/normal-report.json" \
  --log "$HOME/tmp/k230-mainline-blkid-board/trial-uart.log" \
  --result "$HOME/tmp/k230-mainline-blkid-board/trial-result.json"
```

Exit **0**, `recovery-verified-diagnostic-passed`. Fresh reception, true,
proc/uptime, sysfs/devtmpfs/exact mount table, canonical SD1 p2 ancestry and
sysfs/devnode device-number checks all passed. The single bounded read-only
`udevadm test-builtin blkid` returned RC0 and exactly one matching
`ID_FS_TYPE=ext4` and `ID_FS_LABEL=NIXOS_SD`.

The 1322-byte private raw metadata/log output was retrieved completely before
reboot with exact framing/byte count/SHA/RC0 and a fresh shell prompt. The root
operator independently reparsed the setup/probe receipts and complete retrieval
from the private UART log. No metadata contents or private pathname is committed;
the structured result retains source-output and whole-wire-log hashes.

One acknowledged `/bin/reboot -ff` returned through SPL to a new normal boot.
Protected postflight passed exact original system/profile/kernel/init, absence
of the registration marker, all three normal shell services active and all eight
boot hashes unchanged. Persistent boot selection was unchanged. No clock-ignore
argument, root mount or ordinary activation was part of this diagnostic.

This proves the selected root partition's standalone metadata probe, distinct
from the earlier label/read-only mount checks. It does **not** prove whole-disk
or other-partition probes, udev daemon/netlink/coldplug completion, writable
root activation, new display frames or deliberate touch. The full ordinary
boot still has its recorded pre-login timeout; task 5b.5 stays open. No new
photograph or physical finger interaction was performed in this probe.

Next is the separately reviewed [bounded initrd debug-console plan](../../../research/mainline-initrd-debug-console-2026-10-03.md),
which observes unit/worker state while excluding root activation. Its source
plan is not physical proof or a production fix.
