# Mainline ordinary-init coldplug boundary, 2026-10-03

Evidence class: read-only host source, configuration, initrd archive and private
candidate-log inspection. No board, serial, kernel build or source modification.
Ordinary root activation/login and real touch remain **UNVERIFIED**. No blocking
driver or kernel cause is established by this audit.

Worktree `/home/jadams/tmp/k230-mainline-coldplug-drivers`, branch
`audit/mainline-coldplug-drivers`, base
`62e1eb41a140fa6dcf13fd32a8af62c9c8ead75e`; own only this note. No board/build
reservation. Cached `python3 tools/work-status.py` start completed zero; handoff
uses the same command at idle priority.

## Candidate and observed limit

The exact bundle is
`/nix/store/5yqilsfyj35jzrcqjjqilkr6sd47qlms-k230-mainline-drm-trial-boot-files`,
selecting system
`/nix/store/9gdmsrh2igqla1qz0ll97czfw2x42icw-nixos-system-nixos-26.11.20260919.20b1ddd`
and kernel
`/nix/store/9vdk79pa4pm38mlmbflkqh4i4sc9kha0-linux-riscv64-unknown-linux-gnu-7.3.0-rc5`.
Kernel source inspected below is
`/nix/store/l0j3rf11mr65wl5x88a9zzma45ciz687-linux-mainline-k230-drm-src`,
based on Linux `72d3fcf802c45d00b300f25b848a93c3a2bd7c7e` with the opt-in
DRM/restart/five-clock patches. Its configuration is
`/nix/store/7vxby0h1nz78r9qzbqfjjs9vw4x7gpl0-linux-config-riscv64-unknown-linux-gnu-7.3.0-rc5`,
SHA-256 `94e3ab32c17d5ee6f51fcfa0d410bc10927f591db750aafffbd71c7407ef4da8`.
The compressed initrd SHA-256 is
`046c5b012a2b993caa1082926e9928c14bccc0fff456f20f8716c91d13f51842`.

The coordinator's [physical packet](../evidence/mainline-system-trial/physical-2026-10-03/README.md)
records a 180-second ordinary-init readiness timeout with no candidate login,
then operator reset and verified protected normal return (commit `cfcbe592`).
This audit read only the candidate suffix of the private `begin-uart.log`;
the complete private file was 54,143 bytes, SHA-256
`3e6c156677aac67d45ff9ed0d45decda282fe7ee35be60ae68d4218e0cd83026`.
It contains systemd 261.2, coldplug starting, the udev manager reporting started,
and last timestamped progress at approximately 7.236 seconds. It contains
earlier MMC partition, Goodix input and DRM framebuffer registration and
ordinary unused-clock cleanup, without `clk_ignore_unused`. No sysroot ext4
mount, stage2 login, SD timeout/error, panic or Oops was found in this suffix.
These are capture observations, not proof that a particular task blocked or
that kernel timers/interrupts remained healthy throughout the quiet interval.

The prerequisite [read-only root trial](../evidence/mainline-sd1-clocks/physical-no-flag-2026-10-03/README.md)
passed label, `ro,noload` mount, selected init/prepare-root lookup, unmount and
automatic reboot/protected return. That establishes those particular read
paths; it does not establish libblkid enumeration or ordinary writable-root
activation. The ordinary comparison retained the qualified fsck/registration/
growth controls in the [init plan](mainline-init-touch-gates-2026-10-02.md).

## What coldplug asks the kernel to do

The archived trigger unit is a oneshot before sysinit, invoking
`udevadm trigger --type=all --action=add --prioritized-subsystem=module,block,tpmrm,net,tty,input`.
The parallel initrd audit confirms no `--settle`; absence of its completion
message does not distinguish a blocked trigger from workers, other units or
loss of further observable console progress. Re-emitting add events is not
the same operation as re-probing every driver.

Exact kernel source boundaries (paths relative to the source above):

| Path and lines | Operation relevant to coldplug | Remaining limitation |
| --- | --- | --- |
| `drivers/base/core.c:2727–2791,2842–2853` | Device uevent builds major/minor, node, driver/DT and bus/class/type properties; a sysfs uevent write synthesizes an event. | Callback dispatch and allocation can still encounter locks. |
| `drivers/mmc/core/bus.c:59–123`; `drivers/mmc/core/sd.c:725–727` | MMC event and name/serial attributes use already populated card/CID fields. | They do not perform filesystem metadata reads. |
| `block/partitions/core.c:254–262` | Partition event exports cached partition metadata. | This does not exercise block-device data I/O. |
| `drivers/input/input.c:1729–1772` | Input event exports cached name, product, property and capability bitmaps. | Real Goodix event IRQ/I2C activity is a separate path. |
| `drivers/usb/core/driver.c:919–958`; `drivers/usb/core/sysfs.c:856–891` | USB events and binary descriptor reads use existing descriptors; the latter copies cached memory. | Other USB sysfs operations/ongoing asynchronous USB work are not excluded. |
| `drivers/gpu/drm/drm_sysfs.c:229–294` | Status/enabled are cached; modes enumerates the existing list under the mode-config mutex. | A sysfs read can wait on that mutex; this is not evidence that it did. |
| `lib/kobject_uevent.c:320–343,555–655` | Event broadcast takes the uevent socket mutex and uses allocation/netlink with `GFP_KERNEL`. | Generic event delivery is another possible kernel entry boundary, not a diagnosed failure. |

