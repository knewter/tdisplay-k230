# Optional SBI-only diagnostic marker mode — host proof

2026-10-03 UTC. Branch `mainline-boot-boundary-sbi-only`, base
`0d23bb890f891b69fb32d121bc3c4be08ad1d91c`, worktree
`/home/jadams/tmp/k230-mainline-boot-boundary-sbi-only`.
This is source/native/API/object/evaluation proof only. Complete matching
kernel/bundle build, actual SBI-only output, ordinary init/root/login,
automatic return and deliberate glass touch remain **UNVERIFIED**.
Normal recovery must be verified before any new physical trial. Task 5b.5
stays open. No board/UART/camera/full kernel build/staging was performed;
protected normal boot files/profile were not changed.

## Scope and observable limits

The previous four-record trial in
`docs/evidence/mainline-system-trial/boot-boundary-sbi-physical-2026-10-03/README.md`
reached all four direct points and original printk seq1–4, but no next marker
or login. Both suspect original marker calls were passed; the last direct
`basic-after` ECALL return remained unknown. The KUnit call is a no-op when
disabled (`include/kunit/test.h:402–408`), and the actual initramfs wait is
after the missing next marker. This does not establish a console deadlock,
an initramfs-wait stall or a kernel/driver cause.

The separate `kernelMainlineBootTraceSbiOnly` directly layers one patch on
`/nix/store/5k23sa4pbcs651vssp6ybifnr5qc1g9g-linux-mainline-k230-boot-trace-src`,
the ORIGINAL boot-trace source, not the four outer-record layer. Exact
`env.src` inspection verifies this order. Original `init/main.c` SHA-256:
`ce95e6b40b1cbdebff28f4f3434afb87a51e207cf4e7928588b820904e16520d`.
No twenty call sites, kernel operations or branches move. No original
optional output or normal driver/kernel logging is changed.

Only exact runtime `k230.boot_trace_sbi_only=1` selects the new helper path.
An absent/invalid/bare/empty new flag retains the original diagnostic helper,
including its printk/emergency path and 32-record cap. The original runtime
`k230.boot_trace=1` is still required. In selected direct mode there is no
`pr_info`, nbcon emergency operation, formatting, polling, retry or fallback.
Missing `CONFIG_RISCV_SBI`, unavailable runtime DBCN, null/unknown step, or
invalid record length emits no diagnostic fallback.

The constant table contains exactly enter/exit records for basic setup,
initcalls, initramfs wait, root console, init access, namespace, integrity
keys, async wait, initmem/readonly and init exec. Example:

```text
K230_BOOT_SBI_ONLY_V1 step=initramfs-wait-enter
```

Every public fixed record has leading/trailing CRLF in a 64-byte NUL-padded
array with 64-byte alignment. The bounded lookup scans at most twenty known
step names; `strnlen` bounds the record to its fixed field. Matched valid
attempts increment the existing sequence counter before exactly one
`sbi_debug_console_write()` call, with at most 32 attempts across all sites
including exec fallbacks. Zero/partial/error returns still consume that
attempt and never retry. Return count/error is deliberately discarded;
there is no transmitted full-return or output-success claim.

The table, helper, enable state and counter have regular lifetimes; only
option setup is `__init`. No VMAP_STACK formatting buffer or private text
is used. On 4KiB pages every aligned <64-byte field is page-contained,
even though the complete table spans pages. `arch/riscv/kernel/sbi.c:591–617`
uses vmalloc page conversion or kernel `__pa`, clamps page crossings, and
makes one ECALL. `asm/page.h:133–150` supplies kernel mapping conversion;
`sbi.c:691–694` establishes runtime DBCN availability. The one-call mode
uses the API directly, not the zero-progress retry loop in
`earlycon-riscv-sbi.c:30–37`.

A visible record proves an output point was reached, not that its ECALL
returned. A later distinct record proves progress past earlier calls, not
their return byte counts. `sbi_ecall.c:27–46` includes trace hooks and an
ECALL with no wall-clock deadline. Firmware or the shared physical UART can
still block, drop or interleave output; missing/partial records remain
unknown. Removing this diagnostic helper's printk/emergency work changes
flushing/preemption timing and is a discriminator, not a production fix.
Ordinary driver and kernel logging remains active and can independently
block. No reboot/hang-recovery guarantee is provided.

