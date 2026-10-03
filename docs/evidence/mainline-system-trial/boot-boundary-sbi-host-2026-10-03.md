# Optional four-record SBI boot-boundary diagnosis — host proof

2026-10-03 UTC. Branch `mainline-boot-boundary-sbi`, base
`174f8c164b870e5ecd9fa327eef202518fb25b20`, worktree
`/home/jadams/tmp/k230-mainline-boot-boundary-sbi`.
This is source/native/API/object/evaluation proof only. Complete matching
kernel/bundle build, actual direct-SBI output, ordinary init/root/login,
automatic return and deliberate glass touch remain **UNVERIFIED**.
Task 5b.5 stays open. No board/UART, full kernel build, staging or protected
normal file/profile change was performed.

## Bounded increment and interpretation

`kernelMainlineBootTraceSbi` applies only the small additional
`init/main.c` patch to the original boot-trace source. Derivation inspection
verifies its input is the realized
`/nix/store/5k23sa4pbcs651vssp6ybifnr5qc1g9g-linux-mainline-k230-boot-trace-src`;
that file's original `init/main.c` SHA-256 is
`ce95e6b40b1cbdebff28f4f3434afb87a51e207cf4e7928588b820904e16520d`.
The original trace, DRM/restart/five-clock, console, observer and vendor/default
outputs remain unchanged. No kernel driver or console registration changes.

Four unique public records immediately bracket the original
`initcalls-exit` and `basic-setup-exit` printk marker calls. Patched lines
1531/1533 surround line 1532; lines 1758/1760 surround line 1759. Original
printk markers are retained. Both outer SBI calls are outside the marker's
nbcon emergency/preemption interval. They perform no firmware reads, guessed
MMIO, UART opening/settings, console registration or printk fallback.

```text
K230_BOOT_SBI_V1 point=initcalls-before
K230_BOOT_SBI_V1 point=initcalls-after
K230_BOOT_SBI_V1 point=basic-before
K230_BOOT_SBI_V1 point=basic-after
```

Each buffer has leading/trailing CRLF, is `static const` ordinary rodata,
aligned to 64 bytes, and includes at most 64 bytes including its terminating
NUL. The writer passes `sizeof(record)-1`; compile-time and runtime bounds
exclude overlong/empty writes. There are only four fixed call sites, one
attempt per reached point, with no polling, retry or fallback.

Both exact runtime flags `k230.boot_trace=1` and `k230.boot_trace_sbi=1`,
`CONFIG_RISCV_SBI` and `sbi_debug_console_available` are required. Exact
option value 1 enables the new gate; invalid, bare, empty or absent flags do
not. `sbi.c:691–694` sets availability only after the version/DBCN probe.
The API in `arch/riscv/kernel/sbi.c:591–617` handles vmalloc buffers through
`vmalloc_to_page` plus page offset, mapped kernel buffers through `__pa`, and
clamps a crossing-page write. Aligned <=64-byte static buffers are wholly
inside a 4KiB page, avoiding both VMAP_STACK formatting and page truncation.
RISC-V `asm/page.h:133–150` supplies kernel-mapping physical conversion.

The helper regards only returned count == requested length as complete.
**Call sites deliberately discard that boolean.** Full/partial/zero/error
return status is not transmitted and is not physical proof. A complete
visible point establishes that execution reached an output attempt; it does
not establish that the ECALL returned. A later point establishes progress
past earlier calls, but does not encode their returned byte counts. Missing,
partial, duplicated or interleaved output remains inconclusive/unknown.
These fixed records bypass printk/nbcon/8250 ownership, but still share
firmware and the physical UART. They introduce timing perturbation.

`arch/riscv/kernel/sbi_ecall.c:27–46` has trace hooks and one ECALL with no
wall-clock deadline. One attempt does **not** bound a stalled firmware call
or guarantee recovery. In contrast, `earlycon-riscv-sbi.c:30–37` retries until
length reaches zero and does not break on zero progress; this increment does
not use that writer or add earlycon/keep_bootcon. No automatic reset claim.

## Host checks

- `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -p test_mainline_boot_trace_sbi.py -v` — **10 passed**. Native GCC compiles the actual added helper for SBI-enabled and disabled builds, executes runtime/config/extension gates, exact buffers, full/partial/zero/error returns, length bounds and four attempts with zero progress. Native mocks do not execute firmware.
- `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -p 'test_mainline_boot_trace*.py' -v` — **17 passed**, including the unchanged original seven tests.
- `nix-instantiate --parse nix/kernel-mainline-boot-trace-sbi.nix` and `nix-instantiate --parse flake.nix` — **passed**.
- `patch --batch --fuzz=0 <scratch-main.c> nix/patches/mainline/k230-boot-trace-sbi.patch` on an exact copy of the source above — **passed**. Result exactly equals the compiled C. Patch SHA-256: `70df9df969084fb0160aea18bf1c09198210d15904357c9ef24b2a1cdd499cd4`.

