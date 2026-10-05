# Bracket the ordinary init exec attempt

The [unchanged quiet repeat](../evidence/mainline-system-trial/current-p2-baseline-repeat-physical-2026-10-05/README.md)
did not reproduce the earlier closure boundary. It showed fresh Linux and the
pre-exec `/init` announcement without observed systemd startup. Closure-helper
instrumentation is premature. Group5s asks one earlier question: did the
kernel's selected ramdisk init exec attempt return, and with what result?

Selected p2 source `0l4mgw9hr1j7pj247jsrxjd478fnlfy8-linux-mainline-k230-uart-progress-memory-printk-src`
has `run_init_process` at init/main.c1567–1584: announce, call kernel_execve,
retain its signed return value. kernel_init1693–1700 calls it for the selected
ramdisk init, returns on zero and retains the existing error/fallback otherwise.
The optional probe will emit one fixed versioned INFO record containing only
that signed return value, immediately after this selected attempt returns and
before its existing conditional. It will not instrument generic fallback calls.
A separate fixed opt-in, default disabled, must work while existing boot tracing
stays disabled. No addresses, environments, arbitrary payloads or unbounded loop.

Selected fs/exec.c1968–2011 calls bprm_execve;1867–1880 marks successful exec
after exec_binprm. fs/binfmt_elf.c1375–1379 sets user registers and returns zero.
arch/riscv/kernel/process.c144–157 sets EPC/SP;227–232 performs the later
transition to userspace. A zero record therefore supports successful exec setup;
it does **not** prove that transition, the ELF loader, constructors or systemd
main executed. A nonzero record supports a returned error, without a failed
syscall/cause inference. Missing, malformed or partial output remains unknown.
Record presence does not prove its own printk call returned; emission can block,
be filtered or drop. Do not compensate with forced output or more verbosity.

This is an additive child kernel/source/dev/system/trial-bundle variant. Keep
old output identities unchanged and preserve selected p2 config, DT hardware,
root/console/masks, original init ABI/argv/env, and original return/fallback
branches. Qualify every necessary new dependency/store-path/archive difference;
retain exact archived systemd `/init`, Bash, loader and closure-helper bytes.
Do not claim the new Image is byte-equal to p2. No timer/IRQ/MMIO/SMP, tracing,
init wrapper, systemd package or root/target intervention belongs to this probe.

A Bash PID1 wrapper costs less to build but adds interpreter/loader execution,
environment/signals and different exec-failure/fallback semantics. The external
p2 archive has no /dev/kmsg; creating it before systemd's early mount would create
a regular file. Inherited-console output may also block. Targeted systemd-main
markers are a possible later probe only after this exec boundary is clarified;
they require changing the systemd ELF and cannot observe pre-main loader failure.

Land this plan before source. Independently review narrow patch/typed-controller
fixtures and compiled RISC-V object, then actual new build/archive/manifest/
load/CRC and argument qualification. Require NEW protected normal recovery,
sole board/UART reservation and one passive180-second capture, full private
logging, no candidate input on unknown, independent recovery or explicit pending
NEW reset. Commit safe facts, inspect exact CI/publication. Ordinary task5b.5
and physical execution/cause remain **UNVERIFIED**; no new build or probe has run.