## Narrow checks

- `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -p test_mainline_boot_trace_sbi_only.py -v` — **11 passed**. Native GCC executes the actual new helper branch/table assembled with its unchanged original body, for SBI-enabled/disabled builds. Checks cover original absent/invalid-mode behavior/cap, runtime/config/availability gates, null/unknown safety, all twenty exact bytes/alignment, full/partial/zero/error single-call behavior, zero diagnostic printk/emergency calls, and a 100-attempt/32-limit exec fallback case. Requests are mock API inputs, not physical firmware output.
- `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -p 'test_mainline_boot_trace*.py' -v` — **28 passed**, including both unchanged earlier suites.
- `nix-instantiate --parse nix/kernel-mainline-boot-trace-sbi-only.nix` and `nix-instantiate --parse flake.nix` — **passed**.
- `patch --batch --fuzz=0 <scratch-main.c> nix/patches/mainline/k230-boot-trace-sbi-only.patch` against the exact source above — **passed**; result equals the C compiled below. Patch SHA-256: `deeb8326fc3c9f77f6e9dde7cb28d3cccf8c82ae5402266189e60aeadc10a891`.

The original installed dev headers/build config were copied privately from
`/nix/store/k9clwc0icv3xr6caplk2sp2s866875fj-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev/lib/modules/7.3.0-rc5/build`.
The immutable original was not changed. Config SHA-256:
`c5c128ed8b9701f78a0b8bd4f18dacd0d2407ae90eda79a35bba2d9f5ffbeae7`.
It enables 64BIT/RISCV_SBI/VMAP_STACK/PREEMPTION/4KiB pages; KUNIT is disabled.
A private external Kbuild directory contains the actual patched `main.c`
and `obj-y += main.o`.

```sh
make -C /nix/store/5k23sa4pbcs651vssp6ybifnr5qc1g9g-linux-mainline-k230-boot-trace-src \
  O=/home/jadams/tmp/k230-boot-trace-sbi-only-object/build \
  M=/home/jadams/tmp/k230-boot-trace-sbi-only-object/module ARCH=riscv \
  CROSS_COMPILE=/nix/store/4j2mwxqjvnyr6da0925sp0bm4jaj5r5i-riscv64-unknown-linux-gnu-gcc-wrapper-15.3.0/bin/riscv64-unknown-linux-gnu- \
  W=1 main.o
```

**Passed**, actual ELF64 little-endian RISC-V relocatable object, no MODULE
define or full kernel link/run. `readelf -sW/-SW` places the helper in
`.text.unlikely`, state in `.sbss`, only setup in `.init.text`, and the
2560-byte table at `.rodata` offset 0x740 with section alignment 64.
An actual ELF-byte inspection verifies all twenty record fields at
`0x740 + 64 + 128*i`, exactly matching public messages followed by NUL
padding, aligned and <64 bytes/page-contained. Thus the real RISC-V ABI
member offset/stride agrees with native layout, not merely an inferred
struct layout. `sbi_debug_console_write` remains a final-link reference.
Patched C SHA-256: `b776bb9707168ed2a26e393bcdd45808e132e661f1083662640268d856f028b9`.
Object SHA-256: `daea3dc299e9beb50f24cc758fcbfda4e3e1a5dc8f6588cdab46649b4e63042b`.

## Optional identities and evaluation

The new system inherits ORIGINAL serial-only ordinary trace parameters,
replaces only the selected kernel/list, and adds exactly the new opt-in.
There is no four-record flag, earlycon/keep_bootcon, clock bypass, observer
unit or console registration. Uname remains `7.3.0-rc5`. Evaluated params:

```text
consoleblank=0 console=ttyS0,115200n8 root=fstab loglevel=4
lsm=landlock,yama,bpf loglevel=7 k230.boot_trace=1 k230.boot_trace_sbi_only=1
```

Evaluated derivations, not built outputs:

- kernel: `/nix/store/gmd1k7x7y12wg3w4qn2r1cblisa8lwf4-linux-riscv64-unknown-linux-gnu-7.3.0-rc5.drv`
- source: `/nix/store/dy5gqz0nqydnay9w9wj6xhhp6hhywv3h-linux-mainline-k230-boot-trace-sbi-only-src.drv`
- system: `/nix/store/i5lbvwghhrira4sf05z6xa0v9rgcfad1-nixos-system-nixos-26.11.20260919.20b1ddd.drv`
- bundle: `/nix/store/gd9mwhg8hsmlrsic1bngg2m20rczvsf5-k230-mainline-drm-trial-boot-files.drv`

```sh
nix eval --offline --no-write-lock-file --json --impure --expr '
  let f = builtins.getFlake (toString /home/jadams/tmp/k230-mainline-boot-boundary-sbi-only);
      p = f.packages.x86_64-linux;
      c = f.nixosConfigurations.k230-mainline-boot-trace-sbi-only.config;
  in assert p.kernelMainlineBootTraceSbiOnly.drvPath == c.boot.kernelPackages.kernel.drvPath; {
    kernel = p.kernelMainlineBootTraceSbiOnly.drvPath;
    source = p.kernelMainlineBootTraceSbiOnly.src.drvPath;
    system = c.system.build.toplevel.drvPath;
    bundle = p.kernelMainlineBootTraceSbiOnlyTrialBootFiles.drvPath;
    params = c.boot.kernelParams;
    uname = c.boot.kernelPackages.kernel.version;
  }'
nix derivation show /nix/store/dy5gqz0nqydnay9w9wj6xhhp6hhywv3h-linux-mainline-k230-boot-trace-sbi-only-src.drv
nix eval --offline --no-write-lock-file --json --impure --expr '
  let old = builtins.getFlake "git+file:///home/jadams/tmp/k230-mainline-boot-boundary-sbi-only?rev=0d23bb890f891b69fb32d121bc3c4be08ad1d91c";
      new = builtins.getFlake (toString /home/jadams/tmp/k230-mainline-boot-boundary-sbi-only);
      names = [ "kernel" "kernelMainline" "kernelMainlineDrm"
        "kernelMainlineDrmTrialBootFiles" "kernelMainlineUartObserverBootFiles"
        "kernelMainlineBootTrace" "kernelMainlineBootTraceTrialBootFiles"
        "kernelMainlineBootTraceSbi" "kernelMainlineBootTraceSbiTrialBootFiles"
        "toplevel" "toplevel-mainline-console" "toplevel-mainline-drm-trial"
        "toplevel-mainline-uart-observer" "toplevel-mainline-boot-trace"
        "toplevel-mainline-boot-trace-sbi" ];
      paths = f: builtins.listToAttrs (map (name: {
        inherit name; value = f.packages.x86_64-linux.${name}.drvPath;
      }) names);
  in assert paths old == paths new; { before = paths old; after = paths new; }'
```

All evaluations/source-order checks passed. All fifteen existing identities
are equal to base, including both original optional trace variants.
Evaluation performed no realization/full kernel build. Strict OpenSpec/all
56 and whitespace checks passed. Cached work-status ran at start/handoff;
any slow pending handoff result is reported separately without holding the
ready source commit.

## Remaining operator gates

After review, the build owner runs
`nix build .#kernelMainlineBootTraceSbiOnlyTrialBootFiles --no-link --print-out-paths`,
inspects the exact bundle with `tools/mainline-drm-trial-inspect.py`, verifies
matching source/Image/initrd/DT/config/sole init, and prepares a fresh exact
manifest/normal report for the existing controller. No controller changes
or artifact-identity guard bypasses are included.

Only after verified protected normal recovery and board/UART reservation:
`python3 tools/mainline-drm-system-trial.py begin --bundle <exact-built-bundle>
--manifest <private-exact-manifest> --normal-report <private-normal-report>
--state <private-state> --log <private-uart-log> --result <private-result>`.
The original three qualified ordinary-init controls and 180-second readiness
bound stay in force. Preserve raw private evidence; unknown readiness sends
no command or guessed reboot. Firmware call-return remains ambiguous at the
last visible direct record; operator reset/power recovery may be necessary.
No ordinary root, glass touch, unmasked production or automatic recovery
claim follows from this host increment.
