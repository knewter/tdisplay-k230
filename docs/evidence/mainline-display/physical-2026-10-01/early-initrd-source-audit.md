# Exact early-initrd source audit

Read-only follow-up to the two physical attempts, 2026-10-01. This is an artifact/source audit, not an additional board trial or a cause established on hardware.

The matching bundle is `/nix/store/gf3aqks2dg0z3ksz33ysfprnlbk83vw3-k230-mainline-drm-trial-boot-files`. Its initrd is `/nix/store/wpc38h8vcriymblrw07qzg8prd8dp541-initrd-linux-riscv64-unknown-linux-gnu-7.3.0-rc5/initrd`. The original bundle was reproduced from local port commit `0d33011b9de688e2f7d6dcbfecc169b66828018e`, landed as `e3c47141`. The kernel source base in `nix/kernel-mainline-src.nix` is upstream `72d3fcf802c45d00b300f25b848a93c3a2bd7c7e`.

The CPIO listing was inspected with:

```sh
zstd -dc /nix/store/wpc38h8vcriymblrw07qzg8prd8dp541-initrd-linux-riscv64-unknown-linux-gnu-7.3.0-rc5/initrd |
  cpio -itv 2>/dev/null
```

`/init` links to `/nix/store/srwrq12f962d5prr382vvsq76nfvmm84-systemd-riscv64-unknown-linux-gnu-261.2/lib/systemd/systemd`, rather than a shell script. `/bin` links to `/nix/store/fdxwq7dnxazi7g8bhkv1k8ra0qv3hn7d-initrd-bin-env/bin`; `sh` there links to `/nix/store/89hsc9vrrk2vr18yp9yrzs365fz490wv-bash-interactive-riscv64-unknown-linux-gnu-5.3p15/bin/sh`, then `bash`. The archive contains that executable Bash ELF, 1,133,888 bytes, mode 0555. A direct CPIO parser additionally checked its ELF magic. Nothing was extracted or rebuilt for this audit.

Upstream systemd v261.2 resolves to commit `4925d9f07fc697efccd98a93046ff535b8832445`, obtained by `git ls-remote --tags https://github.com/systemd/systemd.git refs/tags/v261.2 'refs/tags/v261.2^{}'`. The source audit is paired with the exact initrd package identity; it does not claim absence of downstream Nixpkgs patches.

The truncated `Setting '/proc/sys/kernel/printk` message matches the debug message in [`sysctl_write_full()`](https://github.com/systemd/systemd/blob/4925d9f07fc697efccd98a93046ff535b8832445/src/basic/sysctl-util.c), before its write operation. [`disable_printk_ratelimit()`](https://github.com/systemd/systemd/blob/4925d9f07fc697efccd98a93046ff535b8832445/src/core/manager.c) requests `kernel/printk_devkmsg=on`. [`main.c`](https://github.com/systemd/systemd/blob/4925d9f07fc697efccd98a93046ff535b8832445/src/core/main.c) calls this during early manager setup, before security/MAC setup, generators and target jobs. The partial line proves neither completion of the sysctl write nor a udev failure. An emergency target would not bypass this early setup. Console-output or interrupt trouble remains a hypothesis.

## Next diagnostic, not performed

Use the same load count/CRC checks and matching original bootargs. Substitute the existing initrd shell before systemd starts:

```text
env import -t 0x7000000 0xd3
setenv bootargs "${bootargs} rdinit=/bin/sh"
printenv bootargs
bootm 0x8000000 0x9000000 0x8400000
```

Check the retained `init=/nix/store/k9f4r2i9k9qj58z8z4l2kssy9rpwxxm1-nixos-system-nixos-26.11.20260919.20b1ddd/init`. Do not save the environment or replace normal boot files. A responsive shell would establish early userspace/serial execution, not a stage2 root login, display usability or real touch. Keep PID1 running; exiting it would panic. Restore the unchanged normal boot selection afterward and commit the actual result. No further trial is claimed here.
