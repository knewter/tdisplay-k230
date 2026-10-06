# system/kernel Specification

## Purpose
Define the pinned Linux kernel and document the board-specific patches and
device-tree differences needed to support the T-Display-K230 panel and touch
controller, so kernel updates can preserve working hardware support.

## Requirements

### Requirement: The kernel is pinned, and its divergence from upstream is recorded

The kernel SHALL be built from a pinned revision of the Xuantie tree used by
Canaan's Linux SDK, and every patch this project carries on top SHALL be
recorded with what it does and why it is needed.

*Grounding: `k230_canmv_v3_defconfig` in `kendryte/k230_linux_sdk` builds
`ruyisdk/linux-xuantie-kernel` at `7d4e1f444f461dbe3833bd99a4640e7b6c2cd529`
with the `k230` defconfig.*

The kernel SHALL carry support for this board's panel and touch controller.
Panel support is configuration — a device tree describing the RM69A10 to the
generic Canaan panel support already in the tree. Touch support is a patch,
because the pinned tree predates GT9895 support.

Where this project's device tree diverges from the `k230-canmv-v3` reference,
the divergence SHALL be recorded. The reference describes a different display
— an ST7701 at 480x800 — so the divergence is expected and is the point.

#### Scenario: The kernel derivation is inspected

- **WHEN** someone asks what this project changed about the kernel
- **THEN** the pinned revision, each carried patch, and the device tree divergences from the reference board are all recorded

#### Scenario: A patch is added to the kernel

- **WHEN** a patch is carried
- **THEN** it is recorded with its origin and the reason it is needed, so a later kernel bump can tell whether it is still required

### Requirement: An optional vector system trial retains the normal recovery path

*Physical grounding: `docs/evidence/card-shell/kernel-rvv/board-trial/boot1.json`, `vector-state1.json` and `trial-normal-recovery.json` record one-time trial boot, matching running identity and normal shell/Wi-Fi return with protected hashes unchanged. Earlier failed load reports and recovery are retained in the same directory.*
*Grounding for the approach: the matching kernel/system/image builds and actual boot-artifact inspection are recorded in `docs/evidence/card-shell/kernel-rvv/`; storage first/repeat boot evidence is in `docs/evidence/storage-capacity/`. Host builds do not prove a trial kernel boots.*

The system SHALL provide an explicitly selected CPU-vector trial with matching kernel, external modules, initrd and userspace. Trial preparation and one-time boot SHALL retain the known normal persistent boot selection and protected credential procedure. The operator SHALL verify artifact identity before loading the trial and verify the normal system, shell and Wi-Fi after returning. A failed load SHALL stop trial execution and attempt normal recovery while the bootloader remains available. Recovery requiring an operator reset SHALL be reported rather than claimed as automatic success.

#### Scenario: A person returns from the vector trial
- **WHEN** the operator resets after a one-time trial without selecting a new persistent system
- **THEN** the known normal system boots with its protected boot data intact
- **AND** the shell and Wi-Fi recovery are recorded separately from trial success

#### Scenario: A staged artifact cannot be verified
- **WHEN** an artifact has an unexpected identity, size or loaded-memory checksum
- **THEN** the operator does not execute the trial kernel
- **AND** the failure and observed recovery outcome are retained

### Requirement: Vector execution is gated by actual kernel and context support

*Physical grounding: `docs/evidence/card-shell/kernel-rvv/board-trial/vector-state1.json` records hwprobe value 63 and a two-process PASS with 2,000 checks per process across signals and scheduling. This is representative state proof, not exhaustive ISA coverage.*
*Grounding: `docs/evidence/card-shell/pixman-rvv/kernel-probe.json` records successful hwprobe with value 59 and no standard V bit; `docs/evidence/card-shell/kernel-rvv/context-probe/board-skip.json` records safe SKIP/77. Full-system guest context and deliberate-corruption cases are separate diagnostic proof.*

The optional vector path SHALL require the kernel's runtime capability report and physical vector computation with preserved state across asynchronous signals and process scheduling. A processor name, ISA string, successful cross-build or guest result SHALL NOT substitute for that physical evidence. If capability is absent or the state check fails, rendering SHALL retain scalar fallback and the failed or skipped result SHALL remain visible. The trial SHALL NOT force vector instructions merely to bypass a failed runtime gate.

#### Scenario: The running kernel does not expose usable standard vectors
- **WHEN** the scalar capability query omits standard vector support or returns an error
- **THEN** the diagnostic skips vector execution and rendering retains its fallback
- **AND** no acceleration result is claimed

#### Scenario: The trial advertises usable vectors
- **WHEN** the trial kernel advertises standard vector support
- **THEN** representative vector computation must survive signals and scheduling on the physical board before vector rendering is evaluated

### Requirement: A vector rendering decision includes correctness and matched cost evidence

*Grounding: physical-board comparison in `docs/evidence/card-shell/kernel-rvv/card-cost/README.md`, `run1/result.json` and `comparison.json` record six matched physical runs with unchanged budgets. CPU-cost changes are small and mixed; every workload fails overall acceptance, four upward-throw checks fail, and the decision retains the ordinary image. This is injected-input measurement, not real-finger or optical proof.*
*Partial physical grounding: `docs/evidence/card-shell/pixman-rvv/pixel-trial/board/result.json` records 192 exact byte comparisons, real RVV callback counts and a detected one-byte corruption control. This proves only its declared pixel cases, not card costs.*

The optional userspace renderer trial SHALL compare its declared pixel cases against the scalar reference and measure the same live-card workload with vector dispatch enabled and disabled on the same trial kernel. It SHALL retain frame/update, input-latency, CPU and memory measurements and all existing card interaction budgets. A compiled vector path, isolated instruction test or faster synthetic operation SHALL NOT be presented as a card-shell speedup. The recorded decision SHALL preserve negative results and distinguish an optional experiment from a default image change.

#### Scenario: Vector operations are correct but do not improve the card workload
- **WHEN** the vector pixel cases pass but matched card measurements do not improve the declared costs
- **THEN** the result records that outcome and does not claim an accepted performance improvement
- **AND** the ordinary renderer remains unchanged

#### Scenario: Vector rendering is considered for future default use
- **WHEN** the optional trial passes correctness and shows a measured benefit
- **THEN** the evidence names the workload, repeated measurements and remaining compatibility limits
- **AND** default promotion remains a separate reviewed change

### Requirement: A parallel mainline kernel build exists and does not affect the default system

The project SHALL provide a mainline-Linux kernel, device-tree, and
boot-files build (`.#kernelMainline`, `.#deviceTreeMainline`,
`.#kernelMainlineBootFiles`) pinned to the newest mainline revision carrying
basic Canaan K230 support, built entirely separately from the pinned vendor
Xuantie kernel `.#kernel` uses. No existing package, `nixosConfigurations`
output, or `.#sdImage` SHALL depend on or be changed by this build existing.

