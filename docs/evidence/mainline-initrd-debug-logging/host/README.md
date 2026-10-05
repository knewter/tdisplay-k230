# Fixed initrd manager logging: actual host qualification

Evidence class: host preparation of existing immutable artifacts. No UART,
kernel/initrd build or physical logging comparison occurred in this command.

The [reviewed controller](controller-host.md) passed 13 focused fixtures and
36 existing ordinary-controller fixtures, independently rerun. It retains the
default paths, 512-byte transport bound and unknown-no-input policy.

The exact [executed qualifier](qualification-command.py) was copied into a NEW
mode-0700 directory under `~/tmp` and run with:

```sh
python3 qualification-command.py \
  --bundle /nix/store/p2kdar89q7dhwdajjy0mrhmxxzcgsalw-k230-mainline-drm-trial-boot-files \
  --dev /nix/store/24hbalyljs6gn6fzkkl24znv8a0x6jdl-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev \
  --normal-report NEW_PRIVATE_NORMAL
```

Exit 0. [Receipt](result.json) freezes controller revision `ec121e6d` and its
source hash. Actual selected source/config/Image/DT/archive/loader/manifest,
five load sizes/hashes/CRCs and original DT arguments match prior realized
artifact proof. System init and archived systemd `/init` have identical bytes.
The original successful full build is historical; this command did not rebuild.

Selected policy is solely the two planned logging tokens: 356 raw argument
bytes and a 374-byte literal command, versus the unchanged marker-free 317-byte
command. Sole console, masks, fsck skip and synchronous initramfs remain.
Helper, normal expectation and immutable identities match the baseline.

The report matches the preceding independently checked
[NEW ordinary recovery](../../mainline-system-trial/current-p2-ordinary-physical-2026-10-05/recovery.json)
in exact identities, services, boot ID and all eight hashes. These host checks
do not constitute another live board preflight. The private prepared state,
manifest/report and recovery identifiers are not published.

Independent actual-host review **PASS**: executed/public bytes, actual hashes/CRCs,
archive/loader/DT, exact policy and fresh recovery anchor were checked separately.
Physical manager output, usable
ordinary root and panel/glass acceptance remain **UNVERIFIED**. The next
operator command is group 5o.3 in the existing mainline plan; it requires
reviewed host gates and an exclusive board/UART reservation. Unknown capture
completion requires a separate NEW reset and protected recovery.