The built configuration sets SDHCI/Kendryte MMC, K230/DWAPB GPIO, DWC2 USB,
Canaan DRM/DSI and Goodix Berlin core/I2C to `=y`. The initrd module list is
empty. `80-drivers.rules` schedules kmod by modalias, but loading these already
built-in drivers is not a new driver-probe explanation. `CONFIG_UEVENT_HELPER`
is disabled. No custom GPIO uevent callback was found in `gpio-k230.c`.
Goodix registers its input device at `goodix_berlin_core.c:644` and IRQ at
`:792`; its input device has no open callback requesting a new I2C probe.
Registration before PID1 is not real-touch proof.

Archived `60-input-id.rules` and `60-persistent-input.rules` inspect input
capabilities/ancestry and make symlinks. `60-drm.rules` uses path ancestry.
Neither is a deliberate touch capture or display modeset. In contrast,
`60-persistent-storage.rules` explicitly invokes `IMPORT{builtin}="blkid"`
for MMC disks/partitions, then derives filesystem label/UUID symlinks. This is
the first specific added block-I/O boundary identified by these rules. The
root fstab requires `/dev/disk/by-label/NIXOS_SD`; closure lookup and activation
come after `/sysroot/nix/store` becomes available.

## MMC waits that a metadata read can encounter

`drivers/mmc/core/core.c:791–828` can sleep while claiming a busy host and then calls
`pm_runtime_get_sync`; there is no local claim deadline. Request completion at
`:403–426` waits on a completion, with retries after returned errors. Generic
SDHCI arms command/data timers at `drivers/mmc/host/sdhci.c:1727–1734` (normally ten
seconds unless the data/busy timeout chooses another interval). Timer and
completion execution remain prerequisites; a host-side deadline cannot prove
they will run. DMA mapping/synchronization exists at `sdhci.c:694,3123–3133`;
no missing-cache-maintenance diagnosis follows from this capture.

The current `drivers/mmc/host/sdhci-of-kendryte.c:313–350,451–471` acquires/enables all five
SD1 clocks before adding the host. Its `:539–558` PM hooks are system-sleep
hooks, with no runtime-PM callbacks or driver shutdown callback. The prior
global-cleanup comparison and subsequent five-clock physical proofs support
the accepted clock-consumer repair, not another speculative clock fix here.
Successful bounded reads/reboot lower the priority of a universal MMC failure;
they cannot exclude request-pattern, concurrency, host-claim or IRQ problems.

## Smallest next discriminator, not performed

Recommend extending only the already proven PID1-shell diagnostic with one
root-partition builtin probe. Preserve fresh receipt/true/proc/uptime gates;
separately establish `/sys` sysfs, `/dev` devtmpfs, the exact block node and a
new volatile output directory in initramfs. Then run exactly once:

```sh
/bin/timeout --signal=TERM --kill-after=2s 20s /bin/udevadm test-builtin blkid /sys/class/block/mmcblk1p2
```

`/bin/udevadm` is the initrd's systemd 261.2 utility, reached through
`/nix/store/fdxwq7dnxazi7g8bhkv1k8ra0qv3hn7d-initrd-bin-env/bin`; do not depend
on candidate Python or an inherited PATH. Redirect both streams to that proven
volatile directory, never the SD filesystem. Report only a fresh complete
begin/end frame, numeric RC and exact unique `ID_FS_TYPE=ext4` and
`ID_FS_LABEL=NIXOS_SD` match booleans;
retain raw output privately. No fsck, mount, root activation or whole-subsystem
trigger is part of this probe. The parallel source audit of official
[v261.2 test-builtin:92–108](https://github.com/systemd/systemd/blob/v261.2/src/udev/udevadm-test-builtin.c#L92-L108)
confirms only the selected builtin runs in its test event context;
[blkid:563–607](https://github.com/systemd/systemd/blob/v261.2/src/udev/udev-builtin-blkid.c#L563-L607)
opens the device read-only and probes metadata. RC0 alone is insufficient,
including an absent-device case. The source check is not execution of the
installed helper. `/bin/timeout` is the archived coreutils 9.11 utility.

Use one bounded host wait (for example 30 seconds, covering the child timeout).
TERM/KILL cannot guarantee return from an uninterruptible kernel wait.
A known failed RC/missing
label is a failed diagnostic and may use the established acknowledged reboot
path only while protocol health is proven. Missing/truncated final markers or
a blocked child remain unknown: no retry, Ctrl-C, guessed input or reboot;
preserve the capture and use the proven operator-reset/protected-normal route.
The wait is not a hardware watchdog or automatic recovery guarantee.

A returned RC0/type/label match separates this particular metadata read from the
ordinary failure but does not prove daemon processing, netlink event delivery,
full disk/other partition enumeration or root activation. If it succeeds,
the next investigation should expose the exact trigger/unit/worker state
through separately reviewed initrd logging, rather than change drivers from
silence. That initrd work belongs to the parallel restart/controller agent.

Host checks: `openspec validate the-board-runs-a-mainline-kernel --strict` and
`git diff --check`. No new test/build or physical result; task 5b.5 stays open.
