# Actual host qualification for one unchanged ordinary repeat

Executed at revision3d2a080c00b2611593cb216bd0f4c40539cd429a, source digest
f5f23057119cb79228ebb868e7f92524a6f9a6f230b9931d438013d34b8da0c5.
No source, kernel/initrd/DT build, transfer or UART was performed by this command.
The [exact qualifier](qualification-command.py) was copied into NEW0700
`~/tmp` scratch and run with Python3.14/native zstd and fdtget:

```sh
python3.14 qualification-command.py \
  --bundle /nix/store/p2kdar89q7dhwdajjy0mrhmxxzcgsalw-k230-mainline-drm-trial-boot-files \
  --dev /nix/store/24hbalyljs6gn6fzkkl24znv8a0x6jdl-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev \
  --normal-report PRIVATE_NORMAL_FROM_NEW_KMSG_RECOVERY
```

Exit0: [safe executed result](result.json). Exact299 argument/317 literal bytes
match the [original quiet physical policy](../current-p2-ordinary-physical-2026-10-05/README.md).
Existing synchronous-initramfs/marker-free selectors select it; all logging
selectors are false. Exact comparisons with the prior actual kmsg preparation
confirm the same manifest, helper, system/kernel/init and protected identities;
only its two explicit logging tokens are absent.

Same p2/24h source/config/Image/DT/archive/init/manifest/load/CRC expectations,
archived systemd ELF, original DT args and bundle SHA256SUMS passed. Historical
full build1c59f856 supplies existing artifacts. The normal report matches
[NEW protected kmsg recovery](../../mainline-initrd-info-kmsg-logging/physical-2026-10-05/recovery.json):
distinct boot, full identities/eight hashes/three services/registration absence.
This checks a recorded anchor, not a new live preflight. The reserved begin
invocation must do its own preflight.

Independent actual-artifact and NEW recovery reviews PASS: executed/public bytes, present immutable hashes/CRCs/archive/DT, unchanged helper, original quiet equality and protected recovery/report binding were rechecked. Source is unchanged
from the independently tested9kmsg+10info+13debug+36ordinary fixtures and shared
AST comparisons. No new selector or behavior was added. The future one180s
passive physical repeat and its recovery remain UNVERIFIED. Either outcome is
a temporal/reproducibility control, not a logging diagnosis or ordinary-root/
panel/glass acceptance. Task5b.5 stays open. [Bounded plan and source limits](../../../research/mainline-ordinary-baseline-repeat-2026-10-05.md).
