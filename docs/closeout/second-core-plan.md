# Second-core closeout: status and the path forward

Written 2026-09-28 while taking over `the-system-runs-on-both-cores` and
`the-small-core-runs-a-recoverable-heartbeat` from an absent operator, on
`close/second-core` off local `master`. This is a status and planning
document, not a new proposal; it does not change any spec. See
`docs/evidence/second-core/README.md`, `cpu0-identity-physical-trial.md`,
and `docs/research/second-core-feasibility.md` for the underlying evidence,
and the two changes' `tasks.md` for the task-by-task audit performed
alongside this document.

## Honest current status

The board has two Xuantie C908 cores (K230 TRM section 1.3.2): CPU0 at
800 MHz, 128 KiB L2, no vector unit; CPU1 at 1.6 GHz, 256 KiB L2, RVV 1.0.
Pinned stage-1 source (`board/canaan/common/k230_img.c:276-285`,
`sdk_autoconf.h:16` `CONFIG_LINUX_RUN_CORE_ID 1`) releases **physical CPU1**
into U-Boot/OpenSBI/Linux and parks **physical CPU0** in `wfi`. The running
system's one Linux hart is physical CPU1, corroborated by its live
RVV/256 KiB-L2 profile (`docs/evidence/cpu-readiness.txt`,
`docs/evidence/second-core/live-handoff-v2.txt`). The "second core" this
project would add back is physical CPU0, the small non-vector core, not a
twin of the core already running the shell.

The blocking fact, now measured on this board rather than only reported
secondhand: **both physical cores read `CSR.MHARTID = 0`.**
`docs/evidence/second-core/cpu0-identity-physical-trial.md` recorded a
first-hand `CPU0_SPL_IDENTITY mhartid=0x0 misa=0x800000000094112f` from a
default-off SPL diagnostic on physical CPU0, immediately before the
existing CPU1 release, then restored the original SPL bytes and proved a
normal reboot. The CPU1-side OpenSBI banner's `Boot HART ID : 0` is the same
CSR read, traced through pinned OpenSBI source
(`include/sbi/riscv_asm.h:166` `current_hartid()`, `lib/sbi/sbi_init.c:534,394,169`).
So this is no longer just the QEMU-author and Linux-DTS-author secondhand
reports cited in `second-core-feasibility.md` — it is this board's own
firmware reporting duplicate hardware hart IDs on both executing cores.

Nothing has been walked back from that finding. The `2026-09-26 source
correction` in `the-system-runs-on-both-cores/proposal.md` also formally
suspended `the-small-core-runs-a-recoverable-heartbeat`: a CPU0
heartbeat/AMP payload proves independent physical execution, not Linux SMP,
and is "not an acceptance path" for the requested outcome. That suspension
predates this closeout; it is recorded, not decided, here.

**What is actually done:** every host-only and pinned-source-audit task in
both changes (register-probe tooling + fixture, kernel source grep for an
HSM status passthrough, the default-off SPL identity diagnostic build, the
CPU0 heartbeat payload/runbook prep) is complete and, where re-checked
during this audit, reproduced independently — see the two `tasks.md` files
for citations. One board-gated read-only task (1.3, the register/ISA
cross-check) and one documentation task (1.4) were also closed on audit,
because their evidence was already committed but not yet ticked. **What is
not done:** the external-card-reader recovery rehearsal, the CPU0 identity
scheme, any interrupt/timer routing for CPU0, the coherency diagnostic, and
therefore any two-CPU boot. No task claims a result it does not have, and no
`<!-- UNVERIFIED -->` marker was resolved into a claim.

## What Linux SMP on these two harts would actually require

Duplicate `mhartid` is not a paperwork problem; it breaks the identity
assumption at every layer OpenSBI and Linux use to address a hart:

