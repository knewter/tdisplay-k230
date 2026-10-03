# Optional boot-boundary kernel — matching build proof

2026-10-03 UTC. Coordinator branch `integrate/mainline-probe-path`, worktree
`/home/jadams/tmp/k230-mainline-probe-integration`, source revision
`7e1e3a60d7ebf607a8312324ae890b97f089b3d1` (bounded build base).
Owned paths for this increment: this evidence directory and the existing
mainline change's task progress note. Root held `/tmp/k230-nix-build.lock`
for the matching full build and released it on completion. No board or UART
was used for these checks.

The full kernel/system/initrd/bundle build **passed**:

```sh
flock -n /tmp/k230-nix-build.lock nix build \
  .#kernelMainlineBootTraceTrialBootFiles --no-link --print-out-paths \
  --max-jobs 1 --cores 16
python3 tools/mainline-drm-trial-inspect.py \
  /nix/store/cr8bv4s6gbchfmcm14c0hrl8agh7zn62-k230-mainline-drm-trial-boot-files
```

The private build log is `~/tmp/k230-mainline-boot-trace-full-build.log`.
Exact matching artifact identities, hashes and results are in
[result.json](result.json). The inspector passed Image-to-system equality,
initrd payload/header/data CRC checks, DT-to-environment bootargs equality,
629-path inventory presence and SHA256SUMS. `nix-store -qR` includes the
bundle itself and reports 630 paths. An exclusive private gzip NAR export
contains eight new paths against the already staged five-clock bundle; its
103,870,216 bytes are transfer preparation, not board registration proof.

The built development output's actual `build/.config` has
`CONFIG_PRINTK=y`, `CONFIG_PRINTK_TIME=y`, `CONFIG_SERIAL_8250_CONSOLE=y`,
`CONFIG_SERIAL_EARLYCON_RISCV_SBI=y` and `# CONFIG_KUNIT is not set`.
The realized patched `init/main.c` equals the translation unit in the
[source/object proof](../boot-boundary-host-2026-10-03.md); the public marker
format is present in the linked Image. Device-tree decompilations are identical
to the proven five-clock baseline after removing `/chosen/bootargs`.

Both the existing `rd.prepare_trial(...)` and the actual ordinary controller's
`prepare(...)` passed against the exact new bundle, candidate file manifest
and protected normal report. The latter verified selected init/kernel/PID1
and executable diagnostic tools. It retains exactly one serial console,
exactly one `k230.boot_trace=1`, no earlycon/keep_bootcon/global clock bypass,
and the original three qualified fsck/root-growth/registration controls.
Preparation used the private `prepare-transfer.py` and
`host-prepare-ordinary.py` under `~/tmp/k230-mainline-boot-trace-board`;
these validate host artifacts and never open UART.

## Physical gate remains open

This is full build/artifact evidence, **not a physical boot**. Marker output,
ordinary root/login, panel power/display, deliberate glass touch and automatic
normal return remain **UNVERIFIED**. Task 5b.5 stays unchecked. The marker
semantics and flushing caveat in the source proof remain controlling: the last
visible enter does not establish a stack or root cause.

After reserving the board and checking protected normal identity, stage the
matching closure with its own GC root alongside the protected installation.
Run the unchanged ordinary controller once:

```sh
python3 tools/mainline-drm-system-trial.py begin \
  --bundle /nix/store/cr8bv4s6gbchfmcm14c0hrl8agh7zn62-k230-mainline-drm-trial-boot-files \
  --manifest <private-exact-manifest> --normal-report <private-normal-report> \
  --state <private-state> --log <private-uart-log> --result <private-result>
```

Its fresh banner/login/root gates and 180-second readiness deadline remain.
Unknown completion means stop input; a manual reset may be necessary. A ready
candidate still requires the independent real-glass `touch --real-touch` and
protected `finish` recovery checks. No proposal is archived by this increment.
