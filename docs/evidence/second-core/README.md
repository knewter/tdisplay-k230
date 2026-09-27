# Second-core readiness decision

Collected 2026-09-22 America/Chicago (2026-09-23 UTC) on the working persistent
Wi-Fi image. [Live handoff](live-handoff.txt) is the output of
`sh tools/second-core-readiness.sh` transferred to `/run` and executed through
the coordinator's exclusive console session. The [OpenSBI banner](opensbi-banner.txt)
is a whitelisted excerpt from the previously captured reboot of this image;
OpenSBI output is not part of Linux's dmesg. No extra reboot or register access
was needed for this investigation.

The initial evidence established a one-hart handoff, rather than an attempted
secondary CPU that failed to boot. The later
[physical CPU0 diagnostic](cpu0-identity-physical-trial.md) measured CPU0's
`mhartid=0`. The pinned OpenSBI source shows that its `Boot HART ID : 0`
is a direct CSR read on the CPU1-side boot path, establishing the same
value for CPU1 through the source-backed physical handoff attribution.

| Gate | Observed/source evidence | Decision |
| --- | --- | --- |
| Hart identity/domain | OpenSBI count 1, Domain0 `0*`; live DT contains only `cpu@0`, hart ID 0; physical CPU0 SPL and CPU1-side OpenSBI's direct CSR read both returned `mhartid=0` | Duplicate hardware IDs require an independently grounded virtual-ID or other supported two-hart mapping; current generic OpenSBI cannot distinguish the cores |
| Firmware start | OpenSBI reports HSM device `---`; Linux detects the generic HSM extension | Extension availability does not prove a secondary reset/vector implementation |
| Interrupt/timer | Live PLIC routes CPU phandle 3 to interrupts 11/9; CLINT routes the same CPU to 3/7 | Current handoff describes one CPU's external, software and timer routes |
| Linux state | `possible`, `present`, `online` all `0`; one CPU brought up | SMP is compiled, but there is no second described CPU to start |
| ISA/cache/coherency | Current C908 has RVV/Sv39; vendor AMP source explicitly manages cache and reserved memory | CPU1 ISA/cache topology and a CPU-to-CPU coherent atomic-sharing contract remain unproved |

### 2026-09-26 read-only continuation

The coordinator, holding the exclusive console, ran the fixture-tested v2
collector on the normal board. The [complete output](live-handoff-v2.txt)
is timestamped `2026-09-27T03:32:04Z`; the [first attempt](live-handoff-v2-partial.txt)
stopped when Python's read-only map of PWR returned `EPERM`. The collector was
then changed to emit that error per register and continue. It opens `/dev/mem`
with `O_RDONLY` and maps only the three named registers with `PROT_READ` when
`SECOND_CORE_READ_MMIO=1`. Neither run wrote MMIO, changed CPU state, or
rebooted. The PWR permission boundary was preserved, so those two register
values are unknown.

The operator's host runner was `/tmp/k230-core-probe-run.py`; it transferred
the inspected `tools/second-core-readiness.sh` to
`/run/second-core-readiness.sh` through `tools/console.py /dev/ttyACM0
--wait=10` and checked its SHA-256 before running this exact board command:

```sh
env SECOND_CORE_READ_MMIO=1 PATH=/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin:/run/current-system/sw/bin:/run/wrappers/bin sh /run/second-core-readiness.sh
```

The source script staged by the operator was
`/tmp/k230-second-core-readiness-v2.sh`. The installed/booted system was
`/nix/store/11y992kp7bikr5hg21i2azfvmca43i7i-nixos-system-nixos-26.11.20260919.20b1ddd`
(source `433a4226`, kernel
`/nix/store/9w07l7qyhd3xykq9wfhjlg3qqc3ijqhs-linux-riscv64-unknown-linux-gnu-6.6.36-xuantie`).

| New field | Physical observation | Interpretation |
| --- | --- | --- |
| CPU1 reset control `0x9110100c` | `0x00013000`, bit 0 clear | Consistent with physical CPU1 released; the pinned stage-1 source describes its release into U-Boot. It is not a standalone physical-to-hart map. |
| PWR CPU1 control/status `0x91103018`/`0x9110301c` | Both `<unavailable:EPERM>` | No power-state conclusion from these reads. |
| Linux CPU ISA/cache | `rv64imafdcv...`, L2 `256K`; CPU masks still all `0` | Corroborates the physical big-core handoff, with one Linux CPU. |

The pinned stage-1 overlay at `k230_linux_sdk` revision
`1104236db4d1e47873bd68924f912747b820228c` resolves the U-Boot prompt's
physical owner: `sdk_autoconf.h` sets `CONFIG_LINUX_RUN_CORE_ID 1`,
`k230_img.c:276-285` releases physical CPU1 into U-Boot and parks physical
CPU0 in `wfi`. This source finding, together with the live RVV/256K profile,
supports Linux running on physical CPU1. It does not make the one Linux
logical hart ID (`0`) a unique identifier across both physical cores. A
first-hand [K230 Linux DTS review](https://lkml.rescloud.iu.edu/2403.3/00159.html)
reports the big core's `mhartid` as 0, and a later [K230 board modeling
discussion](https://www.mail-archive.com/qemu-devel@nongnu.org/msg1188749.html)
reports both cores as 0. Those reports have not been tested on this board.
They strengthen the stop condition against adding a guessed `cpu@1` node.

Host checks on 2026-09-26: `sh tools/test-second-core-readiness.sh` passed
both populated and denied-mapping fixtures; `python3 -m unittest discover -s
tests -p test_ums_target.py` passed 16 tests, including refusal of a wrong
sector count. The known UMS card in `docs/uboot-ums.md` has `249872384`
sectors, but that number was not remeasured in this session, so a live UMS
fallback check remains open. These host results do not complete the PWR
read, recovery rehearsal, or second-core release gates.

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

### 2026-09-27 bounded physical identity trial

The default-off diagnostic package was installed in the two raw SPL slots
after original 512 KiB slot backups were verified both on and off board.
It printed `CPU0_SPL_IDENTITY mhartid=0x0 misa=0x800000000094112f`,
then the existing one-CPU Linux boot completed. Both original SPL slots
were restored, direct-read hashes matched the originals, and a subsequent
normal reboot reached the root prompt with all four shell services active.
The [trial record](cpu0-identity-physical-trial.md) gives commands, hashes,
captures, and the pinned OpenSBI source chain showing that the CPU1-side
`Boot HART ID : 0` is a direct `CSR.MHARTID` read. Both physical cores
therefore report zero through distinct boot paths. This does not establish
a usable two-hart mapping or Linux SMP.