*Grounding: `nix/kernel-mainline-src.nix` pins `torvalds/linux` at the
dereferenced `v7.3-rc5` commit — the newest tag with
`arch/riscv/boot/dts/canaan/k230.dtsi` present, confirmed absent at `v7.2`
by direct tag diff. `nix/kernel-mainline.nix` and
`nix/device-tree-mainline.nix` share no code path with `nix/kernel.nix` or
`nix/device-tree.nix`; `flake.nix`'s new `kernelMainline`/
`deviceTreeMainline`/`kernelMainlineBootFiles` outputs are additive only.*

#### Scenario: Someone builds the mainline kernel

- **WHEN** someone runs `nix build .#kernelMainline`
- **THEN** it exits 0 and produces a riscv64 kernel Image, independent of
  whether `.#kernel` has ever been built

#### Scenario: Someone builds the default system

- **WHEN** someone builds `.#nixosConfigurations.k230.config.system.build.toplevel`
  or `.#sdImage`
- **THEN** the result is byte-identical to what it would be if
  `nix/kernel-mainline.nix`, `nix/kernel-mainline-src.nix`,
  `nix/device-tree-mainline.nix`, and this change's other new files did not
  exist

### Requirement: A parallel full system variant boots the mainline kernel without changing the default system

The project SHALL provide a full NixOS system variant
(`nixosConfigurations.k230-mainline-console`) that substitutes the
mainline kernel for the vendor kernel via the same `k230Kernel` specialArg
substitution mechanism the existing `k230-rvv-trial` variant already uses,
built from the shell-off `k230-console` base rather than the graphical
`k230-coherent-shell` base, and SHALL exclude any out-of-tree kernel module
that is not expected to compile against the mainline pin. No existing
`nixosConfigurations` output SHALL be changed by this variant existing.

*Grounding: `flake.nix`'s `k230-mainline-console` extends `k230-console`
with `specialArgs.k230Kernel = self.k230MainlineKernel` and force-clears
`boot.extraModulePackages`/`boot.kernelModules` (the out-of-tree RTL8189FTV
module `nix/hardware.nix` builds against `config.boot.kernelPackages.kernel`
dynamically, with no reason to expect it compiles against a v7.3-rc5 API
seven major versions newer than its 6.6-era vendor origin, and no SDIO DT
node enabled for it to bind to regardless). Proven:
`nix build .#toplevel-mainline-console` exits 0, producing
`/nix/store/d488a1cibw8r7ip7hbbb9j52hy0kzb0h-nixos-system-nixos-26.11.20260919.20b1ddd`.
Deviates from the coordinator's suggested "-shell-" name for the reason
above; flagged rather than silently decided.*

#### Scenario: Someone builds the mainline system variant

- **WHEN** someone runs `nix build .#toplevel-mainline-console`
- **THEN** it exits 0 and produces a NixOS system closure built against
  `kernelMainline`, independent of whether any other `nixosConfigurations`
  output has ever been built

### Requirement: The mainline build's hardware ceiling is recorded, not assumed

The project SHALL record, per hardware function, whether mainline Linux at
the pinned revision can drive it, citing direct file-existence or
device-tree-content checks rather than changelog summaries. Hardware
functions with no mainline driver SHALL be recorded as blocked rather than
silently omitted, and any of this project's own vendor-kernel patches that
cannot be forward-ported to mainline SHALL be recorded individually with the
reason, not summarized as a single negative finding.

*Grounding: `docs/research/mainline-kernel-inventory.md`'s Inventory table
(each row cites `gh api repos/torvalds/linux/contents/<path>` returning 200
or 404) and its per-patch disposition list (all eleven vendor-kernel patches
checked individually; ten target files absent upstream, one already fixed
upstream independently, none require porting as a patch today).*

#### Scenario: Someone asks whether mainline can drive the display

- **WHEN** someone reads `docs/research/mainline-kernel-inventory.md`'s
  panel row
- **THEN** it states that the pinned upstream tree had no DSI/VO/Canaan
  DRM drivers at the time of the inventory, cites the exact file-existence
  checks, and points to the separately tracked `kernelMainlineDrm`
  continuation without claiming that continuation is complete

#### Scenario: A vendor-kernel patch is checked against mainline

- **WHEN** someone asks whether a specific patch in `nix/kernel.nix` applies
  to the mainline build
- **THEN** the inventory names that exact patch, the file it targets, and
  whether that file exists upstream today

### Requirement: Forward-ported drivers are grounded in the vendor tree and checked against the pinned mainline API

Where this project forward-ports a vendor-tree driver onto the mainline
pin so a boot-critical function (GPIO, SD/MMC, USB) is available, the
ported file or hunk SHALL be traceable to its exact vendor-tree origin by
path, and any API difference between the vendor tree's kernel version and
the pinned mainline revision that required a code change (not just a
Kconfig/Makefile wiring change) SHALL be recorded with what changed and
how it was confirmed, rather than silently patched around.

*Grounding: `nix/patches/mainline/gpio-k230.c` and
`nix/patches/mainline/sdhci-of-kendryte.c` are forward-ported from
`ruyisdk/linux-xuantie-kernel` @ `7d4e1f444f461dbe3833bd99a4640e7b6c2cd529`;
`nix/kernel-mainline.nix`'s postPatch carries the `drivers/usb/dwc2/
{params.c,core.h,core.c}` hunks from the same tree. Two real API
migrations were found and fixed this way, each only after a failed build
named the exact missing symbol: `struct gpio_chip`'s `.read_reg`/
`.write_reg`/`.bgpio_lock` and `bgpio_init()` were replaced upstream by
`struct gpio_generic_chip`/`gpio_generic_chip_init()`
(`include/linux/gpio/generic.h`), confirmed against mainline's own
already-migrated `gpio-dwapb.c`; `sdhci_pltfm_free()` was removed upstream
entirely, confirmed against mainline's own `sdhci-of-dwcmshc.c`, whose
probe error paths and `.remove` call no equivalent function.*

#### Scenario: A forward-ported driver fails to compile against the pinned mainline API

- **WHEN** `nix build .#kernelMainline` fails with an unknown-symbol or
  missing-member compiler error in a forward-ported file
- **THEN** the fix is recorded against the exact API change found, citing a
  mainline reference file that already uses the new API, not a guess

### Requirement: A mainline hardware boot is a named, unclaimed evidence gate

Reaching a mainline-booted serial console, rootfs, or any further hardware
milestone on the physical board SHALL be treated as hardware evidence, never
inferred from a successful cross-build. A change that only cross-builds the
mainline kernel/device-tree SHALL say so explicitly and SHALL NOT claim any
hardware milestone until a board console transcript exists.