- **OpenSBI hart-index remapping.** The pinned OpenSBI 1.4 generic platform
  builds its hart table from device-tree `reg` values
  (`platform/generic/platform.c:95-132`, `lib/utils/fdt/fdt_helper.c:263-284`),
  and its current-hart and hart-lookup helpers both resolve through
  `CSR_MHARTID` — `riscv_asm.h:166`'s `current_hartid()`, and
  `sbi_scratch.c:24-32`'s **first-match** table lookup. Firmware warm entry
  (`firmware/fw_base.S:441-462`) also picks the first matching hart index
  for M-mode scratch/stack before HSM ever runs. With both cores at
  `mhartid=0`, a naive `cpu@1` DT node does not create a second SBI hart; it
  makes CPU0 alias CPU1's boot-hart scratch and stack. `sbi_hsm.c:300-361`
  then cannot target CPU0 as a distinct HSM/IPI destination either. A
  working two-hart OpenSBI here needs either a K230-specific hart-ID source
  earlier than `CSR_MHARTID` (none is defined in the pinned vendor overlay —
  `platform/generic/thead/thead-generic.c` only does C908 errata/PMU setup,
  and a grep of the pinned U-Boot/OpenSBI overlays for another physical
  core-ID CSR found none), or a Canaan-documented remapping this project
  does not currently have.
