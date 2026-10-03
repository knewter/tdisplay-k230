# Bounded initrd blkid diagnostic: host preparation

Prepared 2026-10-03 UTC (local October 2), branch `mainline-drm-blkid-trial`,
base `cfcbe592b3ecd81062682d3857c4a377c3372ff5`, worktree
`~/tmp/k230-mainline-blkid-trial`. Owned paths are the new controller, its tests,
and this evidence directory. No board/UART or build reservation was taken.

This implements the narrow diagnostic from
[the initrd coldplug source audit](../mainline-system-trial/initrd-coldplug-source-audit-2026-10-02.md).
It reuses immutable bundle preparation, protected normal identities/closure/load
counts/CRC/printed arguments and the fresh candidate banner→init-entry→shell
readiness helpers. The shared protected helper gains the same present-or-dangling
`/nix-path-registration` rejection as the ordinary-init controller, while retaining
exact rdinit bootargs. Existing controllers and kernel/bundle files are unchanged.

After one fresh reception receipt, true/proc/uptime must pass. Separate sysfs and
devtmpfs stages then verify exactly one proc/sysfs/devtmpfs mount each. The
selected p2 node must resolve under SD1 `91581000.sdhci1/mmc_host/mmc1`, its MMC
card/block/p2 ancestry must match, partition must be 2, and decimal sysfs device
numbers must equal hexadecimal devnode numbers. The platform component is
source-grounded in `nix/dts/k230-tdisplay-mainline.dts:261`; runtime ancestry remains
a physical gate. No fixed card CID, SD reads or root mount is added to setup.

A fresh private initramfs directory contains one `udevadm test-builtin blkid`
output, under `timeout --signal=TERM --kill-after=2s 20s`, with a 30-second host
receipt window. RC0 and exactly one matching ext4 type and NIXOS_SD label are
required. Raw output is then retrieved once into the protected host UART log,
with a fresh nonce, RC0, exact byte count ≤16384, SHA-256 and following shell
prompt. This preserves metadata before the volatile file disappears at reboot.
No raw retrieval occurs after a failed/unknown probe. Retrieval failure stops
input too. Only complete gates permit one `/bin/reboot -ff`, then receive-only
normal SPL/kernel/login/prompt detection ≤180 seconds and protected postflight.
Unknown completion never prompts an input correction, retry or speculative reset.
Received gates survive errors/timeouts in a private structured result.

Exact initrd inspection (`zstd -dc` plus read-only newc header/symlink walk) showed
`/bin/readlink`, `/bin/stat`, `/bin/timeout` and `/bin/cat` resolve through
`fdxwq7dnxazi7g8bhkv1k8ra0qv3hn7d-initrd-bin-env` to archived coreutils 9.11
`3m27x1rrl0wk30lz5fih10cf1dpqbaa6`; the multicall binary is present.
`/bin/udevadm` resolves to archived systemd 261.2
`srwrq12f962d5prr382vvsq76nfvmm84`. `/bin/sh` resolves to archived bash 5.3p15
`89hsc9vrrk2vr18yp9yrzs365fz490wv`. Host shell fixtures use bash 5.3.15 and
exercise `16#b3`→179 arithmetic; this is source/artifact and host-shell proof,
not execution of that arithmetic on the target.

Narrow proof command:

```sh
python3 -m unittest discover -s tests -p 'test_mainline_drm_*trial.py' -v
openspec validate the-board-runs-a-mainline-kernel --strict
python3 -m py_compile tools/mainline-drm-blkid-trial.py
```

Final result: 138 tests passed in 11.677 seconds (100 existing rdinit, 22
ordinary-init, 16 new blkid); strict OpenSpec validation, Python compilation and
`git diff --check` passed. The combined output is
[the host test log](host-tests-2026-10-03.log).

The new tests use actual generated shell commands with every sysfs/proc/dev path,
mount command and probe redirected to isolated temporary fixtures/stubs. They
cover all setup stages, malformed and mismatched IDs, type/label absence and
duplicates, nonzero/timeout status, stale/duplicate/split receipts, private output
byte bounds/prompt/completion, and stopping before any later input. Orchestration
uses the real serial pump with a fake transport, verifies one successful reboot
and protected postflight, and retains facts without reboot on retrieval failure.
These are host proofs; no injected response is physical evidence.

Operator command after review/landing, using fresh distinct private paths and
root's exclusive reservation:

```sh
python3 tools/mainline-drm-blkid-trial.py \
  --bundle /nix/store/5yqilsfyj35jzrcqjjqilkr6sd47qlms-k230-mainline-drm-trial-boot-files \
  --manifest "$HOME/tmp/k230-mainline-blkid-board/candidate-manifest.json" \
  --normal-report "$HOME/tmp/k230-mainline-blkid-board/normal-report.json" \
  --log "$HOME/tmp/k230-mainline-blkid-board/trial-uart.log" \
  --result "$HOME/tmp/k230-mainline-blkid-board/trial-result.json"
```

Private output/identity reports must not be committed wholesale. This tool does
not start udev, trigger coldplug, mount root, run ordinary `/init`, change clock
policy or mask additional units. A passing probe would establish one metadata
boundary only; ordinary usable root and deliberate real touch remain
**UNVERIFIED**. The process timer cannot guarantee recovery from an uninterruptible
kernel operation. Root owns reviewed execution, physical evidence and recovery.

The coordinator subsequently ran the [physical probe](physical-2026-10-03/README.md):
all metadata/private retrieval gates and automatic protected normal return pass.
The separate ordinary-init/touch acceptance remains open.