*Grounding: this change's own `tasks.md` "Remaining evidence gate" section
names the exact operator command
(`flock /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0
--wait=10`) and the manual U-Boot `ext4load` steps it depends on, without
performing them.*

#### Scenario: Someone asks if the mainline kernel boots on the board

- **WHEN** someone asks whether `.#kernelMainline` has booted on the T-Display-K230
- **THEN** the answer cites a committed board console transcript under
  `docs/evidence/`, or states plainly that none exists yet

### Requirement: A mainline display port remains isolated and evidence-bounded

The project MAY provide an opt-in mainline DRM candidate, but it SHALL
remain a separate derivation from the console-only `kernelMainline` and
SHALL NOT change the vendor kernel, default device tree, system
configuration, or image outputs. Source/API checks, complete kernel builds,
DTB checks, and physical display/touch observations SHALL be recorded as
distinct evidence; one class SHALL NOT be described as proof of another.

*Grounding: `nix/kernel-mainline-drm.nix` builds the copied Canaan DRM/DSI,
RM69A10 panel, and LT9611 code as a separate override of
`kernelMainline`. `nix/device-tree-mainline-drm.nix` and the separate
`kernelMainlineDrmBootFiles` output pair the candidate DTB/Image without
changing default outputs. `docs/evidence/mainline-display-api-compile.md`,
`docs/evidence/mainline-display-dtb.md`, and
`docs/evidence/mainline-display-nix-build.md` record the prepared-header
external-module, host DTS, and complete Nix kernel/DTB/boot-files checks,
with their limits and the absent hardware results.
`docs/evidence/mainline-display-boot-preparation.md` records the matching
opt-in trial system/initrd/bootargs and closure inventory, and the recoverable root staging/U-Boot
procedure. Later committed October 1/2 physical trials at
`docs/evidence/mainline-display/physical-2026-10-01/README.md` establish
partial boot/probe/photographed boot text and distinct normal recovery, but
no usable mainline root or deliberate touch. The DRM driver sources in the pinned
upstream source output are absent; this candidate forward-ports them from
the vendor-derived implementation. The initial candidate omitted display power-domain wiring because the
pinned source has no provider; the DRM-only local provider continuation
remains gated by separate source/build and physical runtime evidence
(`docs/evidence/mainline-display-power-domain.md`).*

#### Scenario: Someone builds the console-only mainline kernel

- **WHEN** someone runs `nix build .#kernelMainline`
- **THEN** the optional DRM candidate does not modify that kernel or its
  existing console boot-files/DTB outputs

#### Scenario: Someone asks whether the DRM candidate drives the panel

- **WHEN** the complete derivation builds, prepared-header object check, and
  DTB round-trip are available, but no physical observation exists
- **THEN** the answer reports those host results and leaves board probe,
  display power, panel illumination, and touch behavior unverified


### Requirement: The optional mainline trial owns an explicit restart recovery boundary

The optional DRM mainline kernel SHALL provide a documented restart mechanism
traceable to the pinned vendor source, isolated from vendor/default and
console-only mainline outputs. Source/API object proof, complete candidate
kernel build, matching trial-bundle proof and physical restart/recovery SHALL
be recorded separately. Physical automatic restart remains UNVERIFIED until
a committed console transcript shows a kernel restart request reaching stage
1 and the protected normal system returning with a fresh boot identity.

*Grounding: the read vendor `drivers/reset/reset-k230.c` at
`7d4e1f444f461dbe3833bd99a4640e7b6c2cd529` registers a priority-128
restart handler and writes bits 0/16 at `0x91102060`. The source audit at
`docs/evidence/mainline-display/physical-2026-10-01/mainline-restart-source-audit-2026-10-02.md`
records the mainline peripheral-only reset driver, absent advertised SBI
SRST, the systemd refusal and distinct operator recovery. Group 5d owns the
kernel/Nix continuation and its separate evidence gates.
`docs/evidence/mainline-restart/README.md` records the initial GCC failure,
corrected source/object/full-kernel/matching-bundle proof and unchanged
base-relative default outputs; its host checks do not provide physical restart proof.*

*Physical grounding: `docs/evidence/mainline-restart/physical-clock-comparison-2026-10-02/README.md`
records a real candidate kernel restart → SPL → protected normal return,
fresh boot ID, matching identities, active shell services and eight unchanged
hashes with temporary `clk_ignore_unused`. This proves that diagnostic
selection only; the baseline still stalls and restart without the flag
requires a separate clock-consumer fix and physical proof.*

*Further physical grounding: `docs/evidence/mainline-sd1-clocks/physical-no-flag-2026-10-03/README.md`
records the targeted five-clock candidate with ordinary clock cleanup, no
`clk_ignore_unused`, real kernel restart → SPL → protected normal boot,
fresh boot identity, three active shell services and eight unchanged hashes.
The full initrd-shell result and artifact identities are committed; ordinary
root activation and deliberate touch remain separately unverified.*

#### Scenario: The operator requests restart from the mainline diagnostic trial

- **WHEN** a real kernel restart request is issued from the reviewed optional
  candidate after the userspace prerequisites pass
- **THEN** the console shows stage 1 restarting and the protected normal
  system returning with a fresh boot identity and verified protected hashes

#### Scenario: A reboot command returns a userspace refusal

- **WHEN** systemd refuses the reboot command or the operator power-cycles
  the board to recover
- **THEN** that result is recorded with its limits and does not satisfy
  the optional mainline kernel's automatic restart evidence gate

#### Scenario: Only the host restart checks have passed

- **WHEN** the changed object, complete kernel and matching trial bundle build
- **THEN** their source/artifact identities are recorded and physical restart
  remains UNVERIFIED; usable-root, panel and touch requirements remain open

### Requirement: Optional mainline progress records distinguish receipt from execution

The project MAY provide a separately named runtime-opt-in kernel diagnostic
for the observed userspace-prompt/no-receipt boundary. It SHALL record bounded
cached UART/IRQ/time progress independently of foreground shell input, with
explicit unavailable/busy/unknown states and no UART register/settings changes.
Observer source/API/object, matching artifact and physical results SHALL be
separate. Existing default and diagnostic outputs SHALL remain unchanged;
finite reporter output SHALL NOT establish ordinary root, Bash receipt,
physical timer health, automatic recovery or a production fix.

<!-- UNVERIFIED: physical counter values, receipt and autonomous progress remain unproved. -->
*Grounding: `docs/evidence/mainline-system-trial/shell-pid1-physical-2026-10-03/README.md`
observes fresh Linux/init entry/Bash prompt and missing bounded receipt.
Its `uart-source-equality.json` records narrow host source/DT comparison only.
Read pinned 8250 RX accounting, RISC-V timer IRQ mapping, IRQ descriptor
accounting and n_tty lock/flush paths as cited in group 5f's design.*

