# Optional mainline boot-boundary markers — host proof

2026-10-03 UTC. Branch `mainline-boot-boundary-trace`, base
`6e4a82f9f965fb4125edb819efbe3a53136d381b`, worktree
`/home/jadams/tmp/k230-mainline-boot-boundary`.

This is host source/API/object/evaluation evidence. Complete kernel build,
artifact inspection, marker output, ordinary init/root/login, automatic return
and deliberate glass touch are **UNVERIFIED**. Task 5b.5 remains open.
No board, UART, cross-kernel build or protected card operation was performed.

## Scope and source

The optional `kernelMainlineBootTrace` applies only
`nix/patches/mainline/k230-boot-trace.patch` to the already assembled DRM,
restart and five-clock SD1 source. Derivation inspection confirms its input is
`/nix/store/l0j3rf11mr65wl5x88a9zzma45ciz687-linux-mainline-k230-drm-src`;
upstream pin remains `72d3fcf802c45d00b300f25b848a93c3a2bd7c7e`.
Unpatched `init/main.c` SHA-256 is
`e020a85da2661817a61a4d15dff0e482ecdd687f0f77d24b2bd74987a6851414`.

The new `k230-mainline-boot-trace` system and
`kernelMainlineBootTraceTrialBootFiles` reuse the ordinary DRM trial builder.
They remove exactly `console=tty0` and append `k230.boot_trace=1`, preserving
`console=ttyS0,115200n8`, the existing root/logging controls and matching sole
system init. No earlycon, keep_bootcon, clock bypass, observer unit or debug
shell is added. Existing kernel/system/console/observer outputs and controllers
are unchanged. The ordinary trial controller supplies its existing qualified
fsck/root-growth/registration controls; these are not production acceptance.

The marker helper and counter/enable flag have regular lifetimes. Only the
boot option parser is `__init`. `include/linux/console.h:606–607` declares the
emergency API (disabled-PRINTK stubs at 670–671). Each enabled call enters
nbcon emergency state, emits one public `pr_info`, then exits. No blocking
operation is inside that interval. `kernel/printk/nbcon.c:1709–1758` documents
the emergency behavior; it can change flushing and scheduling. A marker can
itself block or fail to become visible. This is instrumentation, not a fix or
an autonomous hang-recovery mechanism.

There are 20 fixed sites, ten enter/exit pairs: basic setup, initcalls,
initramfs wait, root-console open, init accessibility, namespace preparation,
integrity keys, async synchronization, initmem/readonly cleanup and init exec.
Namespace markers appear only on the original failed-init-access branch;
init exec can repeat on original fallback paths. At most 32 records are
emitted, with `K230_BOOT_TRACE_V1 seq=N step=<fixed label>`. The original
kernel operations, branches and exec return values remain in order.

An enter-only observation identifies the last visible boundary, not a stack
or a root cause. A pair completed only proves that bracketed call returned.
Even init-exec-exit does not prove userspace readiness. Work before the first
basic-setup marker is not covered. The KUnit call sits between
basic-setup-exit and initramfs-wait-enter; the prepared configuration used for
the object check has `# CONFIG_KUNIT is not set`. Recheck the actual built
configuration before interpreting that gap. No raw bootargs, pointers,
private log contents or counter dumps are emitted.

## Narrow commands and results

- `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -p test_mainline_boot_trace.py -v` — **7 passed**. Native GCC compiles the actual helper extracted from the patch with mocked printk/emergency calls. Tests execute disabled, invalid/bare/empty and exact enabled flag behavior, balanced one-print emergency intervals, exact fixed labels and a 100-attempt/32-record cap. The registration-prefix test is not a full Linux command-line parser test.
- `nix-instantiate --parse nix/kernel-mainline-boot-trace.nix` and `nix-instantiate --parse flake.nix` — **passed**.
- `openspec validate the-board-runs-a-mainline-kernel --strict` and `openspec validate --all` — **passed**, 56 items in the latter. `git diff --check` and staged whitespace check passed. Cached `python3 tools/work-status.py` ran at start and handoff; it performs no fetch or worktree mutation.
- `patch --batch --fuzz=0 <scratch-main.c> nix/patches/mainline/k230-boot-trace.patch` against an exact copy of restored `init/main.c` — **passed**. The zero-context patch avoids committing whitespace-bearing context lines; the resulting C bytes equal those compiled below. Patch SHA-256: `061a6662c06e5da53fba1c2e5e8b96240d1be6baacfd49a231f4481c745afab8`.

The real patched object was built using a private copy of already prepared
headers/configuration from
`/home/jadams/tmp/k230-mainline-restart/.scratch/mainline-restart-object/run.CuXzA8/build`.
The original prepared tree was not changed. The source was the restored exact
`l0j3…` tree; a scratch external Kbuild directory contained the patched
`main.c` and `obj-y += main.o` (no `MODULE` define).

```sh
make -C /nix/store/l0j3rf11mr65wl5x88a9zzma45ciz687-linux-mainline-k230-drm-src \
  O=/home/jadams/tmp/k230-boot-trace-object/build \
  M=/home/jadams/tmp/k230-boot-trace-object/module ARCH=riscv \
  CROSS_COMPILE=/nix/store/4j2mwxqjvnyr6da0925sp0bm4jaj5r5i-riscv64-unknown-linux-gnu-gcc-wrapper-15.3.0/bin/riscv64-unknown-linux-gnu- \
  W=1 main.o
```