- **DT `cpu` nodes with distinct `reg` values.** Even granting a working
  virtual ID, the DT must carry it consistently into `reg`, and every
  consumer that currently assumes one CPU — the PLIC binding at
  `k230.dtsi:210-218` and the CLINT binding at `:255-259`, both wired only
  to `cpu0_intc` today — needs a second, correctly routed interrupt context
  for CPU0. Canaan's own separate small-core Linux DT
  (`src/little/linux/.../k230.dtsi:18-63` in the public SDK, not this
  project's pinned revision) places PLIC/CLINT at different base addresses
  for that core, which is evidence the hardware exposes per-core interrupt
  controllers, not evidence that one joint DT can address both from a single
  Linux image.
- **Cache coherency.** No document in hand — not the TRM, not the vendor
  SDK — states a CPU0/CPU1 cache-coherency or shared-atomic contract. The
  DT's `dma-noncoherent` property is about DMA, not CPU-to-CPU. The vendor
  AMP driver's explicit cache flush-and-invalidate around every shared
  buffer access is adverse evidence: the vendor's own working inter-core
  path does not trust implicit coherency. Linux SMP shares page tables,
  runqueues and spinlocks from the first tick; that cannot be the first
  experiment run against this gap. This project's own heartbeat payload
  (`tools/small-core-heartbeat.S`) already treats coherency as unproven —
  it issues the pinned `l2cache.ciall` encoding after every write and reads
  each output page only once from U-Boot, specifically because "the two
  physical cores do not have a proven coherent-cache contract."
- **ISA mismatch.** CPU1 has RVV 1.0; CPU0 does not. This project's kernel
  is already RVV-by-default (`the-system-enables-proven-c908-extensions`).
  Linux's generic scheduler has no notion of "this hart lacks an extension
  the running binary needs" — a migrated vector instruction on CPU0 traps,
  it does not fall back. A first SMP image would need to ship scalar
  kernel+userspace with RVV disabled everywhere, or a proven per-hart
  `hwprobe`/scheduling contract, before any workload becomes migratable
  between the two cores. Affinity for a few pinned tasks does not protect
  the general, unpinned workload.
- **How vendor RT-Smart AMP avoids all of this.** The vendor path
  (`k230-amp.c`, `amp_test.c`) never asks OpenSBI or Linux to treat CPU0 as
  a peer hart. It loads a wholly separate RT-Smart firmware image into a
  reserved region, flushes it from cache by hand, writes the CPU1
  reset-vector register and `CPU1_RST_CTL` sequence directly from a Linux
  driver, and keeps ownership of shared buffers and peripherals explicit and
  exclusive. There is no SBI HSM handshake, no shared page table, no
  scheduler decision, and no reliance on implicit coherency beyond
  hand-managed cache maintenance. It sidesteps the duplicate-`mhartid`
  problem entirely because it never needs OpenSBI or Linux to address the
  second core by hart ID at all — it addresses it by a fixed reset-vector
  write, the same primitive this project's own heartbeat probe uses.

Put plainly: Linux SMP needs an identity fix at the firmware layer that
nothing in hand currently supplies. AMP/heartbeat-style offload needs none
of that, because it never asks the scheduler to treat CPU0 as a hart.

## Next 3 concrete steps

1. **Rehearse the external-card-reader recovery route, independent of any
   further register write.** This closes task 2.1/2.2 of
   `the-system-runs-on-both-cores` and is a prerequisite for every later
   hardware-writing stage in both changes. Procedure: with the board powered
   off and the card removed, read the current card's whole-disk identity
   (by-id path, model, serial, sector count) with the card still in the
   board if possible beforehand; move it to an external USB/SD reader on the
   host; confirm the same identity and that it is unmounted; `dd` the two
   raw SPL slots (1 MiB and 1.5 MiB offsets, 512 KiB each,
   `nix/stage1.nix:176-180`) to local files and hash them; deliberately
   corrupt a **disposable** copy's SPL slot (not the real card) to confirm
   the reader-based restore procedure actually recovers a card whose SPL
   cannot start U-Boot, which the on-board `dd`-from-Linux method used in
   the 2026-09-27 trial cannot prove (it requires Linux to already be
   running to read the backup off the card). The exact command sequence is
   already written in `docs/evidence/second-core/cpu0-identity-trial.md`'s
   "Prepared external-reader procedure"; it only needs to be executed and
   its result committed. **Risk:** low if performed on a spare/disposable
   card first; the live card is only touched after the reader route is
   proven on a throwaway one. **Effort:** one board/reader session, under an
   hour. **Authorization:** needs the user's go-ahead to use the board,
   the card, and an external reader for this session (AGENTS.md: any
   session touching the board/card needs the operator's coordinated
   session; this plan does not authorize it by itself).

2. **Decide, as a scope decision, whether to pursue a K230-specific SBI
   hart-identity scheme at all, or to formally redirect this budget to the
   AMP/heartbeat offload path.** This is not a board task; it is a decision
   the user should make now that the duplicate-`mhartid` finding is
   board-confirmed rather than secondhand. If the answer is "keep pursuing
   SMP," the concrete next unit of work is a source/documentation-only
   search for any K230-specific hart discriminator (an undocumented CSR, an
   OTP/efuse field, a strapping pin reflected in a register) — a few days of
   source reading and, if nothing surfaces, a support request to Canaan.
   If the answer is "pursue AMP-style offload instead," the concrete next
   unit of work is finishing the already-drafted heartbeat proposal's
   physical proof (step 3 below), since its payload and runbook are ready
   now. **Risk:** none (it is a decision, not an action). **Effort:**
   the user's time to read this document and the two changes' `Why`
   sections. **Authorization:** this is exactly the authorization decision
   itself — no board or card action follows until it is made.

3. **If AMP/heartbeat is chosen: run the already-prepared CPU0 heartbeat
   probe on a disposable card** (`the-small-core-runs-a-recoverable-heartbeat`
   tasks 3.1/3.2). The payload (`tools/small-core-heartbeat.S`), its host
   proof (`docs/evidence/second-core/heartbeat-host.md`, reproduced during
   this audit with an identical SHA-256), and the operator runbook
   (`docs/evidence/second-core/heartbeat-runbook.md`) are ready. This uses
   only the pinned, already-shipped `boot_baremetal 0` U-Boot command; it
   writes no new firmware and stays entirely on a disposable card. **Risk:**
   low-to-moderate — a wrong load/output address could corrupt the live
   U-Boot session, which is why the runbook requires a `bdinfo` memory check
   and a rehearsed recovery (step 1) before release, and the whole test
   ends in a board reset back to the known-good card. **Effort:** one board
   session, well under an hour once the recovery rehearsal from step 1 is
   in hand. **Authorization:** needs the user's go-ahead for a board session
   with a disposable card; per AGENTS.md, this is a hardware-writing
   experiment (it writes CPU0's reset vector and `CPU0_RST_CTL`) and needs
   the rehearsed recovery from step 1 to already be verified before it can
   run, and it must NOT be treated as satisfying the Linux SMP proposal.

Everything past these three steps — a two-hart OpenSBI/DT experiment, the
coherency diagnostic, ISA-aware scheduling — stays blocked behind step 2's
decision and, for the SMP branch, behind actually finding an identity
scheme that does not currently exist in any source or documentation this
project has read.

## Recommendation

Linux SMP is not realistic with what is currently known. The duplicate
`mhartid=0` finding is now measured on this board, not just reported by two
external developers, and it breaks OpenSBI's hart table, its warm-entry
scratch/stack selection, and its HSM/IPI targeting simultaneously — before
DT interrupt routing, before coherency, before the RVV mismatch are even
reached. Nothing in the pinned vendor source, the TRM, or the public SDK
supplies a second per-core identity signal to fix that. Pursuing SMP further
means either discovering an undocumented hardware discriminator or getting
a statement from Canaan; absent one of those, this is a research dead end,
not an engineering backlog.

The AMP/heartbeat-style offload route is the practical one, precisely
because it never needs OpenSBI or Linux to treat CPU0 as an addressable SBI
hart. It reuses the pinned `boot_baremetal 0` release primitive, needs no
new firmware, and has a physically-proved sibling technique already on this
board (the CPU0 SPL identity diagnostic used the same “release, observe,
restore” shape). It cannot deliver shared Linux scheduling or a second
general-purpose CPU — only a separately loaded, explicitly managed payload
on the small core, coordinated by hand rather than by the kernel. That is a
real, bounded capability (network servicing, a decode helper, the theme
helper, once a mailbox/IPC design exists) and it is achievable with evidence
already in hand. It is not what "Linux SMP" originally promised, and this
document does not pretend otherwise; `the-small-core-runs-a-recoverable-heartbeat`
already says the same thing in its own suspension note and its "AMP heartbeat
does not imply shared Linux scheduling" requirement.

## 2026-09-28 addendum: recovery rehearsal waived

The user made two decisions the same day this plan was written, both
recorded here and in `the-small-core-runs-as-a-coprocessor`'s own
proposal.md/design.md/tasks.md:

1. **Scope split (a-d and f authorized):** see that change's own proposal
   for the AMP redirect itself; this addendum covers only the recovery
   procedure below.
2. **The external-card-reader recovery rehearsal in "Next 3 concrete
   steps" step 1 is waived.** The user: "we can easily fix the sd card
   damn. don't worry about recovery we've literally done that fine already
   before. i don't want to do a heartbeat test on a spare card." This
   plan's step 1 (rehearse the external-reader recovery route on a
   disposable card before any further register write) and step 3's
   "disposable card" requirement are both superseded by this decision. No
   task in `the-system-runs-on-both-cores`, `the-small-core-runs-a-
   recoverable-heartbeat`, or `the-small-core-runs-as-a-coprocessor` may
   require a separate spare/disposable card going forward; every board
   step in this project's second-core work runs on the normal card. The
   fallback recovery route for a failed or hung release is the
   already-proven U-Boot one-shot boot from `boot-prev`
   (`docs/evidence/card-shell/bottom-band-flicker/kernel-patch-boot-panic.md`)
   or `ums`/flash reimaging (`docs/uboot-ums.md`), not a rehearsed
   external-reader restore.

This does **not** waive per-write authorization: every board step that
writes a CPU0 reset, power, vector, or reset-controller register still
needs the user's explicit authorization at the time it runs, exactly as
before. The three changes' own `tasks.md`/`specs/` files have been updated
to reflect this waiver directly; this addendum is the cross-referenced
record of the decision itself.