#### Scenario: The serial operator sees a shell prompt but cannot get a reply

- **WHEN** the reviewed optional matching diagnostic is reserved for a physical
  trial and its fresh prompt receives one bounded receipt stimulus
- **THEN** finite independently captured records distinguish driver RX counts,
  actual mapped IRQ accounting and reporter/time progress with their limits
- **AND** missing receipt/records stop further input and keep root/recovery open

#### Scenario: Someone interprets a progress record

- **WHEN** reporter sequence, RX or timer IRQ counters increase
- **THEN** the report names scheduling, processed RX/break counts or
  kernel-accounted timer interrupts respectively, without inferring a physical
  FIFO read for every RX increment, Bash delivery or a causal fix

#### Scenario: Only diagnostic host checks have passed

- **WHEN** optional source/object/kernel/bundle/protocol checks pass
- **THEN** physical output/receipt/return remain UNVERIFIED and task 5b.5 stays open


### Requirement: Optional progress breadcrumbs keep worker and wakeup evidence distinct

The project MAY provide a separately selected finite reporter variant for the
observed zero-report boundary. It SHALL preserve every existing package/source/
trial identity and attempt only fixed worker-entry and first-post-sleep public
SBI records in its normal-priority worker, with ordinary aligned page-contained
storage and no IRQ/TTY/PID1 instrumentation. Both exact runtime opt-ins and
actual DBCN availability SHALL gate breadcrumbs; absent/invalid breadcrumb
selection SHALL retain the original six-sample behavior. The six numeric
sample formats, sleeps, getter semantics and stop checks SHALL remain unchanged.

The explicit controller selection SHALL keep exact candidate/argument and
protected normal qualification, accept only bounded complete fresh fixed
records, and distinguish breadcrumb presence, numeric samples and receipt.
Missing/malformed output SHALL remain unknown and SHALL NOT cause another
stimulus or candidate reboot. Neither breadcrumb presence nor absence SHALL
be described as a causal diagnosis, ordinary-root acceptance or recovery.

<!-- UNVERIFIED: new variant/source/object/controller/full-build and physical breadcrumb proof are planned. -->
*Grounding: `docs/evidence/mainline-uart-progress/physical-2026-10-03/README.md`
and `result.json` record one stimulus, no receipt, zero reports and DBCN
detection. The realized source `4av3w0…` reporter's worker at27–69 first sleeps,
then snapshots/formats/writes, as detailed in group5g's design. Existing
`docs/evidence/mainline-uart-progress/exact-full-host-2026-10-03.md` is host proof
of the original reporter, not this new physical comparison.*

#### Scenario: The operator captures an entry record without a delayed sample

- **WHEN** an exactly qualified fresh trial emits only worker-entry
- **THEN** the report states that the worker reached that output call
- **AND** it leaves firmware return, sleep/wakeup, counters and receipt unknown

#### Scenario: The first post-sleep record is observed

- **WHEN** the qualified first-post-sleep record is complete
- **THEN** the report states that the first sleep and existing stop checks passed
  and the earlier entry call returned
- **AND** it does not claim complete earlier output, physical timer health,
  successful snapshot or Bash receipt

#### Scenario: Output is missing or malformed

- **WHEN** fixed records are absent, duplicated, stale, reordered, truncated or
  interleaved with other console text
- **THEN** the controller preserves private raw evidence and incomplete/unknown
  status without repairing text, another stimulus or a candidate reboot
- **AND** root, deliberate touch and independent recovery gates remain open


### Requirement: Optional post-sample breadcrumbs separate return from wakeup evidence

The project MAY provide a separately selected reporter variant for the observed
n1/no-n2 boundary. It SHALL preserve all existing package/source/config/trial
identities, samples, sleeps, cached getters, stop checks and normal priority.
It SHALL attempt only two additional fixed public SBI records: after the n1
numeric call returns, and after the third sleep/stop check before snapshot.
Ordinary aligned page-contained storage, the new exact opt-in plus both existing
opt-ins, CONFIG_RISCV_SBI and DBCN availability SHALL gate the records. At most
ten one-call attempts SHALL occur; absent/invalid new selection SHALL retain
current behavior without a retry, fallback or IRQ/TTY/PID1 instrumentation.

The separately typed controller SHALL preserve exact candidate/argument and
protected normal qualification, one fresh stimulus and private bounded capture.
It SHALL accept only exact bounded complete fresh records and keep new-point,
old-breadcrumb, numeric-sample, receipt and recovery facts distinct. Missing or
malformed output SHALL remain unknown without another stimulus or candidate
reboot, and SHALL NOT establish a causal fix, root/touch or automatic return.

<!-- UNVERIFIED: after-n1-write/third-post-sleep output, receipt, automatic recovery and ordinary root/glass remain unproven. Source/exact/full/controller and incomplete physical capture are committed. -->
*Grounding: committed [physical packet](../../../../docs/evidence/mainline-uart-progress-breadcrumbs/physical-2026-10-03/README.md)
and [result](../../../../docs/evidence/mainline-uart-progress-breadcrumbs/physical-2026-10-03/result.json)
at revision 278769d0 record both Breadcrumbs points, a matched receipt and
n0/n1 but no n2–n5 in 180 seconds. The subsequent operator reset passed guarded
fresh protected normal postflight and Home observation; automatic return
remains unverified. The read immutable k5a5zrhq… worker at 67–74 sleeps/checks before snapshot
and at 98 calls SBI, as detailed in group 5h's design. This is a source-supported
next boundary, not committed proof of the new diagnostic or a fault.*

#### Scenario: The point following the second numeric write appears

- **WHEN** a qualified fresh trial emits complete after-n1-write
- **THEN** the report states that the earlier n1 firmware call returned
- **AND** it does not claim its full count, the new call's return or third wakeup

#### Scenario: The third post-sleep point appears

- **WHEN** the exact third-post-sleep record is complete
- **THEN** the report states that the earlier point's call returned and the
  third sleep/stop checks passed
- **AND** it leaves snapshot, n2 output, RX/Bash delivery and recovery separate

#### Scenario: A point is missing or malformed

- **WHEN** the new record is missing, stale, echoed, duplicated, reordered,
  truncated or interleaved with other text
- **THEN** private raw evidence and partial facts are retained as unknown
- **AND** there is no further stimulus/reboot or inferred ordinary-root/touch,
  firmware-return or automatic-recovery result


*Subsequent actual [PostSample packet](../../../../docs/evidence/mainline-uart-progress-post-sample/physical-2026-10-03/README.md)
records matched args/Bash/worker-entry only, one stimulus and no receipt/samples/
new points in180.0975s. It does not prove reaching either new point or entry-call
return; subsequent NEW operator reset passed guarded fresh normal postflight
and Home observation. Host and incomplete capture completion
do not satisfy the scenarios above or ordinary-root task5b.5.*

