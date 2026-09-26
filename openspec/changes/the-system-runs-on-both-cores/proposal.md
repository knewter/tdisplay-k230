## Why

Right now every background job — Wi-Fi association, a video decode helper, a
Python theme helper, a udev-triggered script — competes with the Sway
compositor for the same single hart. A person notices this as the shell
stuttering while the theme helper regenerates a wallpaper cache, or a decode
helper stealing frames from the compositor during a card animation. A second
usable hart would let that background work run without taking cycles from the
thing being looked at.

Be honest about what that second hart actually is. `docs/evidence/cpu-readiness.txt`
records the current Linux hart reporting RVV and a 256 KiB L2; the K230 TRM
section 1.3.2 assigns exactly that RVV/256 KiB profile to the 1.6 GHz CPU1.
That makes CPU1 execution a strong inference for the hart Linux already runs
on (`openspec/specs/system/second-core-readiness/spec.md`,
"A second-core decision distinguishes handoff evidence from silicon
capability"). It is still an inference, not a register-proven fact: no source
or captured handoff in this repository maps a physical core to a Linux hart
ID. If the inference holds, **the second hart is the 800 MHz little core**,
not a matching twin of the one running the shell today. Plain-terms benefit:
a background core for decode assistance, network/SDIO servicing, Python
helpers and the theme helper, run at half the clock of the compositor's core
and — per the TRM's CPU0/CPU1 split — without a vector unit. It is a place to
put work that should not stall the display, not a second compositor engine
and not a path to double interactive throughput.

That last property is also the main hazard. This project's kernel now
carries an RVV path by default (`the-system-enables-proven-c908-extensions`,
modifying `system/kernel`: "the ordinary system uses physically proved
vectors"). A kernel built with V compiles vector instructions into library
and userspace code paths that assume the executing hart has RVV. RISC-V does
not require every hart in an SMP system to share the same instruction-set
extensions, and this SoC's own two cores do not: CPU1 has RVV 1.0, CPU0 does
not (K230 TRM section 1.3.2; `docs/research/second-core-feasibility.md`).
Linux's generic scheduler has no built-in concept of "this hart lacks an
extension the running binary needs" — a task or library call that uses a
vector instruction, migrated onto a hart without RVV, takes an illegal-
instruction trap, not a graceful fallback. Any SMP plan for this board is
therefore a heterogeneous-ISA scheduling problem before it is a throughput
problem.

## What Changes

This proposal does not add a `cpu@1` node, write a reset or power register, or
change OpenSBI, U-Boot, or the kernel. It records a staged, evidence-gated
plan and the decision-quality bar each stage must clear before the next one
is attempted, matching `.skills/k230-spec-change/SKILL.md`'s grounding order
and `docs/research/second-core-feasibility.md`'s "minimal recoverable
experiment" and "passive handoff audit" sections:

- **(a) Read-only board probes.** No reset, power, or CPU-state write.
  Extend the existing read-only collector
  (`tools/second-core-readiness.sh`) to add the two documented read-only RMU/
  PWR register reads (`0x9110100c`, `0x91103018`, `0x9110301c` — TRM sections
  2.1.4 and 2.3.4) taken with a proven read-only MMIO method, and record
  whether the kernel exposes an OpenSBI HSM hart-status query without a
  Linux CPU up/down transition. Cross-check `/proc/cpuinfo`'s `misa`/`uarch`
  and the live L2 size against the TRM's CPU0/CPU1 table to sharpen, not
  replace, the existing inference.
- **(b) An OpenSBI + device-tree experiment.** Only after (a) yields a
  documented physical hart ID, reset-vector value, and PLIC/ACLINT context
  for the second core (from Canaan or a read-only register observation that
  settles it) does this project prepare a `cpu@1` node with verified
  interrupt routing and an OpenSBI domain/HSM start path. Two release
  mechanisms are open and neither is chosen yet: OpenSBI platform code
  performing the `CPU1_RST_CTL`/reset-vector writes itself, or U-Boot
  releasing CPU1 into a spin-table before handing off to OpenSBI. This stage
  is the first one that writes a reset/power register, and it does not run
  without the explicit authorization and recovery rehearsal in Risk and
  recovery below.
- **(c) Coherency validation.** Only after a second hart demonstrably starts
  does this project run atomic/litmus-style stress and a timer/IPI stress
  across both harts, because no CPU0/CPU1 cache-coherency or atomic-sharing
  contract is documented anywhere this project has read (TRM or vendor SDK).
- **(d) ISA-aware SMP scheduling.** Only after (c) passes does Linux SMP
  scheduling get enabled, and only with an explicit heterogeneous-ISA
  constraint: either hard CPU affinity that keeps vector-capable code off the
  little core, or a kernel-level per-hart-safe gate before any task carrying
  a vector-using library path can run there. Until one of those exists,
  enabling scheduling across both harts is not safe with the current
  RVV-by-default kernel.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `system/second-core-readiness`: records the staged evidence-gated bring-up
  plan itself — what each stage requires before the next may start, which
  stages write hardware state, and the heterogeneous-ISA scheduling
  constraint — as requirements the project is held to, not only a readiness
  snapshot.

## Impact

No Nix derivation, kernel, device tree, OpenSBI, or U-Boot source changes.
`tools/second-core-readiness.sh` gains new read-only fields in a later,
separately authorized change; this proposal only specifies what they must be
and why. Every stage past (a) needs the physical board and an explicit user
authorization before any reset/power register write, per AGENTS.md.
