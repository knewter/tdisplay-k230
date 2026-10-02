# Read-only root mount/path controller: host proof, 2026-10-02

Bounded task 5b.5 preparation, worktree
`/home/jadams/tmp/k230-mainline-root-path`, branch `audit/mainline-root-path`,
base `48c83245f797364ee43c828a6183cc3e96ae4ad8`. Owned changes are the initrd
trial controller, its test file, this note, and an append-only preparation note
in the change's tasks. No board, serial device, physical mount, staging, reboot,
Nix build or build slot was used. Task 5b.5 remains unchecked.

`--mode root-mount` repeats receipt, true, proc mount/uptime, devtmpfs/node and
the single read-only exact root-label check within its own trial. A previously
observed label is not reused as the gate. A complete label nonmatch or nonzero
RC skips root mounting and follows the existing recovery path with a failed
diagnostic. Failed minimal/device prerequisites retain recovery-required stop
behavior. `--ignore-unused-clocks` remains restricted to label mode.

Only after label RC 0 plus exact `NIXOS_SD` match, individually bracketed stages:

1. Confirm that `/proc/mounts` contains no `/sysroot` mount; create `/sysroot`
   with `/bin/mkdir -p /sysroot` and require it to be an empty directory using
   builtins, including hidden entries.
2. Invoke exactly one
   `/bin/mount -t ext4 -o ro,noload /dev/mmcblk1p2 /sysroot`.
3. Scan `/proc/mounts` with shell builtins, without printing it. Require exactly
   one `/sysroot` entry, source `/dev/mmcblk1p2`, filesystem `ext4`, and exact
   `ro` plus `noload` or `norecovery` option tokens. Strings such as
   `errors=remount-ro` do not satisfy `ro`.
4. Separately run builtin `test -x /sysroot${SELECTED_SYSTEM}/init` and
   `test -x /sysroot${SELECTED_SYSTEM}/prepare-root`. The selected immutable
   system comes from the already validated bundle/manifest. A failed first
   lookup skips the second. Neither executable is run.
5. If the mount returned success or the completed mount-table check observed
   a mount, invoke one `/bin/umount /sysroot`. After returned success, separately
   require no remaining `/sysroot` entry before reporting a diagnostic pass.
   A returned unmount failure is not retried and cannot produce a pass.

Each stage prints fixed `K230_RDINIT_ROOT_BEGIN TOKEN STAGE=...` and
`K230_RDINIT_ROOT_END TOKEN STAGE=... RC=...` lines. Mount-table stages add only
`MOUNTED=0|1`. Parsers require unique complete ordered fresh-token pairs and
bounded RCs. The post-unmount stage has its own `after-umount` identity, so the
initial unmounted marker cannot satisfy it. Known filesystem/path failures
preserve a failed diagnostic even if normal recovery later succeeds. No raw
label, cmdline, filesystem listing or mount table is emitted by this mode.

External mount, executable lookup and unmount stages have 60-second marker
bounds; other stages retain the 30-second default. Missing/invalid completion
at any stage stops all further input, including cleanup and reboot. The outer
controller records `mainline-initrd-root-mount-unknown-v1`, status
`recovery-required-unknown-no-reboot-requested`, with the unknown stage.
Completed results use `k230-initrd-root-mount-v1`; failed initial prerequisites
use `k230-initrd-root-mount-prerequisite-failure-v1`. The existing bounded
reboot/180-second normal-login/protected-postflight flow follows only completed
diagnostics. A timeout stops observation, not a blocked I/O request. Keep the
board reservation until actual protected normal recovery is verified.

## Exact artifact grounding and limits