### Requirement: Optional memory-progress comparison isolates repeated worker output

The project MAY provide a separately selected explicit memory-progress reporter.
It SHALL retain existing outputs/identities and, only under its exact opt-in,
preserve six sleeps/cached snapshots/stop checks while suppressing every worker
output call and publishing finite consistent ordinary-memory progress. A separate
normal-priority observer SHALL use one finite kernel wait and at most one aligned
bounded-size DBCN summary attempt. It SHALL NOT add MMIO, IRQ/TTY/PID1 output,
retry/fallback, firmware/console-policy or scheduler changes. Gate absence or
invalid values SHALL retain inherited behavior without observer creation.

The typed minimal controller SHALL qualify exact host artifacts/source/config,
fresh received arguments/Bash readiness and protected normal state. It SHALL
send at most one receipt then bounded passive capture, with no further input or
candidate reboot. Summary, receipt and recovery SHALL remain independent facts;
missing output SHALL NOT identify a cause or prove ordinary root/glass.

<!-- UNVERIFIED: memory comparison source/artifacts/controller/physical results are planned. -->
*Grounding: [PostSample capture](../../../../docs/evidence/mainline-uart-progress-post-sample/physical-2026-10-03/README.md)
and [read-source audit](../../../../docs/research/mainline-memory-progress-comparison-2026-10-03.md)
record variable reporter progress and firmware output dependencies, not causation.*

#### Scenario: A consistent completed summary arrives

- **WHEN** one exact fresh summary records all six worker snapshots completed
- **THEN** it establishes recorded progress before the observer's final output call
- **AND** it does not establish that call's return, a root cause or ordinary boot

#### Scenario: Summary or receipt is absent

- **WHEN** bounded capture has no complete qualified summary or receipt
- **THEN** preserve each missing fact as unknown, including observer/output limits
- **AND** send no further candidate input or reboot and require separate recovery


### Requirement: Optional same-image zero-stimulus comparison keeps receive untested

The controller MAY provide an explicit Memory-only no-stimulus comparison. It
SHALL require minimal/same-image/progress/Memory selectors, preserve exact
candidate/source/config/archive/load guards and identical volatile bootargs, and
reject conflicts before UART access. After candidate boot it SHALL send zero
candidate bytes on success/error/timeout/finally paths and retain bounded passive
capture and strict fresh summary parsing. It SHALL record receipt NOT_REQUESTED,
stimulus_attempts=0 and RX NOT_TESTED rather than infer receive or ordinary-root
acceptance. Default one-stimulus behavior SHALL remain unchanged.

Only the existing ordered fresh normal-recovery qualification SHALL permit
protected normal postflight writes; recovery remains independent of summary
completeness. Missing output SHALL stay unknown and SHALL NOT establish input
causation, an IRQ/timer/firmware fault or ordinary mainline acceptance.

<!-- UNVERIFIED: typed zero-stimulus comparison implementation/host/physical proof are planned. -->
*Grounding: [Memory physical packet](../../../../docs/evidence/mainline-uart-progress-memory/physical-2026-10-03/README.md)
records one input attempt with no summary/receipt; withholding that dependency
is a distinct controller intervention using existing immutable artifacts.*

#### Scenario: A completed summary arrives without a stimulus

- **WHEN** an exact qualified fresh summary records six worker snapshots complete
- **THEN** report that pre-output memory progress with zero candidate stimulus
- **AND** preserve RX NOT_TESTED and independent recovery/ordinary-root limits

#### Scenario: Capture fails or no summary arrives

- **WHEN** passive capture times out or records malformed/missing output
- **THEN** preserve unknown facts and send no additional candidate bytes
- **AND** require independently qualified normal recovery or operator reset


### Requirement: Optional polling comparison changes only qualified idle policy

The controller MAY offer a typed Memory polling-idle comparison. It SHALL
require minimal/same-image/progress/Memory/no-stimulus selectors and reject
conflicts before UART access. It SHALL qualify the same realized source/config/
Image/archive/manifest and append exactly one bare volatile `nohlt` after
checking the selected built-in polling setup. It SHALL reject hlt, duplicates,
value variants and arbitrary bootarg changes; defaults SHALL remain unchanged.

After boot it SHALL send zero candidate bytes and retain bounded passive capture,
strict fresh args/summary parsing, receipt NOT_REQUESTED, zero stimulus attempts
and RX NOT_TESTED. Protected normal recovery SHALL remain independently gated.
A difference SHALL be described only as idle/tick-policy dependence, without
inferring WFI/IRQ/timer/firmware cause, ordinary-root acceptance or a production
power policy. Missing output SHALL remain unknown.

<!-- UNVERIFIED: typed polling controller and physical idle-policy comparison are planned. -->
*Grounding: [zero-input physical result](../../../../docs/evidence/mainline-uart-progress-memory/no-stimulus-physical-2026-10-04/README.md)
and [read source/config/linked setup](../../../../docs/research/mainline-memory-idle-polling-comparison-2026-10-04.md).
The already-built setup is host evidence; runtime polling and usable boot are unverified.*

#### Scenario: Polling produces a valid completed summary

- **WHEN** exact received arguments include the sole bare nohlt intervention
- **AND** a strict fresh summary reports six completed snapshots
- **THEN** record that progress with zero input and idle/tick-policy limits
- **AND** preserve separate RX, normal recovery and ordinary boot acceptance

#### Scenario: Polling capture is incomplete

- **WHEN** output is absent, malformed or capture fails
- **THEN** preserve unknown progress and send no additional candidate bytes
- **AND** require independent protected recovery or operator reset


### Requirement: Separate observer output through the registered Linux console

The diagnostic MAY offer a separately built MemoryPrintk variant with an exact
gate requiring existing Memory/progress gates. It SHALL retain six worker sleeps/
cached snapshots/atomic publication and one observer completion wait/acquire,
suppress worker output, and replace its one final explicit DBCN attempt with one
ordinary KERN_INFO fixed K230_UMK1 summary. The same call SHALL begin with a
newline to separate an existing shell prompt from the timestamped summary line;
the parser SHALL not strip prompts to recover malformed records.
It SHALL not force console ownership,
use emergency/raw-MMIO/fallback/retry output or change IRQ/firmware/priority policy.
Every prior source/config/package/trial identity SHALL remain unchanged.

The typed controller SHALL require minimal/same-image/progress/Memory/no-stimulus
and reject combined idle/point/trace selectors before UART. It SHALL qualify the
new actual source/config/Image/format/setup and exact DT/archive/load guards,
receive exact arguments and fresh Linux8250 ttyS0 registration/console markers.
It SHALL parse only the observed timestamp-prefixed fixed new namespace and
bounded coherent fields, rejecting old/wrong-channel/stale/malformed/duplicate/
truncated records. It SHALL keep zero input, NOT_REQUESTED/RX NOT_TESTED, bounded
capture and independent protected normal recovery.