The actual original installed kernel dev build headers/config were copied
privately from
`/nix/store/k9clwc0icv3xr6caplk2sp2s866875fj-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev/lib/modules/7.3.0-rc5/build`.
The immutable original was not modified. `.config` SHA-256:
`c5c128ed8b9701f78a0b8bd4f18dacd0d2407ae90eda79a35bba2d9f5ffbeae7`.
Actual config enables 64BIT, RISCV_SBI, VMAP_STACK, PREEMPTION and 4KiB pages;
KUNIT and DEBUG_VIRTUAL are disabled. A private external Kbuild directory
contains the actual additionally patched `main.c` and `obj-y += main.o`.

```sh
make -C /nix/store/5k23sa4pbcs651vssp6ybifnr5qc1g9g-linux-mainline-k230-boot-trace-src \
  O=/home/jadams/tmp/k230-boot-trace-sbi-object/build \
  M=/home/jadams/tmp/k230-boot-trace-sbi-object/module ARCH=riscv \
  CROSS_COMPILE=/nix/store/4j2mwxqjvnyr6da0925sp0bm4jaj5r5i-riscv64-unknown-linux-gnu-gcc-wrapper-15.3.0/bin/riscv64-unknown-linux-gnu- \
  W=1 main.o
```

**Passed**, actual ELF64 little-endian RISC-V relocatable object, no MODULE
define. `readelf -sW/-SW` places the helper in `.text.unlikely`, enable state
in `.sbss`, only setup in `.init.text`, and all four buffers in ordinary
`.rodata` with section alignment 64. Buffer offsets 0x80/0xc0/0x100/0x140
and symbol sizes 44/43/40/39 include NUL and satisfy the page bound.
`sbi_debug_console_write` remains a final-link reference. No full link/run.
Patched C SHA-256: `fa235885447587df2f5125f1a5c39bc392d137f2e42a2d6c0c5ceb6f313184d5`.
Object SHA-256: `0bcf52c9b7c96a68584d8d6dfacace1850e928debefcbcfd6c72fd3b79f5db36`.

## Optional outputs and evaluation

`k230-mainline-boot-trace-sbi` inherits the original serial-only ordinary-init
variant and replaces only its kernel and parameter list, adding exactly one
new flag. A stronger local list priority avoids merging duplicate mkForce
lists. The trial builder remains unchanged and appends the selected sole
system init. Evaluated parameters are:

```text
consoleblank=0 console=ttyS0,115200n8 root=fstab loglevel=4
lsm=landlock,yama,bpf loglevel=7 k230.boot_trace=1 k230.boot_trace_sbi=1
```

Offline evaluated derivations (not built): kernel `fygkrgq6ifyndhs7fb459a3pkcmk7a49`,
source `k2lgf9zkq16q5dicqjq1vwqyz1gac4xv`, system `6ra4xv0rhmr00bbmkrh5rp10yhh4q3j6`,
bundle `zw4hlbj25pyj9yfly0w3rpfqjhsssx8w`; all `/nix/store/*.drv` with
corresponding kernel/source/system/trial names. Uname remains `7.3.0-rc5`.

```sh
nix eval --offline --no-write-lock-file --json --impure --expr '
  let f = builtins.getFlake (toString /home/jadams/tmp/k230-mainline-boot-boundary-sbi);
      p = f.packages.x86_64-linux;
      c = f.nixosConfigurations.k230-mainline-boot-trace-sbi.config;
  in assert p.kernelMainlineBootTraceSbi.drvPath == c.boot.kernelPackages.kernel.drvPath; {
    kernel = p.kernelMainlineBootTraceSbi.drvPath;
    source = p.kernelMainlineBootTraceSbi.src.drvPath;
    system = c.system.build.toplevel.drvPath;
    bundle = p.kernelMainlineBootTraceSbiTrialBootFiles.drvPath;
    params = c.boot.kernelParams;
    uname = c.boot.kernelPackages.kernel.version;
  }'
nix derivation show /nix/store/k2lgf9zkq16q5dicqjq1vwqyz1gac4xv-linux-mainline-k230-boot-trace-sbi-src.drv
nix eval --offline --no-write-lock-file --json --impure --expr '
  let old = builtins.getFlake "git+file:///home/jadams/tmp/k230-mainline-boot-boundary-sbi?rev=174f8c164b870e5ecd9fa327eef202518fb25b20";
      new = builtins.getFlake (toString /home/jadams/tmp/k230-mainline-boot-boundary-sbi);
      names = [ "kernel" "kernelMainline" "kernelMainlineDrm"
        "kernelMainlineDrmTrialBootFiles" "kernelMainlineUartObserverBootFiles"
        "kernelMainlineBootTrace" "kernelMainlineBootTraceTrialBootFiles"
        "toplevel" "toplevel-mainline-console" "toplevel-mainline-drm-trial"
        "toplevel-mainline-uart-observer" "toplevel-mainline-boot-trace" ];
      paths = f: builtins.listToAttrs (map (name: {
        inherit name; value = f.packages.x86_64-linux.${name}.drvPath;
      }) names);
  in assert paths old == paths new; { before = paths old; after = paths new; }'
```

