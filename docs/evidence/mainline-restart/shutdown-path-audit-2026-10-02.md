# Candidate shutdown path source audit, 2026-10-02

Recorded at `2026-10-02T17:33:48Z`. Evidence class: read-only host source,
installed configuration and candidate DTB inspection. No board input, serial,
build, reset or new physical observation. Restart, callback execution and the
cause of the interrupted return remain **UNVERIFIED**.

Worktree `/home/jadams/tmp/k230-mainline-root-path`, branch
`audit/mainline-root-path`, base `9e9985c46838c58838e5395572cec4492ee47fcc`.
Only this file is owned. No board or build slot was reserved. The completed
cached start-status report was reused as directed by the coordinator.

## Exact candidate and observation boundary

Inspection used these installed artifacts, not an assumed upstream driver:

- Kernel `/nix/store/4wkhxf55y1abg1kg2xd0acsfjqr64j0h-linux-riscv64-unknown-linux-gnu-7.3.0-rc5`;
  `Image` is 38,530,560 bytes, SHA-256
  `70a81b2172710c64463b53693e2e505a4d82ae2f7b644b2fc93cee9016b05330`.
- Source `/nix/store/jvz4v73g8a67pqwm06v079h6s1cpqr9s-linux-mainline-k230-drm-src`,
  Linux pin `72d3fcf802c45d00b300f25b848a93c3a2bd7c7e` plus the repository's
  optional K230 display/power/restart changes.
- Configuration at
  `/nix/store/5wfn6k1lm9fvbwny2qk52admhwm5q4rm-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev/lib/modules/7.3.0-rc5/build/.config`,
  SHA-256 `c5c128ed8b9701f78a0b8bd4f18dacd0d2407ae90eda79a35bba2d9f5ffbeae7`.
- Bundle `/nix/store/asj7l4zj5jrjkgng4nrcx3y72p7jf7aa-k230-mainline-drm-trial-boot-files`;
  its `k230-tdisplay-mainline-drm.dtb` SHA-256 is
  `48e3d470264db4f816c428a66d72852b5a283ebf679f647e65725573f70f89a1`.
- Matching system
  `/nix/store/v9qc1sf0iz53s3x6g6vwfyaxghkfpnyk-nixos-system-nixos-26.11.20260919.20b1ddd`.

The committed [physical minimal report](physical-minimal-2026-10-02/README.md)
records returned receipt, true, proc setup and uptime, then userspace
`Rebooting.` without a candidate kernel restart announcement before operator
intervention and serial disconnect. It does not record a completed automatic
return deadline. Independent normal recovery, boot ID
`08f9455a-1044-4d72-b7ae-bc70d611a8e2`, protected hashes and reviewed camera
Home are separate evidence. The [dispatch audit](restart-dispatch-audit-2026-10-02.md)
places that userspace message immediately before the reboot syscall; it is
not a kernel entry or callback marker. No private capture was read for this
follow-up.

## Before the restart callback

All paths below are relative to the exact source above. `kernel/reboot.c:101–106`
and `288–299` order reboot notifiers, usermode-helper disable, device shutdown,
restart-prepare callbacks, reboot-CPU migration and syscore shutdown before
`Restarting system`. Only then come kmsg dump and RISC-V `machine_restart()` /
`do_kernel_restart()` (`arch/riscv/kernel/reset.c:19–29`). The K230 callback's
terminal loop is therefore downstream of the missing announcement, assuming
that announcement could still reach the capture. Console loss is not excluded.

`drivers/base/core.c:4875–4947` has important gaps in `initcall_debug` tracing:

1. `wait_for_device_probe()` drains deferred work, waits for probe count zero
   and synchronizes async probes (`drivers/base/dd.c:816–824`), then probing
   is blocked and cpufreq suspended. These precede all device trace lines.
2. Devices are walked in reverse registration order, not DT address order.
   Parent and device mutexes are acquired before any trace line.
3. `pm_runtime_get_noresume()` / `pm_runtime_barrier()` precede the line.
   The latter can cancel work synchronously or wait without a local timeout
   for runtime suspend/resume/idle completion
   (`drivers/base/power/runtime.c:1424–1484`). A pending resume can run here.