**Passed**, ELF64 little-endian RISC-V relocatable object. `readelf -sW/-SW`
places `k230_boot_trace_mark` in `.text.unlikely`, both state variables in
`.sbss`, and only `k230_boot_trace_setup` in `.init.text`. Both emergency APIs
remain resolved-at-link references. No full kernel link or execution occurred.
Initial `LLVM=1` attempt failed because the cached GCC configuration supplied
Clang-unsupported `-fmin-function-alignment=8` and `-fconserve-stack`; the
matching GCC 15.3 check above then passed. Prepared config SHA-256:
`40fee52e7dc0d13cc9cd98c51925da55f99c0a4a85c74b390715c264d88cf758`.
Patched C: `ce95e6b40b1cbdebff28f4f3434afb87a51e207cf4e7928588b820904e16520d`.
Object: `028eba4643b06e3a972e928a7ee732591191824035f086babfe969bf990cf45e`.
This checks this translation unit against prepared headers, not the final
Nix kernel configuration/link.

Offline `nix eval --offline --no-write-lock-file --json --impure` evaluated
`.packages.x86_64-linux` and the optional system. It confirmed uname
`7.3.0-rc5`, selected system kernel equals the optional kernel, and params:

```text
consoleblank=0 console=ttyS0,115200n8 root=fstab loglevel=4
lsm=landlock,yama,bpf loglevel=7 k230.boot_trace=1
```

Evaluated derivations (not built outputs):

- kernel: `/nix/store/0pigagzwxzpk8wvk4ww4dhp90hdmsriy-linux-riscv64-unknown-linux-gnu-7.3.0-rc5.drv`
- source: `/nix/store/cj04yq9adb0647rla5gxa142pcp9v602-linux-mainline-k230-boot-trace-src.drv`
- system: `/nix/store/w7s9xm888bqzh64j8m3cvb221n2pwcjk-nixos-system-nixos-26.11.20260919.20b1ddd.drv`
- bundle: `/nix/store/5rj49f4z0k110zwpkfxj2jm4s542mk72-k230-mainline-drm-trial-boot-files.drv`

The same offline expression compared drvPaths with
`builtins.getFlake "git+file:///home/jadams/tmp/k230-mainline-boot-boundary?rev=6e4a82f9f965fb4125edb819efbe3a53136d381b"`.
All nine existing package identities are equal: `kernel`, `kernelMainline`,
`kernelMainlineDrm`, `kernelMainlineDrmTrialBootFiles`,
`kernelMainlineUartObserverBootFiles`, `toplevel`, `toplevel-mainline-console`,
`toplevel-mainline-drm-trial`, `toplevel-mainline-uart-observer`.
Evaluation invoked no source realization or kernel build.

Reproducible evaluation commands (run from this worktree; no build):

```sh
nix eval --offline --no-write-lock-file --json --impure --expr '
  let f = builtins.getFlake (toString /home/jadams/tmp/k230-mainline-boot-boundary);
      p = f.packages.x86_64-linux;
      c = f.nixosConfigurations.k230-mainline-boot-trace.config;
  in assert p.kernelMainlineBootTrace.drvPath == c.boot.kernelPackages.kernel.drvPath; {
    kernel = p.kernelMainlineBootTrace.drvPath;
    source = p.kernelMainlineBootTrace.src.drvPath;
    system = c.system.build.toplevel.drvPath;
    bundle = p.kernelMainlineBootTraceTrialBootFiles.drvPath;
    params = c.boot.kernelParams;
    uname = c.boot.kernelPackages.kernel.version;
  }'
nix eval --offline --no-write-lock-file --json --impure --expr '
  let old = builtins.getFlake "git+file:///home/jadams/tmp/k230-mainline-boot-boundary?rev=6e4a82f9f965fb4125edb819efbe3a53136d381b";
      new = builtins.getFlake (toString /home/jadams/tmp/k230-mainline-boot-boundary);
      names = [ "kernel" "kernelMainline" "kernelMainlineDrm"
        "kernelMainlineDrmTrialBootFiles" "kernelMainlineUartObserverBootFiles"
        "toplevel" "toplevel-mainline-console" "toplevel-mainline-drm-trial"
        "toplevel-mainline-uart-observer" ];
      paths = f: builtins.listToAttrs (map (name: {
        inherit name; value = f.packages.x86_64-linux.${name}.drvPath;
      }) names);
  in assert paths old == paths new; { before = paths old; after = paths new; }'
nix derivation show /nix/store/cj04yq9adb0647rla5gxa142pcp9v602-linux-mainline-k230-boot-trace-src.drv
```

The last command exposes the final patch derivation's `env.src` for the exact
DRM source input check. The evaluated new config path is
`/nix/store/c55hagx8ss9vkpgfzpc24k2jb8qnqg8q-linux-config-riscv64-unknown-linux-gnu-7.3.0-rc5`;
it has not been realized by this work, so the final built KUnit/configuration
check remains with the build owner.

## Remaining operator gate

After review, the build-slot owner must build
`nix build .#kernelMainlineBootTraceTrialBootFiles --no-link --print-out-paths`,
inspect the exact resulting bundle with `tools/mainline-drm-trial-inspect.py`,
verify matching Image/system/initrd/DT bootargs and configuration, and create
its exact controller manifest/protected normal report. Physical use remains
operator-only, with a reserved board/UART and protected staging/preflight.

The existing ordinary controller command is:

```sh
python3 tools/mainline-drm-system-trial.py begin --bundle <exact-built-bundle> \
  --manifest <private-exact-manifest> --normal-report <private-normal-report> \
  --state <private-state> --log <private-uart-log> --result <private-result>
```

Keep the original 180-second readiness bound and fail-closed candidate/root
checks. No prompt/receipt means no further input or guessed reboot. Preserve
raw private output, report the last complete marker and any unknown boundary;
operator reset recovery may still be required. If readiness returns, root and
real glass touch still need their existing independent checks and protected
normal postflight. No task is completed by this host increment.
