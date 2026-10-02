# MMC shutdown boundary source audit, 2026-10-02

Recorded at `2026-10-02T19:28:50Z`. Evidence class: read-only host source,
installed artifact and DTB inspection. No board, serial, build, register reads
or new physical observation. The stalled operation, affected clock and
automatic restart remain **UNVERIFIED**.

Worktree `/home/jadams/tmp/k230-mainline-mmc-shutdown`, branch
`audit/mainline-mmc-shutdown`, base
`3e6941d77280a96619e72c197cf51bbc77f0231c`. Only this file is owned. No board or
build slot was reserved; the coordinator owns the board. Cached start-status
completed with exit 0.

## Exact candidate and reported boundary

The inspected source is
`/nix/store/jvz4v73g8a67pqwm06v079h6s1cpqr9s-linux-mainline-k230-drm-src`:
Linux pin `72d3fcf802c45d00b300f25b848a93c3a2bd7c7e`, with the optional K230
display/power/restart patches. Kernel
`/nix/store/4wkhxf55y1abg1kg2xd0acsfjqr64j0h-linux-riscv64-unknown-linux-gnu-7.3.0-rc5`
and bundle
`/nix/store/asj7l4zj5jrjkgng4nrcx3y72p7jf7aa-k230-mainline-drm-trial-boot-files`
are the identities in the previous [shutdown audit](../evidence/mainline-restart/shutdown-path-audit-2026-10-02.md).
Fresh SHA-256 inspection of the bundle DTB returned
`48e3d470264db4f816c428a66d72852b5a283ebf679f647e65725573f70f89a1`.
Its sole `init=` selects
`/nix/store/v9qc1sf0iz53s3x6g6vwfyaxghkfpnyk-nixos-system-nixos-26.11.20260919.20b1ddd/init`;
the controller adds volatile `rdinit=/bin/sh`.

The coordinator reports that the corrected quiet trial returned clean
receipt, true, proc mount and uptime, then all six runtime trace stages
(`sys-mkdir`, `sys-mount`, `permissions`, `prior`, `write`, `readback`) with
RC 0 and match true. `initcall_debug` read back `Y`. After real `/bin/reboot -ff`,
shutdown entries included Goodix, display, GPIO and I2C, ending at
`[5.600764] mmcblk mmc1:59b4: shutdown`. The coordinator subsequently reports
the full 180-second normal-return deadline completed: controller exit 1,
`normal login not observed after initrd reboot`, and no later kernel restart
announcement, SPL or login in the 52,918-byte capture. No further input was
sent. A reviewed camera still showed boot text; reset-button recovery was
requested and remained pending. These are coordinator-reported facts, with
provenance in the [physical packet](../evidence/mainline-restart/physical-runtime-ready-2026-10-02/README.md).
The private capture was not opened. This source note supplies no new physical
proof or normal-recovery claim.

## What the last entry establishes

