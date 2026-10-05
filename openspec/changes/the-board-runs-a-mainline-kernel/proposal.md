## Current evidence status (2026-10-02)

The original host milestones below are historical build records. Committed
physical trials in
`docs/evidence/mainline-display/physical-2026-10-01/README.md` observe Linux
7.3-rc5, DRM/fb0, Goodix input registration and photographed panel boot text,
but no usable mainline root or deliberate touch. Later PID1 shell probes
reached `/bin/true`; the minimal trial's systemd reboot refusal did not reach
the kernel. The protected normal system was independently restored by an
operator power cycle, recorded in
`docs/evidence/mainline-display/physical-2026-10-01/minimal-probe-recovery-2026-10-02/README.md`.
These are partial boot/probe/recovery observations, not product acceptance.
Task 5d.4 now has physical proof for the targeted five-clock candidate
without `clk_ignore_unused`: ordinary clock cleanup, kernel restart → SPL →
protected normal return with fresh identity and unchanged boot hashes,
recorded in `docs/evidence/mainline-sd1-clocks/physical-no-flag-2026-10-03/README.md`.
The earlier global-clock comparison remains historical evidence. Task 5b.5
stays open for ordinary NixOS root activation and deliberate touch.

## Why

Today's kernel is a pinned vendor fork, `ruyisdk/linux-xuantie-kernel` @
`7d4e1f444f461dbe3833bd99a4640e7b6c2cd529` (Linux 6.6.36, `nix/kernel-src.nix`),
carrying eleven local patches (`nix/kernel.nix`) that exist only because that
tree is old, undermaintained upstream, and missing fixes this board's bring-up
needed: a bounded DSI PHY wait, a bounded thermal loop, an RTC day-of-month
mask bug, a DCS-read backport, a touch driver backport, and more. Nobody
outside this project reviews that tree, security fixes land on it only if
someone backports them by hand, and every future Linux feature (newer
schedulers, newer DRM, newer RISC-V vector support) requires either a manual
backport or staying frozen at 6.6 forever.