A record SHALL establish only observer progress through the changed output
channel, not output-call return, DBCN causation, ordinary-root or glass acceptance.
Missing output SHALL remain unknown. Native, target object, full artifact,
controller qualification, physical observation and recovery SHALL stay separate.

<!-- UNVERIFIED: Linux-console variant/source/build/controller/physical proof are planned. -->
*Grounding: [polling result and recovery](../../../../docs/evidence/mainline-uart-progress-memory/poll-idle-physical-2026-10-04/README.md)
and [actual timer/backend/source audit](../../../../docs/research/mainline-memory-printk-channel-comparison-2026-10-04.md).
The registered backend is observed; future UMK output and useful mainline boot are unverified.*

#### Scenario: A fresh Linux-console summary is observed

- **WHEN** exact new gate/args and fresh Linux ttyS0 backend markers are observed
- **AND** one timestamp-prefixed K230_UMK1 summary satisfies bounded state rules
- **THEN** preserve recorded worker/observer progress with zero input
- **AND** retain separate output-return, recovery and ordinary-boot limits

#### Scenario: No qualified Linux-console summary arrives

- **WHEN** capture is incomplete or output fails strict qualification
- **THEN** preserve unknown scheduling/timeout/output facts with no further input
- **AND** require independent protected recovery or operator reset


### Requirement: Optional same-image comparison disables tickless activation only

The controller MAY offer a typed MemoryPrintk nohz-off comparison. It SHALL
require minimal/same-image/progress/Memory/no-stimulus/MemoryPrintk selectors
and reject type/mode/competing selector conflicts before UART access. It SHALL
qualify the same actual source/config/Image/archive/manifest/DT/load identities,
NO_HZ_COMMON/NO_HZ_FULL/HIGH_RES_TIMERS/HZ=250/RISCV_TIMER/RISCV_SBI support
and unique linked nohz setup. It SHALL append exactly one trailing `nohz=off`
to the qualified baseline, reject original/alternate/bare/empty/duplicate nohz
forms and arbitrary additions, and preserve all existing default transports.

The diagnostic SHALL keep its source/worker/observer/output gate and fresh exact
arguments/backend/strict UMK parsing. It SHALL send zero candidate bytes through
bounded capture/error/finally, record NOT_REQUESTED and RX NOT_TESTED and keep
protected normal recovery independently gated. A valid record SHALL support
progress under changed tickless policy only, without inferring hardware periodic
interrupts, a timer/IRQ/firmware cause, printk return or ordinary boot acceptance.
Missing output SHALL remain unknown. Runtime policy observation SHALL remain
distinct from compiled parser support and received-token evidence.

<!-- UNVERIFIED: typed nohz-off controller, actual host preparation and new physical comparison are planned. -->
*Grounding: [MemoryPrintk capture](../../../../docs/evidence/mainline-uart-progress-memory-printk/physical-2026-10-04/README.md)
and [selected config/Image/source audit](../../../../docs/research/mainline-memory-printk-periodic-tick-comparison-2026-10-04.md).
The compiled option is grounded; new output and usable mainline boot are unverified.*

#### Scenario: Tickless-off comparison yields a qualified summary

- **WHEN** fresh exact arguments include the sole nohz=off intervention
- **AND** one strict fresh UMK record satisfies the existing bounded state rules
- **THEN** record progress under changed tickless policy with zero input
- **AND** preserve separate output-return, RX, recovery and ordinary boot limits

#### Scenario: Tickless-off comparison remains incomplete

- **WHEN** output is absent, malformed or capture fails
- **THEN** preserve unknown facts without sending candidate bytes
- **AND** require independent protected recovery or a new operator reset


### Requirement: Fixed autonomous PID1 comparison remains constrained and passive

The controller MAY offer a separately typed autonomous Bash-PID1 comparison
using the same actual Image/initrd/DT. It SHALL require minimal/same-image-shell
selectors and reject all diagnostic progress/timer/trace/shutdown conflicts
before UART. It SHALL reconstruct only the reviewed fixed script and fresh
32-hex nonce, remove reporter gates, preserve qualified original init/rdinit
and boot controls and enforce the unchanged literal transport bound. It SHALL
not expose arbitrary scripts or weaken existing transport/default policies.

Before physical use it SHALL establish native exact Hush lexer/variable/quote/
command execution and selected Linux argv handling, actual artifact/archive
sh/sleep/Bash builtin proof and exact printed bootargs. Source models alone
SHALL NOT satisfy native execution. Fresh candidate phase/args/backend/bin-sh
entry SHALL qualify only complete exact-nonce begin/end records; echoed scripts
and commandline text SHALL NOT count. Malformed/stale/duplicate/reversed/
truncated records SHALL retain unknown facts without repair.

The script SHALL check PID1/UID0, attempt begin, one five-second sleep and end
after success, then attempt an interactive exec independently of that chain.
It SHALL deliberately issue no exit/reboot. The controller SHALL keep a bounded
60-second zero-input capture on all paths, RX NOT_TESTED and independent
protected normal recovery. Record presence SHALL NOT authorize candidate input,
prove that record's own output-call return, a full runtime identity guard, a timer/IRQ cause or
ordinary boot/touch acceptance. Missing output SHALL remain unknown.

<!-- UNVERIFIED: typed autonomous PID1 native parser/controller/actual host/physical proof are planned. -->
*Grounding: [nohz-off capture](../../../../docs/evidence/mainline-uart-progress-memory-printk/nohz-off-physical-2026-10-04/README.md)
and [read kernel/Hush/archive scout](../../../../docs/research/mainline-autonomous-bash-pid1-comparison-2026-10-04.md).
Native parser execution and autonomous board records remain unverified.*

#### Scenario: Autonomous PID1 produces begin and end

- **WHEN** qualified exact arguments and fresh complete nonce records occur in order
- **THEN** record limited PID1/UID0 output and successful earlier printf/sleep
- **AND** preserve distinct prompt/output-return, RX, recovery and boot limits

#### Scenario: Autonomous PID1 evidence is incomplete

- **WHEN** a record is absent or fails strict qualification
- **THEN** keep unknown facts and send no candidate bytes
- **AND** require independent protected recovery or a NEW operator reset


### Requirement: Fixed ordinary-init manager logging comparison

The system trial controller SHALL offer typed begin-only `--initrd-debug-logging`
requiring synchronous-initramfs and marker-free ordinary init. It SHALL append
only `rd.systemd.log_level=debug rd.systemd.log_target=console`, reject inherited
conflicting logging keys including underscore/hyphen aliases and invalid
types/combinations before UART, retain unchanged defaults and transport bound,
and preserve the selected policy through guarded continuation.

