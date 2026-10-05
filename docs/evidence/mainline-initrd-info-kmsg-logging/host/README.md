# Actual same-artifact info/kmsg qualification

Executed host proof at controller revision0ba47bc06e0932842daa7461b8aefc7fba2058f8.
The [exact qualifier](qualification-command.py) was copied into a NEW0700
`~/tmp` directory and executed with Python3.14/native zstd and fdtget:

```sh
python3.14 qualification-command.py \
  --bundle /nix/store/p2kdar89q7dhwdajjy0mrhmxxzcgsalw-k230-mainline-drm-trial-boot-files \
  --dev /nix/store/24hbalyljs6gn6fzkkl24znv8a0x6jdl-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev \
  --normal-report PRIVATE_NORMAL_FROM_NEW_ARMED_INFO_RECOVERY
```

Exit0: [safe actual result](result.json). Same source/config/Image/DT/archive,
manifest and five load/CRC expectations, matching systemd init ELF, original
DT bootargs and bundle SHA256SUMS passed. Historical full build1c59f856 still
supplies the existing artifacts; no new build, transfer, flash or UART occurred.
Exactly one info/console value changes: destination console→kmsg. Argument bytes
355→352; literal command373→370, below the unchanged512-byte transport bound.
Default marker-free command remains317 bytes; root/init/masks/join/sole console,
helpers and all immutable identities remain equal. This is source/artifact
proof, not execution or delivery on the board.

The normal anchor matches [NEW armed recovery](../../mainline-initrd-info-logging/physical-2026-10-05/recovery.json)
with distinct boot, exact identities/eight hashes/three services and registration
absence. The host qualifier rechecks that receipt/report; it is not a new live
board preflight. That occurs only under the later reserved begin invocation.

[Controller source proof](controller-host.md) and independent reviews passed:
9 new+10info+13debug+36ordinary fixtures. Unaffected function bodies match the
reviewed base, including readiness, loads, identity/recovery, full-log pumping
and unknown-no-input paths. Independent actual-artifact review PASS: executed/public bytes, actual identities/hashes/CRCs/archive/DT, source and fresh recovery binding rechecked.
Physical kmsg delivery, ordinary root/panel/glass and task5b.5 remain UNVERIFIED.
Next board command is task5q.3, only after reviewed source/actual host gates and
NEW protected recovery. Backend fallback/filter/drop limits stay explicit in
[the source plan](../../../research/mainline-initrd-info-kmsg-comparison-2026-10-05.md).