Mainline Linux has been gaining real Canaan K230 support since late 2025:
`arch/riscv/Kconfig.socs`' `ARCH_CANAAN`, a pinctrl driver
(`drivers/pinctrl/canaan/pinctrl-k230-iomux.c`, `PINCTRL_K230`), a reset
driver (`drivers/reset/reset-k230.c`, `RESET_K230`), a clock driver
(`COMMON_CLK_K230`), and a basic `arch/riscv/boot/dts/canaan/k230.dtsi` +
`k230-canmv.dts`/`k230-evb.dts` all merged for the v7.3 window (too late for
v7.2, confirmed: `git show v7.2:arch/riscv/boot/dts/canaan/` lists only K210
files). A USB-PHY driver and its device-tree binding for K230 were also
accepted upstream (Vinod Koul, `lkml.org/lkml/2026/2/27/1255`) but the DT node
wiring it into `k230.dtsi` has not landed as of this writing. An SDHCI series
(`sdhci-of-dwcmshc.c` reuse, v5 as of March 2026, "tested successfully on
CanMV-K230-V1.1 with AP6212 SDIO on MMC0 and MicroSD on MMC1") is still under
review on `linux-riscv`, not yet merged into any tagged or `master` tree
checked here. There is still no mainline display (`canaan-drm`/VO/DSI),
touch, audio, RTC, PMU/power-key, thermal, ADC, PWM, GPIO, or crypto driver
for this SoC — `panel-canaan-universal.c`, `canaan_drv.c`, `rtc-k230.c`,
`canaan_thermal.c`, `k230-adc.c`, `k230-pmu-pwrkey.c`, `canaan_k230_inno.c`
all return HTTP 404 from `torvalds/linux` today (checked directly via
`gh api repos/torvalds/linux/contents/<path>`, 2026-09-29); the GT9895 touch
driver this project backported (`goodix_berlin`) is, unusually, already
upstream on its own merits, since it was itself a v6.12 mainline driver we
backported onto the older vendor tree.

So mainline cannot run this handheld's shell today, and won't be able to for
some time — the display stack alone is a from-scratch driver effort with no
public work in progress found. But mainline *can* now be built for this SoC,
and getting there — a real cross-build, a real device tree, a real forward
port of what applies — is work worth doing in parallel with the vendor-kernel
image, so that: (1) the day mainline gains a usable display driver, this
project is not starting from zero; (2) our patches that fix generic-Linux
bugs (not Canaan-driver bugs) have a known home; and (3) the board has a
path to a maintained, security-patched kernel for its console/network/storage
functions even before the display works.

## What Changes

- Publish a researched hardware/mainline-support inventory (this document +
  `docs/research/mainline-kernel-inventory.md`) covering every function
  `docs/research/board-capability-inventory.md` already names, with a fourth
  column this project has not written before: mainline driver status,
  cited by file existence (`gh api .../contents/<path>` returning 200 vs.
  404) and, where a driver is genuinely missing, the exact in-review patch
  series if one exists.
- Add a **second, parallel** kernel/device-tree/boot-files build
  (`.#kernelMainline`, `.#deviceTreeMainline`, and a boot-files output) pinned
  to a specific mainline commit that carries basic K230 support
  (`v7.3-rc5`, the newest tag with `arch/riscv/boot/dts/canaan/k230.dtsi`
  present; there is no stable release with K230 support yet — `v7.2` does not
  have it). This does **not** touch `.#kernel`, `.#deviceTree`,
  `nixosConfigurations.k230`, or `.#sdImage` — the shipped image keeps
  booting the vendor Xuantie kernel unchanged.
- Forward-port whatever of our eleven vendor-kernel patches target hardware
  or bugs mainline already covers (expected: none of the display/audio/RTC/
  power-key ones, since mainline has no driver for any of them to patch;
  the vector-toolchain-probe fix turns out to be already fixed upstream,
  see inventory). Record exactly which patches port, which do not, and why,
  rather than silently dropping any.
- Define a phased plan whose first milestone is host-provable
  (`nix build .#kernelMainline`, `.#deviceTreeMainline`) and names the actual
  first hardware milestone as "boots to a serial console" — not "SD rootfs" —
  because mainline has no merged storage driver for this SoC yet; SD rootfs
  and USB networking are later milestones explicitly gated on upstream
  patches this project does not control the timeline of.
- Add `system/kernel` requirements recording that a parallel mainline build
  exists, that the default system is unaffected by it, and what its current
  hardware ceiling is — the same pattern already used for the optional RVV
  trial kernel in this same capability.
- **Milestone 1, coordinator-directed continuation of this same change**:
  forward-port GPIO (`gpio-k230.c`), SD/MMC (`sdhci-of-kendryte.c`) and USB
  (`dwc2` parameter/register hunks) from the pinned vendor tree onto the
  mainline pin, with matching device-tree nodes; add a full NixOS system
  variant (`nixosConfigurations.k230-mainline-console`) that boots this
  kernel, with the out-of-tree Wi-Fi kernel module excluded (no expectation
  it compiles against a kernel seven major versions newer than its origin);
  and produce matching boot files (Image, a DTB with this system's real
  bootargs baked in, and its initrd wrapped for U-Boot) so a future
  one-shot boot attempt has everything staged. Two real vendor-to-mainline
  API migrations were found (by a failed build, not by inspection) and
  fixed against mainline's own already-migrated reference drivers — see
  `docs/research/mainline-kernel-inventory.md` and design.md decisions 7–10
  for the full account. Still entirely host-only; no board action taken.

## Capabilities

### Modified Capabilities

- `system/kernel`: adds requirements for the parallel mainline build
  (existence, non-default status, and its recorded hardware ceiling).
  Existing requirements (the vendor kernel is pinned and its patches
  recorded; the RVV trial retains normal recovery; vector execution is
  gated by kernel/context support) are unchanged.

### New Capabilities

None. This is infrastructure inside the existing `system/kernel` capability,
not a new user-observable capability — nothing about what the shipped
handheld does changes.

## Impact

`nix/kernel-mainline-src.nix`, `nix/kernel-mainline.nix`,
`nix/dts/k230-tdisplay-mainline.dts`, `nix/device-tree-mainline.nix`,
`nix/kernel-mainline-boot-files.nix`, `nix/patches/mainline/{gpio-k230.c,
sdhci-of-kendryte.c}`, `flake.nix` (new package/nixosConfigurations outputs
only, no changes to existing ones), `docs/research/mainline-kernel-inventory.md`,
`openspec/specs/system/kernel/spec.md`. No change to `nix/kernel.nix`,
`nix/kernel-src.nix`, `nix/device-tree.nix`, `nix/k230.nix`,
`nix/hardware.nix`, `nix/sd-image.nix`, `nix/shell.nix`, or any existing
`nixosConfigurations` output — confirmed by `git diff --stat` against each
after every task group, including the milestone-1 continuation. The original
functional proof was host-only (cross-builds, including a full NixOS
system-closure build). Later physical trials obtained partial boot/probe
evidence as summarized above; usable root and deliberate touch remain named open gates for the board
operator; automatic restart is now physically proved for the targeted five-clock
candidate without the temporary clock bypass.


The isolated DRM continuation also provides `k230-mainline-drm-trial` and
`kernelMainlineDrmTrialBootFiles`: a console system built against the DRM
candidate, its matching initrd/bootargs and closure inventory, and an offline
root-stage/manual U-Boot procedure. `nix/mainline-drm-trial.nix`,
`tools/mainline-drm-trial-inspect.py`, and
`docs/evidence/mainline-display-boot-preparation.md` own this host-only
preparation. The normal system profile and boot files remain selected; card staging
and partial physical boot/probe evidence are now committed, while task
5b.5 remains open for usable root and deliberate touch.


A further bounded, coordinator-authorized continuation forward-ports the
vendor's K230 genpd controller and binding into the optional DRM candidate
and wires the display domain before a physical trial. Prior vendor-board
DSI failure/resolution evidence grounds this dependency; mainline runtime
behavior remains UNVERIFIED. This touches only
`nix/kernel-mainline-drm.nix`, `nix/patches/mainline/k230-power-domains.c`,
the local power-domain binding header, the DRM DTB builder/DTS and candidate
DRM master's runtime-PM error handling. Console/default variants and clock/
reset choices remain outside this continuation. Full candidate/DTB/boot-bundle
builds prove the source artifacts; task 5b.5 still requires the board.


## Bounded continuation: recoverable optional mainline restart

A console operator cannot yet rely on a mainline diagnostic trial returning
itself to the protected normal system. The 2026-10-02 minimal trial reached
the initrd shell, but systemd refused its reboot request before the kernel
was called; subsequent normal recovery needed an operator power cycle.
The read source audit in
`docs/evidence/mainline-display/physical-2026-10-01/mainline-restart-source-audit-2026-10-02.md`
finds no advertised SBI SRST in the candidate logs and no restart handler in
mainline's peripheral reset driver. This is a separate recovery dependency,
not an explanation for the missing usable NixOS root.

Group 5d adds the pinned vendor K230 restart register sequence to the
optional `kernelMainlineDrm` only, using the pinned mainline managed restart
API, checked probe-time mapping and registration, and device-owned cleanup.
The source/API object proof, complete kernel build, matching trial bundle,
and physical restart/normal recovery are separate gates. Record host proof
under `docs/evidence/mainline-restart/`; keep physical restart UNVERIFIED and
5b.5 open until their named observations exist.

This continuation owns `nix/kernel-mainline-drm.nix` and a narrow patch
under `nix/patches/mainline/`. No stage-1/OpenSBI change, userspace register
write, reboot-controller change, new reset address, mainline pin update, or
vendor/default/console-only kernel change is in scope. Board and serial work
belong to the reserved operator after review and matching bundle proof;
host work requires no board reservation.

## Bounded continuation: observe progress when the serial shell cannot answer

The same-image Bash trial produces a fresh userspace prompt but cannot answer
one of eight bounded receipt attempts; ordinary NixOS startup remains unproved.
`docs/evidence/mainline-system-trial/shell-pid1-physical-2026-10-03/README.md`
records this physical boundary and distinct pending operator recovery. The next
increment provides a **separate opt-in mainline kernel diagnostic** to distinguish
cached driver receive progress, actual UART/timer interrupt accounting and
reporter scheduling without requiring foreground shell commands.

Add a runtime-gated, normal-priority finite kernel reporter, at most six samples
across approximately thirty seconds. Validate UART0 binding inside the 8250
core, copy cached counters/state using nonblocking lifecycle/port try-locks, and
obtain actual mapped UART and RISC-V timer IRQ identities. Release every lock
before emitting one bounded fixed public SBI record per sample. Keep ordinary
logging, clock/reset/interrupt settings, shell PID1/async policy and qualified
controls unchanged. This experiment observes software state; it neither reads
UART registers nor proves physical FIFO/baud or Bash delivery.

Source/API/object tests, optional complete kernel/matching bundle, unchanged
existing derivations, host protocol tests and one protected physical comparison
are separate gates (group 5f). No default image, stage 1, production fix, extra
core bring-up, TTY polling/configuration, priority/affinity change or automatic
recovery claim is included. Runtime output and interpretation are UNVERIFIED
until this named operator trial. Ordinary-root/panel/glass task 5b.5 stays open.


## Bounded continuation: distinguish worker entry from its first delayed sample

The finite comparison recorded in
`docs/evidence/mainline-uart-progress/physical-2026-10-03/README.md` reached the
fresh matching kernel arguments and Bash prompt, attempted one receipt, and
captured neither a receipt nor any of six expected reports. DBCN capability
detection was printed. There are no UART/timer counters to interpret. The
first report follows worker scheduling, a five-second sleep, cached snapshot
and firmware output; that observation cannot distinguish those boundaries.

Group 5g adds a separately selected breadcrumb variant of the existing finite
reporter. It attempts only two fixed public direct-SBI records: worker-entry
before its first sleep and first-post-sleep before its first snapshot. Keep
all six existing sample records, delays, cached getter behavior and normal
priority unchanged. Both exact runtime gates are required for breadcrumbs;
new named source/kernel/system/object/trial outputs preserve every existing
package/source/trial identity. The normal card profile and boot selection stay
protected. Typed controller qualification and strict parsing are a separate
implementation task, not an implicit extension of the existing mode.

This is a kernel/Nix/controller observability refinement within the existing
mainline change. No IRQ, TTY, PID1, clock/reset, firmware, console-policy or
priority/affinity change is included. A visible record proves reaching its
firmware call, not that it returned; absence leaves scheduling/output unknown.
Native/source/object/full-artifact checks and one protected physical comparison
remain separate gates. Breadcrumb output, RX delivery, automatic return and
ordinary-root/panel/glass acceptance remain UNVERIFIED; task 5b.5 stays open.


## Bounded continuation: distinguish the second write's return from the third wakeup

The committed [breadcrumb packet](../../../docs/evidence/mainline-uart-progress-breadcrumbs/physical-2026-10-03/README.md)
at revision 278769d0 records both worker points, a matched fresh receipt and
numeric n0/n1, but no n2–n5 during the bounded 180-second capture. Its
[result](../../../docs/evidence/mainline-uart-progress-breadcrumbs/physical-2026-10-03/result.json)
is independently reviewed. The subsequent operator reset passed guarded fresh
protected normal postflight and Home observation; its distinct
[recovery receipt](../../../docs/evidence/mainline-uart-progress-breadcrumbs/physical-2026-10-03/operator-reset-recovery.json)
does not qualify automatic return. A complete n1 line does
not show its firmware call returning, or the worker reaching its third wakeup.
No counter value, IRQ fault or ordinary-root result is inferred from that gap.

Group 5h adds a separately named layered diagnostic variant with two fixed
public records: immediately after the n1 numeric SBI call returns, and after
the n2 sleep/stop check before snapshot. Preserve the six samples, existing
breadcrumbs, sleeps/getters/stop behavior, normal priority and every existing
package/source/config/trial identity. A new exact runtime gate requires both
existing progress/breadcrumb gates. Two single attempts bring the worker's
maximum to ten writes; no fallback, retry or wall-clock firmware guarantee.

This refines kernel/Nix/controller observability in the open mainline change.
No IRQ/TTY/PID1, clock/reset, console, firmware, scheduler policy or production
fix is included. Source/native/exact-object/full-artifact/controller and one
protected physical comparison remain distinct gates. New output and recovery
are UNVERIFIED; ordinary-root/panel/glass task 5b.5 remains open. The plan lands
before source implementation, and only the reserved operator uses the board.


Group5h's matching source/objects/full artifacts and positive controller gates
passed. Its independently reviewed physical capture reached worker-entry/Bash,
but no receipt, numeric samples or new points in180.0975s; the committed
[physical packet](../../../docs/evidence/mainline-uart-progress-post-sample/physical-2026-10-03/README.md)
and deployment receipt preserve that incomplete result. The subsequent NEW
operator reset passed guarded fresh normal postflight and reviewed Home evidence.
No return from entry's output, first sleep completion or later point is proved.
This leaves the ordinary mainline acceptance requirement and task5b.5 open.

## Bounded continuation: memory progress without repeated worker output

The [PostSample capture](../../../docs/evidence/mainline-uart-progress-post-sample/physical-2026-10-03/README.md)
reached worker-entry/Bash but no receipt or later samples/points, unlike the prior
n0/n1 result. Group5i adds a separately selected intervention: preserve six
sleeps/cached snapshots/stop checks, suppress all worker output, record progress
in ordinary memory and let one independent observer attempt a final summary.
[Read source and limits](../../../docs/research/mainline-memory-progress-comparison-2026-10-03.md)
show firmware console locking and unbounded UART polling as possible dependencies,
not a diagnosed cause or proven installed-firmware identity. No new MMIO,
IRQ/TTY/PID1/firmware/console-policy/scheduler change. New comparison remains
UNVERIFIED; ordinary root/panel/glass task5b.5 stays open. Fresh protected normal
recovery is required before another trial. Land this plan before source work.


## Same-image continuation: withhold the candidate shell stimulus

The [Memory physical capture](../../../docs/evidence/mainline-uart-progress-memory/physical-2026-10-03/README.md)
records fresh args/Bash, one attempted stimulus and no receipt/summary in 180.1021s.
Group 5j adds a separately typed controller-only zero-stimulus comparison against
the SAME qualified lznjjfx1 image/dev/source/config/DT and identical volatile
bootargs. No kernel rebuild or runtime firmware/IRQ/TTY/timer change. Strict
summary and protected normal gates remain; receipt becomes NOT_REQUESTED and RX
NOT_TESTED. A difference under withheld input is not its cause or RX acceptance.
Missing summary remains unknown; fresh operator recovery is required first.
Land this bounded plan before implementation; 5b.5 stays open.


## Same-image continuation: test idle/tick-policy dependence

The [zero-input capture](../../../docs/evidence/mainline-uart-progress-memory/no-stimulus-physical-2026-10-04/README.md)
reached Bash but no summary in 180.0995s with zero stimulus. Group 5k adds one
separately typed idle-polling comparison: append only bare volatile `nohlt` to
that same Memory image's qualified bootargs and retain zero candidate input.
[Read source/config/linked setup](../../../docs/research/mainline-memory-idle-polling-comparison-2026-10-04.md)
support this bounded discriminator without a rebuild. No IRQ/MMIO/firmware,
worker/observer, affinity/priority or production power-policy change. A result
can show idle/tick-policy dependence, not its cause. New runtime selection,
summary and recovery remain UNVERIFIED; ordinary task 5b.5 stays open. Fresh
normal recovery and actual host qualification precede one boot. Land this plan
before controller implementation.


## Bounded continuation: independent Linux-console observer output

[Polling](../../../docs/evidence/mainline-uart-progress-memory/poll-idle-physical-2026-10-04/README.md)
received nohlt/Bash but no summary in 180.0929s; subsequent NEW reset restored
protected normal/Home. The [timer/backend audit](../../../docs/research/mainline-memory-printk-channel-comparison-2026-10-04.md)
found no grounded timer-DT switch and observed a registered Linux8250 ttyS0 console.
Group 5l adds a separately gated source/controller variant: retain Memory progress
and observer wait/snapshot, replace its one final explicit DBCN attempt with one
ordinary KERN_INFO Linux-console summary in a distinct K230_UMK1 namespace.
A leading newline in that same call separates the summary from Bash prompt
output; timestamp-prefixed complete-line parsing stays strict.
Baseline zero-input policy remains; no combined nohlt, raw MMIO, force/emergency
printing, fallback, retry, IRQ/firmware/priority change or production fix.
This requires a new matching kernel build and exact artifact/controller proof;
all previous package/source/config/trial identities remain unchanged. Native,
target-object, full build, physical output and recovery are separate. A record
supports observer progress through the changed output path, not cause or API
return. Silence remains unknown; ordinary 5b.5 stays open. Land this plan first.


## Same-image continuation: disable tickless activation

The [MemoryPrintk physical capture](../../../docs/evidence/mainline-uart-progress-memory-printk/physical-2026-10-04/README.md)
reached Bash with exact arguments and a registered Linux console, but no observer
record or automatic normal return in 180.1019 seconds. Group 5m tests one remaining
tick-policy dependency using the same already-built p2 MemoryPrintk image: append
only volatile `nohz=off`, retaining zero candidate input. The
[source/config/Image audit](../../../docs/research/mainline-memory-printk-periodic-tick-comparison-2026-10-04.md)
grounds this option. It disables tickless activation; high-resolution timers and
the RISC-V oneshot/SBI timer path remain. Earlier nohlt already restarts idle
ticks, so its negative result limits this hypothesis without testing the global
nohz activation policy. No kernel/initrd/DT rebuild or firmware/IRQ/MMIO change.
Land typed controller planning first; actual host qualification and NEW protected
normal recovery precede one physical comparison. Runtime policy, observer output
and recovery remain UNVERIFIED; ordinary task 5b.5 stays open.


## Bounded continuation: autonomous PID1 output and one sleep

The [same-image nohz-off capture](../../../docs/evidence/mainline-uart-progress-memory-printk/nohz-off-physical-2026-10-04/README.md)
reached Bash readiness but no observer record in 180.025 seconds. Group 5n
observes userspace directly: the same p2 Image/initrd/DT runs a fixed Bash-PID1
script that checks PID1/UID0, emits a fresh begin record, sleeps once for five
seconds and emits end on success, then attempts an interactive shell. Every
reporter/trace/nohz/nohlt gate is absent; no received command is needed. The
[read source/archive/quoting scout](../../../docs/research/mainline-autonomous-bash-pid1-comparison-2026-10-04.md)
grounds a 503-byte transport, while explicitly leaving native parser execution
unproved. Native exact Hush and selected Linux argv proof are mandatory before
physical use; do not weaken the generic transport policy or offer arbitrary
scripts. No new kernel/initrd/DT build, IRQ/MMIO/firmware change, production fix
or ordinary-root claim. Land this bounded plan first. Actual host qualification
and NEW protected normal recovery precede one 60-second passive comparison.
Missing output remains unknown and ordinary task 5b.5 stays open.


## Bounded continuation: ordinary-init manager logging

The current p2 ordinary comparison reaches mounted sysroot and starts closure
lookup without a usable login. Add one typed logging-only comparison so the
operator can distinguish queued dependencies, main-process spawn/exec failure,
running closure lookup and completion before activation. Use the same artifacts
and protected recovery; no kernel rebuild or new masks/targets. This requires
the physical board for its result. Nested shell/syscall tracing and ordinary
boot acceptance are outside this diagnostic. [Scope and source grounding](../../../docs/research/mainline-initrd-debug-logging-2026-10-05.md).