4. With `initcall_debug`, class `shutdown_pre` or bus/driver `shutdown` is
   printed immediately **before** its callback. There is no callback-exit
   line. Platform devices print the bus entry even if their driver is unbound
   or lacks `.shutdown`; `platform_shutdown()` simply returns in those cases
   (`drivers/base/platform.c:1527–1537`).

Consequently no device lines leaves probe drain, cpufreq, the first locks or
runtime barrier, earlier preparation, and console visibility unresolved. A
last device line leaves both that callback and the next device's unprinted
locks/barrier unresolved. `drivers/base/syscore.c:117–131` prints
`PM: Calling <symbol>` before each syscore shutdown callback; its list mutex
also precedes those lines. None of these are completion markers.

## Enabled nodes and actual driver hooks

`fdtget` on the bundle DTB and the installed `.config` gave:

| Candidate node | Available resources | Shutdown path in exact source |
| --- | --- | --- |
| `/soc/sdhci1@91581000` | `okay`, `canaan,k230-dw-mshc`, IRQ 144/type 4; clock phandle 6 IDs 31/13; reset phandle 7 ID 9 | Kendryte host has probe/remove/PM operations, **no platform shutdown**. SD card MMC bus and `mmcblk` shutdown still apply. SD0 at `91580000` is disabled. |
| `/soc/usb@91500000`, `/soc/usb@91540000` | Both `okay`, `canaan,k230-otg`; IRQs 173/174/type 4; clock phandle 6 IDs 16/17; reset phandle 7 IDs 11/12 | Compatible matches DWC2 in `drivers/usb/dwc2/params.c:366`; `platform.c:808` assigns `dwc2_driver_shutdown`. |
| `/soc/vo@90840000`, `/soc/dsi@90850000` | Both `okay`; VO IRQ 133/type 4 | Canaan VO and DSI platform drivers have **no shutdown** (`canaan_vo.c:918`, `canaan_dsi.c:863`). |
| `/soc/dsi@90850000/panel@0` | `canaan,universal`, absent status (available) | Panel DSI driver has probe/remove but **no shutdown**. DSI core installs its driver wrapper only when a panel supplies `.shutdown` (`drm_mipi_dsi.c:2054–2055`). |
| `/display-subsystem` | `okay`, `canaan,display-subsystem`, power domain phandle 13/index 2 | Master has probe/remove but **no shutdown** (`canaan_drv.c:391–399`). |
| `/soc/power-controller@91103000` | `canaan, k230-sysctl-power`, absent status (available), phandle 13 | K230 provider has probe and managed cleanup, **no shutdown**. |

`CONFIG_MMC`, `MMC_BLOCK`, `MMC_SDHCI_OF_DWCMSHC_KENDRYTE`, `USB_DWC2`,
`USB_DWC2_DUAL_ROLE`, `DRM_CANAAN`, `DRM_CANAAN_DSI`,
`DRM_PANEL_CANAAN_UNIVERSAL`, `SOC_K230_PM_DOMAINS`, `PM`,
`PM_GENERIC_DOMAINS`, `RESET_K230` and `RISCV_SBI` are all built in (`y`).
Availability/configuration/matching are not proof of successful physical
binding. DT IRQ values are interrupt-specifier IDs, not measured IRQ activity.

The concrete waits are:

- **SD card:** `drivers/mmc/core/bus.c:143–161` calls the bound card driver's
  shutdown (`block.c:3293`, `3333`), stops host detection, then SD bus shutdown
  (`sd.c:1838` → `mmc_sd_suspend` → `_mmc_sd_suspend`). `mmc_queue_suspend`
  quiesces the block queue and claims/releases the host to drain outstanding
  requests (`queue.c:483–493`). Host ownership waits with `schedule()` and no
  local timeout (`core.c:791–830`), then runtime-resumes the host. Detection
  stop calls `cancel_delayed_work_sync` (`core.c:2357–2369`). SD suspend claims
  the host again and either sends supported power-off notification or deselects
  cards, then powers off (`sd.c:1706–1732`, `1746–1758`). Request completion
  waits (`core.c:381`, `408`) depend on lower-layer completion/timeout progress;
  they are not locally bounded waits. The power-off busy poll has a 1000 ms
  limit, which does not bound host acquisition or all request completion.
  The host PHY initialization loop has 15,000 iterations with 10–15 us sleeps
  (`sdhci-of-kendryte.c:142–179`); it is not an assigned shutdown callback and
  does not bound the entire MMC shutdown path.