It SHALL retain exact artifact/load/CRC/printed/live-argument and normal identity
guards, a 180-second passive readiness bound and complete private logging past
rolling-buffer capacity. Unknown readiness or I/O SHALL send no candidate input.
Manager job/ExecStart state SHALL NOT be reported as nested command or syscall
tracing, ordinary-root acceptance or protected recovery.

<!-- UNVERIFIED: ordinary mainline root/panel/glass acceptance remains open; bounded controller/host/physical logging comparison is recorded below. -->
*Grounding: [current ordinary physical boundary](../../../../docs/evidence/mainline-system-trial/current-p2-ordinary-physical-2026-10-05/README.md)
and [selected archive/pinned systemd source](../../../../docs/research/mainline-initrd-debug-logging-2026-10-05.md).
[Controller and actual host qualification](../../../../docs/evidence/mainline-initrd-debug-logging/host/README.md) and [bounded physical result plus NEW recovery](../../../../docs/evidence/mainline-initrd-debug-logging/physical-2026-10-05/README.md) are recorded. No systemd startup/login was observed; ordinary boot acceptance remains unverified.*

#### Scenario: Qualified logging comparison reaches an observed unit boundary

- **WHEN** fresh qualified candidate output names manager jobs or ExecStart state
- **THEN** record only the observed queued/spawned/running/completed unit facts
- **AND** retain separate login, identity, blocked-call and recovery limits

#### Scenario: Verbose comparison does not reach qualified readiness

- **WHEN** login or I/O completion is unknown within the fixed bound
- **THEN** preserve the complete private log without candidate input or fallback
- **AND** require independent protected recovery or a NEW operator reset


### Requirement: Fixed info-level ordinary-init console comparison

The system trial controller SHALL offer typed begin-only `--initrd-info-logging`,
requiring synchronous initramfs and marker-free ordinary init, excluding debug
logging, and selecting only `rd.systemd.log_level=info rd.systemd.log_target=console`.
It SHALL preserve old/default/debug behavior, typed resumed selection, pre-UART
alias/conflict/type rejection, the transport bound and all immutable artifact,
normal identity, load/CRC and exact printed/live argument guards.

The comparison SHALL keep a 180-second passive readiness bound, complete private
logging and unknown-no-input behavior. Changed observed progress SHALL NOT be
reported as a blocked output-call diagnosis, ordinary boot acceptance or recovery.

<!-- UNVERIFIED: ordinary mainline acceptance remains open; bounded controller/host/physical comparison is recorded below. -->
*Grounding: [debug/console physical result](../../../../docs/evidence/mainline-initrd-debug-logging/physical-2026-10-05/README.md)
and [bounded child/source analysis](../../../../docs/research/mainline-initrd-info-console-comparison-2026-10-05.md). [Actual host qualification](../../../../docs/evidence/mainline-initrd-info-logging/host/README.md) and [physical capture](../../../../docs/evidence/mainline-initrd-info-logging/physical-2026-10-05/README.md) passed their bounded review; no systemd startup/login was observed.*

#### Scenario: Lower verbosity changes observed progress

- **WHEN** qualified same-artifact info/console output reaches new messages
- **THEN** record those observations and the sole changed value
- **AND** retain independent runtime identity, cause and recovery limits

#### Scenario: Info comparison remains silent

- **WHEN** qualified login or I/O completion remains unknown
- **THEN** preserve private facts without candidate input or fallback
- **AND** require independent protected recovery or a NEW operator reset


### Requirement: Fixed info-level ordinary-init kmsg comparison

The userspace trial controller SHALL offer typed begin-only
`--initrd-info-kmsg-logging`, requiring synchronous initramfs and marker-free
ordinary init, excluding debug and info-console. It SHALL select exactly
`rd.systemd.log_level=info rd.systemd.log_target=kmsg`, preserve existing
profiles/defaults and typed saved continuation with old missing=false, and
reject aliases/conflicts/types before UART.

It SHALL preserve the immutable artifacts, normal identity, five load/CRC,
printed/live argument and transport guards,180-second passive readiness,
complete private logging and unknown-no-input behavior. It SHALL NOT report
kmsg selection as proof that console was unused, every record was delivered,
a blocked call was identified, ordinary root worked or recovery succeeded.

<!-- UNVERIFIED: physical kmsg output/ordinary acceptance remains open; independently reviewed controller and actual host proof are recorded below. -->
*Grounding: [physical info/console result](../../../../docs/evidence/mainline-initrd-info-logging/physical-2026-10-05/README.md)
and [selected-source backend audit](../../../../docs/research/mainline-initrd-info-kmsg-comparison-2026-10-05.md). [Controller and executed actual host qualification](../../../../docs/evidence/mainline-initrd-info-kmsg-logging/host/README.md) passed independent review; no physical delivery is claimed.*

#### Scenario: Changing the destination changes observed progress

- **WHEN** qualified same-artifact info/kmsg output reaches new messages
- **THEN** record the sole changed destination and observed boundary
- **AND** retain fallback/filtering, runtime identity, cause and recovery limits

#### Scenario: Kmsg comparison remains unknown

- **WHEN** qualified login or I/O completion is absent
- **THEN** keep complete private output without candidate input or fallback trial
- **AND** require independent protected recovery or a NEW operator reset


### Requirement: The ordinary baseline is repeated before another boot intervention

The operator SHALL be able to repeat one unchanged quiet p2 ordinary policy
with existing synchronous-initramfs and marker-free selectors, without any
logging selector or new artifacts. Actual qualification SHALL establish exact
299-byte arguments/317-byte literal command and unchanged immutable/root/init/
mask/console/helper/load/CRC guards after NEW protected recovery.

The repeat SHALL retain the180-second passive readiness bound, complete private
logging and unknown-no-input policy. Its outcome SHALL be reported as a
reproducibility control, not a logging cause, ordinary-root acceptance, glass
proof or automatic recovery. Subsequent recovery SHALL be independently
verified or explicitly pending a NEW operator reset.

<!-- UNVERIFIED: ordinary acceptance remains pending; independently reviewed physical repeat did not reproduce the former closure boundary and subsequent NEW protected recovery passed. -->
*Grounding: [previous quiet ordinary boundary](../../../../docs/evidence/mainline-system-trial/current-p2-ordinary-physical-2026-10-05/README.md),
[silent kmsg capture](../../../../docs/evidence/mainline-initrd-info-kmsg-logging/physical-2026-10-05/README.md)
and [read archive/source control plan](../../../../docs/research/mainline-ordinary-baseline-repeat-2026-10-05.md). [Actual unchanged-baseline preparation](../../../../docs/evidence/mainline-system-trial/current-p2-baseline-repeat-host-2026-10-05/README.md) and [NEW protected recovery](../../../../docs/evidence/mainline-initrd-info-kmsg-logging/physical-2026-10-05/recovery.json) passed independent review. [Completed physical repeat](../../../../docs/evidence/mainline-system-trial/current-p2-baseline-repeat-physical-2026-10-05/README.md) passed independent review; subsequent NEW [protected recovery](../../../../docs/evidence/mainline-system-trial/current-p2-baseline-repeat-physical-2026-10-05/recovery.json) passed independent review.*