The historical gf3 bundle's initrd is
`/nix/store/wpc38h8vcriymblrw07qzg8prd8dp541-initrd-linux-riscv64-unknown-linux-gnu-7.3.0-rc5/initrd`.
A read-only newc walk of its zstd output confirms `/bin/mount` and `/bin/umount`
in `fdxwq7dnxazi7g8bhkv1k8ra0qv3hn7d-initrd-bin-env`, resolving through the
util-linux bin output into
`wj2ib2qm1znrpv2i8b433v69m07m86ll-util-linux-minimal-riscv64-unknown-linux-gnu-2.42.3-mount/bin/`.
`/bin/findmnt` and `/bin/mountpoint` are absent from that bin environment, so
this mode uses builtin scans instead. Receipt sets volatile `PATH=/bin:/sbin`;
external utilities use absolute names. Recheck utilities in the selected new
bundle before physical use.

The pinned mainline ext4 source at
`/nix/store/vnzm30w6v4na0ylpw8vclyn7dn9vvkf0-linux-mainline-k230-drm-src/fs/ext4/super.c`
(upstream base `72d3fcf802c45d00b300f25b848a93c3a2bd7c7e`) maps both `noload`
and `norecovery` to NOLOAD. NOLOAD bypasses journal loading; its option display
uses the first matching spelling, `norecovery`. A read-only mount without this
flag would not establish the no-replay boundary. A dirty filesystem can yield
an incomplete no-replay view; a failed lookup here does not prove corruption
or absence of a recoverable closure.

This is a `rdinit=/bin/sh` diagnostic, not an ordinary `/init` boot. The original
archive's `/init` is systemd 261.2. Its fstab has root `x-initrd.mount` and pass
1 without `ro,noload`; closure discovery leads to activation and switch-root.
The candidate `prepare-root` calls activation and creates/changes filesystem
state. This mode does not invoke fsck, replay, chroot, activation, switch-root,
candidate init or prepare-root. Mount/path success would establish only a
direct filesystem and executable lookup, not NixOS activation or root login.
The [root-path audit](mainline-root-path-audit-2026-10-02.md) records that separate
ordinary-init boundary. `rootflags=ro,noload` must not be casually treated as
overriding the existing fstab policy; the pinned upstream
[systemd generator manual](https://github.com/systemd/systemd/blob/4925d9f07fc697efccd98a93046ff535b8832445/man/systemd-fstab-generator.xml)
explicitly distinguishes those settings.

## Host checks and remaining operator gate

On 2026-10-02, UTC observation `2026-10-02T17:02:20Z`, these commands passed:

```sh
python3 -m unittest discover -s tests -p test_mainline_drm_initrd_shell_trial.py
python3 -m py_compile tools/mainline-drm-initrd-shell-trial.py tests/test_mainline_drm_initrd_shell_trial.py
openspec validate the-board-runs-a-mainline-kernel --strict
git diff --check
```

The final suite has 62 tests, retaining the earlier 49. Root tests cover label
and setup gates, one mount, selected-system paths, strict flag tokens and mount
identity, cleanup after known failures, no retry/input after unknown markers,
and distinct outer-controller unknown results. Generated shell scans execute
under both host sh and bash with isolated mount tables, including false final
entries, aliases, wrong source/type, missing flags, duplicates and missing
tables. Generated mount/unmount commands execute only temporary stubs; path
tests inspect fixture executables and confirm they are not executed. Host
fixtures use no actual host mount or board lock.

UNVERIFIED: no mainline mount, closure lookup, usable root, automatic restart or
touch result was obtained. After reviewed matching bundle/manifest/utility
proof, physical automatic recovery, board reservation and fresh protected normal
report, the future operator command is (not run):

```sh
python3 tools/mainline-drm-initrd-shell-trial.py \
  --bundle /nix/store/EXACT_REVIEWED_RESTART_BUNDLE \
  --manifest /path/to/MATCHING_MANIFEST.json \
  --normal-report /path/to/FRESH_STRUCTURED_PROTECTED_NORMAL.json \
  --mode root-mount
```

Replace placeholders with reviewed exact artifacts. Keep normal profile and
protected card boot files selected. Review, merge, push and physical work remain
with the coordinator; full `/init` activation is not authorized by this probe.