The new identity/selected kernel/parameter evaluation and exact already-traced
source-input inspection passed. All twelve existing derivation identities,
including the original optional trace kernel/system/bundle, compare equal to
base 174f8c16. No realization/full kernel build was requested by evaluation.
`openspec validate the-board-runs-a-mainline-kernel --strict` and
`openspec validate --all` passed (56 items). `git diff --check` and staged
whitespace validation passed. Cached `python3 tools/work-status.py` ran at
start/handoff without fetch or mutation; the handoff scan may finish after
source commit and its exact result is reported to the coordinator.

## Remaining operator proof

After review the build owner must run
`nix build .#kernelMainlineBootTraceSbiTrialBootFiles --no-link --print-out-paths`,
inspect the matching bundle with `tools/mainline-drm-trial-inspect.py`, and
qualify the existing ordinary controller with a fresh exact manifest and
protected normal report. The operator must first verify normal reset recovery,
reserve board/UART, and use the existing `tools/mainline-drm-system-trial.py
begin --bundle <exact-built-bundle> --manifest <private-exact-manifest>
--normal-report <private-normal-report> --state <private-state> --log
<private-uart-log> --result <private-result>` flow.

The original three qualified ordinary-init controls and 180-second readiness
bound remain. Raw evidence stays private. Unknown/missing readiness sends no
commands or guessed reboot; another operator reset may be necessary. Later
source/driver diagnosis, real root/login, physical touch and protected return
remain separate gates, not conclusions from these host checks.

## Coordinator's outcome map for the next physical trial

This is a source-based interpretation plan, **not observed direct-SBI output**.
Use only complete fixed records after the fresh selected-kernel boot. Missing
or partial records remain unknown; a later record can establish progress even
when an earlier record was lost. Every case retains the ordinary identity/root
and physical-touch gates.

| Last direct point observed | What the source establishes | What remains unresolved |
| --- | --- | --- |
| None | No direct boundary observed. | Initcall completion, extension/output availability and progress. |
| `initcalls-before` | `do_initcalls()` reached its return. | That SBI call's return and the complete original initcalls-exit marker call. |
| `initcalls-after` | The original initcalls-exit marker helper returned. | This SBI call's return, the short do_basic_setup return and next emission. |
| `basic-before` | `do_basic_setup()` returned. | This SBI call's return and the complete basic-setup-exit marker helper. |
| `basic-after` | Both suspect printk marker helpers returned. | This SBI call's return and subsequent initramfs/root/init progress. |

The exact pre-SBI trace source has calls at `init/main.c:1486–1488` and
`1710–1718`; the actual config disables KUnit. A visible printk record still
does not prove printk returned: `8250_port.c:3493–3526` transmits bytes before
ownership reacquisition, transmitter-empty wait and IER restoration;
`nbcon.c:942–943` and `1644–1648` can retry ownership or pending flushes.
Emergency exit at `nbcon.c:1734–1757` can wake print threads and re-enable
preemption. These are source-supported possibilities, not observed causes.

If `initcalls-before` and legacy seq3 appear without `initcalls-after`, the
strongest separately reviewed follow-up is one gated/static direct-SBI point
immediately after `pr_info` and before emergency exit. That can show the printk
call returned. It adds an ECALL while preemption/emergency state is held,
extends that interval, shares UART/firmware and has no firmware deadline;
missing output remains inconclusive. It is **not implemented** here. Avoid
placing probes inside UART ownership/IER manipulation. An optional skip of only
the suspect diagnostic marker could test instrumentation dependence, but would
lose that marker and perturb sequencing; it is not a production fix. Neither
follow-up is a reason to change normal outputs or declare a root cause now.