- **USB:** if low-level hardware is enabled, DWC2 shutdown disables global
  interrupts, calls `synchronize_irq`, then disables PHY/clocks/regulators
  (`platform.c:368–376`, `164–187`). IRQ synchronization spins for hard IRQ
  completion and waits for threaded handlers without a local timeout
  (`kernel/irq/manage.c:50–79`, `118–127`). PHY/resource release can acquire
  further framework locks; runtime state and optional PHY presence are unknown.
  USB interface shutdown wrappers also depend on dynamically bound devices;
  the DT alone cannot enumerate those callbacks.
- **Display/power:** `drm_atomic_helper_shutdown` occurs only in Canaan master
  **unbind** (`canaan_drv.c:295–305`), not ordinary `device_shutdown`. Remove
  and managed cleanup are not invoked merely by reboot. The master retains a
  runtime-PM reference after successful probe. Its runtime barrier and other
  devices' barriers still run, so display-related locks/work are not excluded.
  Provider power-on/off polling is bounded to 1000 iterations with `udelay(1)`
  per loop (`k230-power-domains.c:64–113`); repair polling applies only to AI.
  Those bounds assume executing CPU/MMIO progress. They establish neither
  physical completion nor invocation during this reboot.

## Ranked next interpretation, not a cause finding

1. Use the already assigned volatile `initcall_debug` minimal trial to locate
   preparation progress on this exact bundle. Preserve the candidate receipt
   boundary; exclude the initial normal reboot and boot-time initcall lines.
   This separates visible device/syscore progress from wholly unobserved
   preparation, while preserving the lock/barrier gaps above.
2. If the final candidate device line identifies the SD card, prioritize the
   queue/host/detection/card-command path; if it identifies DWC2, prioritize
   IRQ synchronization/resource release. Neither line alone attributes a
   stall: the next device may be waiting before its line. Any further callback
   entry/exit or pre-barrier instrumentation needs a separately reviewed source
   change, matching build and bounded physical recovery.
3. If device lines progress into `PM: Calling`, narrow to syscore/pre-announcement
   work. If the candidate kernel announcement is captured, revisit restart
   dispatch and handler priority/registration with the existing dispatch audit.
   Direct atomic DRM shutdown and provider cleanup rank below these concrete
   paths because this candidate has no ordinary shutdown hooks for them.

The source supplies no evidence that USB, MMC, runtime PM, display or a reset
register caused the failure. In particular, SD enumeration does not prove
root-label reads, filesystem access, root startup or usable mainline login.
No driver disable, guessed MMIO read or arbitrary interrupt survey is proposed.
Retain the existing single-reboot/180-second normal-return controller bound;
serial disconnect or missing return remains recovery-required, with no extra
child command, retry, Ctrl-C or persistent environment change. The board
operator owns recovery and protected normal postflight. This audit adds no
physical pass and closes neither 5d.4 nor 5b.5.

## Host commands and limits

Read-only commands were narrow `rg -n` / `sed -n` reads of the source files
named above, `fdtget -l "$BUNDLE/k230-tdisplay-mainline-drm.dtb" /soc`, and
`fdtget -t s` for compatible/status or `-t x` for interrupts/clocks/resets/
power-domains/phandle on the exact table nodes. Absent properties were checked
as `FDT_ERR_NOTFOUND`; corrected node names were taken from `-l`, not inferred
from unit addresses. Python `pathlib`/`hashlib.sha256` read the installed Image,
configuration and DTB to reproduce the sizes/hashes above. No cmdline or raw
UART contents were published. Validation is the narrow OpenSpec command
`openspec validate the-board-runs-a-mainline-kernel --strict` plus
`git diff --check`; runtime tests are inapplicable to this documentation-only
source inspection.
