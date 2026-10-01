# Mainline DRM matching boot-path preparation

This is host build evidence and an unperformed operator procedure for task
5b.5 of `the-board-runs-a-mainline-kernel`. No board, serial port, card, boot
environment, or normal system profile was changed. The physical task remains
unchecked. The separate `k230-mainline-drm-trial` configuration extends the
mainline console profile with the DRM candidate kernel; it does not enable or
claim a graphical shell. `kernelMainlineDrmTrialBootFiles` supplies that
system's Image, DTB with its `init=` path, wrapped initrd, volatile
`bootargs.txt`, closure inventory, and Nix registration stream.

The original `kernelMainlineDrmBootFiles` remains Image+DTB only. Do not pair
that bundle with an arbitrary vendor or console initrd. The trial's own
closure must exist on an ext4 root labelled `NIXOS_SD`; the generated initrd
uses `root=fstab` and the inherited label-based mount, without guessing MMC
Linux enumeration. No system profile change is required: `init=` selects the
exact trial system directly.

Display power remains **UNVERIFIED** for this candidate. The existing vendor
board evidence in `docs/evidence/dsi-phy-hang.md` records DSI reads of
`0xffffffff` until the display power-domain runtime-PM reference was held.
The mainline candidate has no `sysctl_power` provider and omits its phandle.
Matching the boot path does not repair that dependency. Serial/root boot,
panel illumination, and deliberate touch interaction need separate physical
observations; a failing panel is not proof that the root staging failed.

## Host proof

Build the combined output (its dependencies include the matching system):

```sh
flock /tmp/k230-nix-build.lock nix build .#kernelMainlineDrmTrialBootFiles \
  --no-link --print-out-paths --max-jobs 1 --cores 4
```

Run the inspector with the flake-pinned native `dtc` on PATH:

```sh
nix shell --inputs-from . nixpkgs#dtc --command \
  python3 tools/mainline-drm-trial-inspect.py <output-path>
```

It checks that
Image matches the system's selected kernel, both DTB and volatile environment
select the matching `init=`, the U-Boot header/payload CRCs are valid, and the
wrapped initrd is byte-identical to that system's initrd. The committed
companion log records the result and output inspection. The combined output
is `/nix/store/9v5jwcg97kp96jfj6nll4a4yixxzqh2x-k230-mainline-drm-trial-boot-files`,
selecting system
`/nix/store/jz3dwcq9wq99jl7111zcg4bpcxz92i6k-nixos-system-nixos-26.11.20260919.20b1ddd`
and the previously built DRM kernel
`/nix/store/qa041skh6iy7rmx86c5zfn2xyq036f0g-linux-riscv64-unknown-linux-gnu-7.3.0-rc5`.
All artifact checks passed; the closure inventory has 629 paths. The combined
build needed the missing kernel auxiliary outputs, so it rebuilt that same
kernel derivation before packaging the NixOS initrd/system. `nix flake check
--no-build` and strict change validation also passed.

## Offline root staging — operator only, not performed

Reserve the board/card first. Shut down normally before removing the card.
Mount its existing root partition read-write at an operator-chosen path; do
not format or replace it. The commands below intentionally fail unless the
mount is ext4 with the expected label. Build on the host first, then set
`trial_bundle` to the output above and `trial_root` to the mounted root.