All source line citations below refer to the exact installed source above.
[`drivers/base/core.c:4875`](https://github.com/torvalds/linux/blob/72d3fcf802c45d00b300f25b848a93c3a2bd7c7e/drivers/base/core.c#L4875)
walks devices in reverse registration order. Parent/device mutex acquisition
and `pm_runtime_barrier(dev)` occur before the printed shutdown entry. The
entry precedes the bus callback, with no callback-exit marker and no marker
before the next device's locks/barrier. Therefore this trace establishes that
the MMC card's preceding locks/barrier completed. It leaves both its callback
and a subsequent device's unprinted preparation possible. It also places this
trial beyond the initial global probe drain and cpufreq suspension.

`kernel/reboot.c:288` puts the restart-prepare chain, CPU migration and syscore
shutdown between device shutdown and `Restarting system`. None is established
by a card-entry line. Console visibility beyond the last line is unproved.

## Actual MMC card shutdown sequence and waits

[`drivers/mmc/core/bus.c:143`](https://github.com/torvalds/linux/blob/72d3fcf802c45d00b300f25b848a93c3a2bd7c7e/drivers/mmc/core/bus.c#L143)
calls these stages in order; they are not individual platform-host callbacks:

| Stage | Exact source and possible wait |
| --- | --- |
| Block driver shutdown | `block.c:3279–3296` suspends the main queue and any hardware partition queues. `queue.c:483–493` quiesces dispatch, then claims/releases the host to drain outstanding requests. MMC sets `BLK_MQ_F_BLOCKING` (`queue.c:455`), so `block/blk-mq.c:280–305` waits for SRCU readers, without a local deadline. This is a dispatch grace period, not itself a claim that all I/O completed. |
| Host claim | `core.c:791–830` waits uninterruptibly for another owner to release the host, with no local timeout for ordinary `mmc_claim_host`; the first claim also executes `pm_runtime_get_sync(mmc_dev(host))`. This occurs in queue suspend and again in SD shutdown. |
| Stop rescanning | `core.c:2357–2369` may synchronously disable a card-detect IRQ, then sets `rescan_disable` and calls `cancel_delayed_work_sync(host->detect)`. A currently running detect worker/IRQ can delay this stage; its presence is not established by the trace. This is not `mmc_stop_host()` or driver removal. |
| SD shutdown | `sd.c:1830–1840` assigns `.shutdown = mmc_sd_suspend`; `sd.c:1706–1732` claims the host, chooses optional SD power-off notification or non-SPI deselection, powers off on success, then releases. The card's notification feature bit is not present in the available evidence. |
| Card command | `mmc_ops.c:101–125` deselects with CMD7, argument 0, no response. `core.c:381,408` waits for command/request completion without its own timeout, but SDHCI supplies software timers. `sdhci.c:1727–1734` ordinarily arms 10 seconds; `core.h:18` allows three command retries. `sdhci.c:3238–3291` records timeout and finishes the request under the host lock. Timer execution, lock acquisition and completion work must progress; missing a hardware IRQ alone does not prove indefinite waiting. Notification has additional SD commands and polling, so CMD7 is not guaranteed to be selected. |
| Power off | `core.c:1372–1391` sets clock/power off and invokes initial-state/host `set_ios`. `sdhci.c:2353–2364` disables signal IRQs and reinitializes the controller. `sdhci_reset()` (`sdhci.c:204–236`) polls reset for 100 ms using `ktime_get`; K230 `set_clock(0)` (`sdhci-of-kendryte.c:270–283`) disables the internal clock and returns. These are local bounds, not a bound on the whole callback or on stalled MMIO/timekeeping. |
| Card runtime-PM state | On successful SD suspend, `sd.c:1746–1756` disables runtime PM and marks the card suspended. Runtime-PM draining can itself synchronize pending work/operations; `drivers/base/power/runtime.c:1424–1484` contains an uninterruptible completion wait with no local deadline. |

The Kendryte platform driver has **no `.shutdown` assignment**
(`sdhci-of-kendryte.c:495–514`); its PM operations are system suspend/resume,
not runtime suspend/resume. Its remove-time clock disables are not called by
the MMC card shutdown. Probe chooses `have_phy = 0` specifically for host
`91581000` (`:345–351`), so the PHY's 15,000-iteration sleep/poll loop is not
the expected SD1 power-off branch. Generic controller reset still applies.

## Clock and minimal-initrd context

Fresh `fdtget` shows SD1 clocks `6 1f 6 d`: IDs 31 (core/base) and 13 (bus/AHB).
The node has no additional clock consumers. It matches
[the board DTS](../../nix/dts/k230-tdisplay-mainline.dts) at SD1 address
`0x91581000`, IRQ 144 level-high, with `no-1-8-v` and high-speed enabled.
Driver probe (`sdhci-of-kendryte.c:398–410`) gets/enables only core and bus.
The DT reset entry is not consumed through the reset framework by this driver.

The [earlier exact vendor/mainline comparison](../evidence/mainline-display/physical-2026-10-01/mainline-root-path-audit-2026-10-02.md)
records the vendor's dummy SD clocks and adoption of firmware-enabled gates.
Fresh mainline source confirms ordinary flags-0 SD1 card, AXI and timer gates
(`drivers/clk/clk-k230.c:559,582,639`), distinct from the claimed base/AHB gates.
`drivers/clk/clk.c:1541–1571` can disable an enabled gate with zero software
enable count; `:1580–1595` makes `clk_ignore_unused` bypass the entire late
cleanup. Missing SD clock consumers are thus a grounded hypothesis. Neither a
particular gate's disable nor a stalled request has been observed.

The minimal protocol (`tools/mainline-drm-initrd-shell-trial.py:726–836`) runs
the bare initrd shell, mounts proc and, for tracing, sysfs. It does not mount
devtmpfs, execute `e2label`, mount card root, run the selected `/init`, or start
normal services. Ordinary `init=` remains selected for a full boot, while
`rdinit=` overrides the first initramfs program here. This reduces userspace
card activity but does not exclude kernel scan/detect/runtime work or prior
outstanding requests. Enumeration and partition detection prove neither later
read I/O nor root-filesystem usability. Do not activate `/init` to diagnose this
shutdown boundary.

## Ranked next discriminators, not performed

1. A same-bundle **minimal runtime-trace comparison** with exactly one added
   volatile `clk_ignore_unused` is source-grounded and needs no card read or
   filesystem mount. Preserve quiet boot, readiness/receipt gates, runtime
   parameter permission/write/readback gates, real reboot command and the
   same bounded automatic normal-return deadline. Require the printed exact
   bootargs and `clk: Not disabling unused clocks` marker. Advancing past the
   same boundary or returning normally supports dependence on unused-clock
   cleanup; it cannot identify a gate or prove the printed card callback was
   the original blocker. Equal outcomes leave the hypothesis unresolved.
   The base controller restricts this flag to label mode; extending it to this
   explicit comparison belongs to the coordinator's reviewed controller task.
   Never persist the flag or make it normal boot policy.
2. If that comparison does not resolve the boundary, prepare a separate source
   candidate with fixed begin/end markers at the MMC bus stages above and a
   `device_shutdown` marker before each device's locks/barrier plus after its
   callback. First distinguish block suspend, detect drain, SD suspend and a
   subsequent device; then bracket only the identified host claim, SRCU wait,
   SD command or power-off operation. This avoids treating entry as completion
   or instrumenting a broad device/interrupt survey. Instrumentation can alter
   timing and requires a reviewed build, exact artifact identity and physical
   operator proof; none was produced here.

For either trial, absent final protocol/recovery markers mean unknown state:
stop host input, preserve the private capture and use the coordinator's
documented recovery route. No retry, Ctrl-C, shell exit, guessed register write,
fsck or filesystem activation follows a blocked child. The bounded deadline
limits observation; it cannot force a stalled kernel to restart. Protected
normal files/profile and their pre/postflight verification remain required.

## Host proof and remaining gate

Read `sed`/`rg` slices of the exact installed MMC, block, runtime-PM, clock and
reboot sources; inspect only the bundle bootargs and the SD1 DTB properties;
run `sha256sum` on the DTB. Narrow repository checks:

```sh
git diff --check
openspec validate the-board-runs-a-mainline-kernel --strict
python3 tools/work-status.py
```

Diff check and strict OpenSpec validation passed. Status reads cached Git state
only; the handoff invocation runs idle. No runtime or build check was needed
for this documentation-only change. Review/merge/push remain coordinator work;
physical comparison, localization and automatic normal return remain open.