#### Scenario: The unchanged baseline reaches the previous unit boundary

- **WHEN** one qualified repeat again reaches closure lookup
- **THEN** record that reproduced boundary and any additional observed progress
- **AND** retain nested-command, cause, root and independent recovery limits

#### Scenario: The unchanged baseline does not reproduce prior progress

- **WHEN** qualified startup/readiness or I/O remains unknown
- **THEN** preserve the temporal difference without compensating changes/input
- **AND** require independent protected recovery or a NEW reset


### Requirement: Selected ramdisk init exec return is observable with a bounded optional probe

An additive default-disabled diagnostic SHALL emit at most one fixed versioned
INFO record containing only the signed return value after the selected ramdisk
init exec attempt, before the original success/error branch. It SHALL preserve
original init bytes/ABI/argv/env, return/fallback behavior, old Nix outputs and
protected root/console/mask/load/CRC/identity guards. Its typed begin-only
selection SHALL reject aliases/conflicts/types before UART and require exact
new source/build/archive/arguments/manifests with independent review.

The physical trial SHALL retain the180-second passive readiness bound, full
private coverage and unknown-no-input policy. Zero SHALL indicate successful
exec setup only, not user-mode transition, loader, constructors or systemd main.
Missing/partial records SHALL remain unknown. Record presence SHALL NOT imply
its own output call returned, a failing instruction was found, ordinary root
worked or recovery succeeded. Recovery SHALL be independently verified or
explicitly pending NEW reset.

<!-- UNVERIFIED: userspace transition, output-call return and ordinary acceptance remain pending; physical capture recorded one valid ret=0 with no qualified login within180s, independently reviewed. Subsequent NEW protected normal recovery passed independent review. -->
*Grounding: [independently reviewed quiet repeat](../../../../docs/evidence/mainline-system-trial/current-p2-baseline-repeat-physical-2026-10-05/README.md) and [selected source/alternative/proof plan](../../../../docs/research/mainline-init-exec-return-probe-2026-10-05.md). [Source/native/object/evaluation proof](../../../../docs/evidence/mainline-init-exec-return/host/README.md) passed independent review. [Actual full build/new-header object/artifact qualification](../../../../docs/evidence/mainline-init-exec-return/actual-host/README.md) passed independent review. [Restoration with retained roots and fresh qualification](../../../../docs/evidence/mainline-init-exec-return/restoration-host/README.md) passed independent review after the later availability failure. [Reviewed physical capture](../../../../docs/evidence/mainline-init-exec-return/physical-2026-10-05/README.md) and [exact publication](../../../../docs/evidence/mainline-init-exec-return/physical-2026-10-05/publication.json) establish exec setup success only. Subsequent NEW [protected recovery](../../../../docs/evidence/mainline-init-exec-return/physical-2026-10-05/recovery.json) passed independent review. Userspace execution, output-call return and ordinary acceptance remain UNVERIFIED; this is not a shipped capability.*

#### Scenario: Selected init exec returns zero

- **WHEN** a qualified fresh capture contains the fixed complete zero result
- **THEN** record successful exec setup with the exact artifacts and observation
- **AND** retain userspace-execution, output-call-return, cause and recovery limits

#### Scenario: Returned error or absent record

- **WHEN** a qualified capture contains a nonzero result or no complete result
- **THEN** record the returned value or unknown boundary without causal inference
- **AND** send no candidate input on unknown readiness and require protected recovery

### Requirement: PID1 return and first userspace syscall have bounded optional witnesses

An additive default-disabled child of the selected init exec-return diagnostic
SHALL preserve the parent record and offer at most two additional fixed versioned
INFO records, scoped to armed PID1: after kernel_init returns before user-exit
preparation, and after successful syscall entry from user mode before dispatch.
The arm SHALL be set only for selected ramdisk exec success with both exact
parent and transition runtime gates enabled. Ordinary-lifetime
exact1 gate and consumed-before-output one-shots SHALL prevent fallback/task/
retry output. The diagnostic SHALL NOT modify init/argv/env, return values,
assembly/sret, IRQ/timer/vector/exit-work state or existing Nix output identities.

A typed begin-only selection SHALL require exact parent/new gates, synchronous
initramfs and marker-free ordinary init, reject conflicting/invalid selection
before UART, and require independently reviewed source/context/object plus
actual build/config/DT/archive/arguments/manifest qualification. Records SHALL
be fresh and strictly ordered among present records; duplicates, malformed or
reversed observations SHALL fail closed. Missing earlier frames SHALL remain
incomplete/unknown without negating an independently valid later user ECALL
witness or fabricating missing observations. The physical capture SHALL preserve complete private logging,
protected staging/normal/load/CRC guards,180-second passive readiness and unknown
no-input behavior. Recovery SHALL be independently verified or explicitly pending
NEW reset. Ordinary root/panel/glass acceptance SHALL remain separate.

<!-- UNVERIFIED: source/controller/native/parent-header objects are independently reviewed; full matching artifact qualification and physical two-point behavior remain unverified. -->
*Grounding: [physical exec setup success without readiness](../../../../docs/evidence/mainline-init-exec-return/physical-2026-10-05/README.md) and read exact Linux source sites/context restrictions in design.md group5t. [Implemented source/native/parent-header object proof](../../../../docs/evidence/mainline-init-exec-transition/source/README.md) and [controller/qualifier fixtures](../../../../docs/evidence/mainline-init-exec-transition/controller/README.md) passed independent review. All110 prior package derivation identities are unchanged with equal config/parameters: [complete evaluation](../../../../docs/evidence/mainline-init-exec-transition/source/identity-evaluation.json). Physical witness behavior remains UNVERIFIED.*

#### Scenario: Kernel init returns before entering userspace

- **WHEN** a qualified capture records kernel-init-return after exec-result0
- **THEN** record that the original kernel_init and exec-result output call returned
- **AND** retain the new output-call-return and user-execution unknowns

#### Scenario: PID1 executes a userspace environment call

- **WHEN** a qualified capture records a valid first-user-ecall witness
- **THEN** record a user ECALL instruction and successful kernel entry setup
- **AND** retain missing earlier records as incomplete/unknown plus syscall completion, loader/constructors/systemd-main and cause limits

#### Scenario: A planned witness is missing or invalid

- **WHEN** qualified progress or record validity is absent
- **THEN** preserve the unknown boundary without candidate input or compensating changes
- **AND** require independent protected recovery or a NEW operator reset