```sh
set -eu
trial_bundle=$(nix build .#kernelMainlineDrmTrialBootFiles --no-link --print-out-paths)
trial_root=/path/to/mounted/root
mountpoint -q "$trial_root"
test "$(findmnt -nro FSTYPE --target "$trial_root")" = ext4
test "$(findmnt -nro LABEL --target "$trial_root")" = NIXOS_SD
trial_system=$(readlink "$trial_bundle/system")
test -x "$trial_bundle/system/init"
nix path-info --closure-size "$trial_system"
df -h "$trial_root"
# Record the known-good profile; leave it and /sbin/init unchanged.
readlink "$trial_root/nix/var/nix/profiles/system"
sudo mkdir "$trial_root/var/lib/k230-mainline-drm-trial"
sudo rsync -aH --recursive --ignore-existing --files-from="$trial_bundle/store-paths" \
  / "$trial_root/"
# No output is expected: verify every closure file against the source.
sudo rsync -aH --recursive --checksum --dry-run --itemize-changes \
  --files-from="$trial_bundle/store-paths" / "$trial_root/"
sudo cp "$trial_bundle"/{Image-mainline-drm,k230-tdisplay-mainline-drm.dtb,initrd.uimg,bootargs.txt,SHA256SUMS,registration} \
  "$trial_root/var/lib/k230-mainline-drm-trial/"
(cd "$trial_root/var/lib/k230-mainline-drm-trial" && sha256sum -c SHA256SUMS)
test -x "$trial_root$trial_system/init"
# Keep the trial closure rooted without selecting/activating it.
sudo mkdir -p "$trial_root/nix/var/nix/gcroots"
sudo ln -s "$trial_system" "$trial_root/nix/var/nix/gcroots/mainline-drm-trial"
readlink "$trial_root/nix/var/nix/profiles/system"
sync
```

Confirm adequate free space before copying. Stop if rsync verification
reports changes or the normal profile differs.
The registration stream is included for an operator who needs Nix database
registration later (`nix-store --load-db` on the board); registration is not
system activation and is not needed to select the boot's explicit `init=`.
Unmount the root cleanly, reinstall the card, and retain its normal boot
partition and files. These commands create no flash image and do not copy
anything into the normal boot partition.

## Recoverable manual U-Boot trial — operator only, not performed

With the single-board reservation held, start a serial capture using the
change's named proof command:

```sh
flock /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=10
```

Interrupt autoboot manually. Preserve the console transcript. The load
addresses and `bootm` flow below follow the existing recoverable RVV trial
in `tools/rvv-board-boot.py`. The card boot/root partitions are the existing
`mmc 1:1` and `mmc 1:2`; inspect `mmc list`/partition contents and stop if
they do not match. Use the normal boot partition's known-good OpenSBI wrapper.
Every load must succeed. Compare its byte count to the artifact size before
proceeding; compare U-Boot `crc32` with a host `zlib.crc32` of each file if
load integrity is in question.

```text
ext4load mmc 1:2 0x7000000 /var/lib/k230-mainline-drm-trial/bootargs.txt
setenv trial_args_size ${filesize}
ext4load mmc 1:1 0x8000000 /fw_jump_add_uboot_head.bin
ext4load mmc 1:2 0x200000 /var/lib/k230-mainline-drm-trial/Image-mainline-drm
ext4load mmc 1:2 0x8400000 /var/lib/k230-mainline-drm-trial/k230-tdisplay-mainline-drm.dtb
ext4load mmc 1:2 0x9000000 /var/lib/k230-mainline-drm-trial/initrd.uimg
env import -t 0x7000000 ${trial_args_size}
printenv bootargs
bootm 0x8000000 0x9000000 0x8400000
```

Confirm `bootargs` names the trial bundle's exact `system/init` before boot.
Do not run `saveenv`, `k230_set_dtb`, or change `bootcmd`/normal selectors.
If a load fails, stop and `reset`. If Linux hangs, power-cycle and let normal
autoboot proceed; all candidate environment changes above are volatile and
normal files/profile remain selected. If U-Boot remains at a prompt after
reset, follow the already recorded known-good boot flow, not a candidate
selector. Record the subsequent vendor kernel/login as restoration proof.

A successful root trial must record `uname -a`, `/proc/cmdline`,
`readlink /run/current-system`, `findmnt /`, and relevant kernel probe output.
Identify the touch event node with `cat /proc/bus/input/devices`, then record
`timeout 15 od -An -tx1 /dev/input/eventN` while deliberately pressing and
releasing the glass (replace `eventN` with the identified node). Describe the
physical action and timestamps alongside the output. Capture a panel
photograph separately.
Do not report injected events or kernel object builds as touch evidence.
Commit the serial log, photograph, interaction record, and normal restoration
log before completing task 5b.5. A runtime observation is required for the
candidate's display-power behavior.
