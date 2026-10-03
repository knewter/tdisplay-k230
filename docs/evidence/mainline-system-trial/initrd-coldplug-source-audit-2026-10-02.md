# Ordinary-init coldplug boundary: source audit

Read-only host inspection, 2026-10-03T04:16:00Z–04:22:10Z (local date October 2).
Worktree `~/tmp/k230-mainline-initrd-block-audit`, branch
`audit/mainline-initrd-block`, base `62e1eb41a140fa6dcf13fd32a8af62c9c8ead75e`.
No board, UART, build, persistent configuration or kernel changes were performed.
This note supports the still-open mainline usable-root gate; hardware diagnosis
and ordinary-init acceptance remain **UNVERIFIED**.

The selected bundle is
`/nix/store/5yqilsfyj35jzrcqjjqilkr6sd47qlms-k230-mainline-drm-trial-boot-files`,
system `9gdmsrh2igqla1qz0ll97czfw2x42icw-nixos-system-nixos-26.11.20260919.20b1ddd`.
Its initrd resolves to
`/nix/store/jdgads5ibbb0zflglhjfncq8ayc1jbfz-initrd-linux-riscv64-unknown-linux-gnu-7.3.0-rc5/initrd`,
SHA-256 `046c5b012a2b993caa1082926e9928c14bccc0fff456f20f8716c91d13f51842`.
Kernel source is `/nix/store/l0j3rf11mr65wl5x88a9zzma45ciz687-linux-mainline-k230-drm-src`,
upstream pin `72d3fcf802c45d00b300f25b848a93c3a2bd7c7e`.

## Observed phase and limits

Only the suffix after the fresh Linux 7.3.0-rc5 banner of the protected ordinary
begin log was inspected. It contains initrd systemd 261.2, starting coldplug,
started udev manager, and journal service output; its final printed kernel uptime
is 7.235580. Coldplug completion, an EXT4/sysroot mount, switch-root and a mainline
login were not observed. The operator reports the full 180-second readiness
window expired without further input, then protected normal recovery after a
user reset. The operator owns the committed physical log/result/recovery proof.
The last printed unit does not identify a stuck worker, syscall or device.

## Archived ordering

The initrd's archived unit links resolve to
`/nix/store/srwrq12f962d5prr382vvsq76nfvmm84-systemd-riscv64-unknown-linux-gnu-261.2/example/systemd/system/`.
`systemd-udev-trigger.service` lines 10–22 specifies a oneshot before
`sysinit.target`, invoking `udevadm trigger --type=all --action=add
--prioritized-subsystem=module,block,tpmrm,net,tty,input`. It does not request
`--settle`. The tagged trigger implementation enumerates devices and submits
uevents; waiting for completed worker processing is separately conditional on
that option. Thus missing oneshot completion is not itself proof of a worker
settle wait. [systemd v261.2 trigger source](https://github.com/systemd/systemd/blob/v261.2/src/udev/udevadm-trigger.c#L82)

The archived `/nix/store/74smkncxhwn59qjyk6s75rn9qjvw30kf-initrd-fstab` selects
`/dev/disk/by-label/NIXOS_SD` as ext4 root. Archived
`/nix/store/grbingyip4f722kiw8bapi448si7xq55-initrd-udev-rules/60-persistent-storage.rules`
lines 132–139 performs builtin `blkid` before filesystem by-label/by-UUID links.
The archived
`/nix/store/jwsqx59h42k5ilmxr5fiy8kxphj3jgz6-unit-initrd-find-nixos-closure.service/initrd-find-nixos-closure.service`
line 6 requires mounts for `/sysroot/nix/store`. No observed sysroot mount means
closure lookup and activation have not been demonstrated. This identifies a
metadata-probe boundary to test, not a proven cause or a missing driver.

The exact kernel config has built-in EXT4, devtmpfs/mount, MMC/Kendryte SDHCI,
sysfs, Unix sockets, epoll, signalfd, timerfd, inotify, cgroups and file handles.
This rules out those particular omitted config entries; it does not prove
systemd boot compatibility or device progress.

## Narrow next diagnostic

Use the same bundle with the already guarded fresh `rdinit=/bin/sh` protocol.
After fresh proc/sysfs/devtmpfs mount-table receipts and the verified selected
`mmcblk1p2` partition ancestry/devnode, run just:

```sh
/bin/timeout --signal=TERM --kill-after=2s 20s \
  /bin/udevadm test-builtin blkid /sys/class/block/mmcblk1p2 \
  > "$proven_private_volatile_output" 2>&1
```

The pathname above is a protocol placeholder, not an operator-ready command.
A reviewed controller must first create/verify its unique volatile directory,
frame the command with a fresh nonce, and record the actual return status plus
unique exact `ID_FS_TYPE=ext4` and `ID_FS_LABEL=NIXOS_SD` property matches. Keep
raw metadata private. Duplicate/missing/malformed receipts, nonzero status or
unknown completion stop further input; do not retrieve, retry or reboot blindly.
Only fully verified successful gates permit the existing single minimal reboot
and protected normal-return protocol. The 20-second process timer plus host
receipt deadline bounds observation; a blocked kernel operation may prevent
signal/kill completion and still require operator recovery.

The archived `bin` and `usr/bin` links point to
`/nix/store/fdxwq7dnxazi7g8bhkv1k8ra0qv3hn7d-initrd-bin-env/bin`.
Its `udevadm` resolves to the archived systemd 261.2 binary; `timeout` resolves to
`/nix/store/3m27x1rrl0wk30lz5fih10cf1dpqbaa6-coreutils-riscv64-unknown-linux-gnu-9.11/bin/timeout`
(the `coreutils` multicall binary is also archived). No added dependency is needed.

Exact v261.2 `udevadm-test-builtin.c` lines 92–111 constructs a test-builtin event
and invokes the selected builtin. `udev-builtin-blkid.c` lines 559–607 opens the
block device read-only and probes metadata; absent-device handling can return
zero, so zero status alone is insufficient. `udev-builtin.c` lines 135–156 prints
properties to stdout in test-builtin mode. This directly tests one read-only
metadata boundary without starting the daemon, triggering all subsystems,
creating by-label links, mounting root or proving the full ordinary-init path.
[Selected builtin dispatch](https://github.com/systemd/systemd/blob/v261.2/src/udev/udevadm-test-builtin.c#L92),
[read-only blkid probe](https://github.com/systemd/systemd/blob/v261.2/src/udev/udev-builtin-blkid.c#L559),
[property output](https://github.com/systemd/systemd/blob/v261.2/src/udev/udev-builtin.c#L135).

Do not substitute `rd.udev.log_target=console`: the v261.2 udev cmdline parser
accepts log level/trace but no log-target option; unknown options are ignored.
[Exact parser](https://github.com/systemd/systemd/blob/v261.2/src/udev/udev-config.c#L50).

## Reproducibility

Host commands: `zstd -dc <exact-initrd>` followed by a read-only Python newc
header walk (2025 members); `nl -ba` on the exact archived units/rules above;
`rg` on the selected kernel config; `nix-store --query --deriver` and
`nix derivation show` for systemd; and read-only inspection of the candidate log
suffix. The selected systemd derivation records source
`/nix/store/kmjp175p5kwpaab5vcvs97i3xcmay856-source`, absent locally, so the
linked official v261.2 tagged sources were fetched for implementation semantics.
The immutable archived units/binaries remain the actual candidate artifacts.
No secret-bearing transcript or metadata was copied into this note.
