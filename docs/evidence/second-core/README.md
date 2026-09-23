# Second-core readiness decision

Collected 2026-09-22 America/Chicago (2026-09-23 UTC) on the working persistent
Wi-Fi image. [Live handoff](live-handoff.txt) is the output of
`sh tools/second-core-readiness.sh` transferred to `/run` and executed through
the coordinator's exclusive console session. The [OpenSBI banner](opensbi-banner.txt)
is a whitelisted excerpt from the previously captured reboot of this image;
OpenSBI output is not part of Linux's dmesg. No extra reboot or register access
was needed for this investigation.

The evidence establishes a one-hart handoff, rather than an attempted secondary
CPU that failed to boot. It does not identify logical hart 0 as physical CPU0.

| Gate | Observed/source evidence | Decision |
| --- | --- | --- |
| Hart identity/domain | OpenSBI count 1, Domain0 `0*`; live DT contains only `cpu@0`, hart ID 0 | No assigned second hart or verified physical-to-logical map |
| Firmware start | OpenSBI reports HSM device `---`; Linux detects the generic HSM extension | Extension availability does not prove a secondary reset/vector implementation |
| Interrupt/timer | Live PLIC routes CPU phandle 3 to interrupts 11/9; CLINT routes the same CPU to 3/7 | Current handoff describes one CPU's external, software and timer routes |
| Linux state | `possible`, `present`, `online` all `0`; one CPU brought up | SMP is compiled, but there is no second described CPU to start |
| ISA/cache/coherency | Current C908 has RVV/Sv39; vendor AMP source explicitly manages cache and reserved memory | CPU1 ISA/cache topology and a CPU-to-CPU coherent atomic-sharing contract remain unproved |

**Decision:** retain the working single-hart image. Do not add a guessed DT CPU
node or release/reset a core. The [source investigation](../../research/second-core-feasibility.md)
identifies the vendor AMP reset-vector sequence but does not establish Linux SMP
compatibility. AMP would also need a separate payload, reserved memory,
cache-maintained shared buffers, mailbox protocol and peripheral ownership.

The next bring-up proposal must first pin source or vendor documentation for the
physical hart map, CPU1 vector/domain/HSM startup, timer/IPI/PLIC contexts and
coherency/atomics. Once those gates are met, use a recoverable experimental image
and require two enumerated OpenSBI harts, two Linux CPUs, timer/IPI stress and
shared-memory atomic tests before running video comparisons. If coherency cannot
be established, scope an AMP offload protocol instead of claiming a second Linux
CPU. The readiness investigation is complete; second-core enablement is not.
