# Same-image initramfs/initcall comparison — controller host proof

2026-10-03 UTC. Coordinator branch `integrate/mainline-probe-path`, base
`b27821af8f94325cdee18ea8a4679e443823e2e1`, worktree
`/home/jadams/tmp/k230-mainline-probe-integration`. Owned source is
`tools/mainline-drm-system-trial.py`, its focused tests, the narrow CI step,
this evidence note and the mainline task progress note. Root and independent
reviewer approved the corrected source. No board, UART, full build or transfer
was used for this increment. Current failed-candidate recovery is UNVERIFIED
until another confirmed operator reset and protected normal postflight.

## What the comparison changes

The [SBI-only physical attempt](boot-boundary-sbi-only-physical-2026-10-03/README.md)
reached `initramfs-wait-enter`, with no subsequent exit/login. The final SBI
call return and actual wait entry are unknown. Its visible external unpacking
printk is not completion proof.

Exact realized source
`/nix/store/26hzn5vin6b27cc4mpffc9fn5x8ikwqn-linux-mainline-k230-boot-trace-sbi-only-src/init/initramfs.c:603–608`
defaults `initramfs_async` true and accepts a bool parameter. At 789–798, the
rootfs initcall **always schedules the same async worker** and, when false,
waits for that domain/cookie before later initcalls continue. It does not run
the worker inline. `kernel/async.c:129,136–147,310–320` runs the worker, removes
the domain entry, wakes waiters and implements the untimed wait. main.c:1554–1555
emits `initcalls-exit` only after the initcall sequence returns. A fresh
complete post-initcalls record with this knob therefore proves the earlier
rootfs join returned, independently of that record's own final SBI return.

Begin-only `--wait-initramfs-in-initcall` adds exactly one volatile
`initramfs_async=0` token. Same built/staged Image, initrd, hardware DT,
wrapper, manifest, selected system/immutable init, sole serial console and
three original qualified controls remain selected. No saveenv, boot-file
rewrite, new kernel, mask or bypass is added. The selector requires exact
base/SBI-only flags and rejects duplicate, bare or contradictory values,
extra consoles, earlycon, keep_bootcon and the four-record variant's flag.
Any initramfs_async token already in the artifact is rejected to prevent
ambiguous comparisons. Default artifact behavior has the original command.

The typed boolean is saved in protected candidate-ready state and restored
for touch/finish; old states default false. CLI reselection on a resumed
phase is rejected before state/serial access. Actual `setenv` output and
subsequent candidate cmdline must match the new expected argument list. All
five loads/CRCs, identity/file/profile/service/mask checks, single bootm,
180-second passive readiness and unknown-no-input/retry behavior remain.

## Narrow proof

```sh
python3 -m unittest discover -s tests -p 'test_mainline_drm_system_trial.py'
python3 -m unittest discover -s tests -p 'test_mainline_drm*trial.py'
nix eval --offline --no-write-lock-file --raw \
  .#kernelMainlineBootTraceSbiOnlyTrialBootFiles.drvPath
openspec validate the-board-runs-a-mainline-kernel --strict
openspec validate --all
git diff --check
```

**29 focused tests passed**, independently repeated after a concrete review
correction to token-name checks. Added proof exercises actual volatile boot
command generation, five loads/five CRCs, missing printed argument stopping
before bootm, unknown post-boot readiness sending no further input, exact
missing/duplicate runtime-token rejection, saved-mode finish, malformed
saved mode before serial access, and actual CLI begin-only parsing. Expanded
fixtures reject six instrumentation names with bare/=0/=1/=false forms.
This is host/mock transport and fixture execution, not board proof.

The broader 207-trial-test suite passed before that token-name correction;
the corrected focused 29 suite was rerun. Existing ordinary flow and old
saved-state compatibility are covered by that suite. Selected bundle
derivation remains exactly
`/nix/store/gd9mwhg8hsmlrsic1bngg2m20rczvsf5-k230-mainline-drm-trial-boot-files.drv`;
there is no rebuild. Actual controller `prepare(...)` against
`/nix/store/brmp1qf9cz65yciazabc8yg5j39nn643-k230-mainline-drm-trial-boot-files`
passed in both modes using its exact manifest and last verified protected
normal baseline: system/kernel/PID1/manifest/helper/normal are identical,
bootargs differ only by the final token, and the actual volatile command
is 140 bytes, below 512. Private preparation record:
`~/tmp/k230-mainline-boot-trace-sbi-only-board/wait-initramfs-host-prepare.json`.
The 29-test command is also added to CI; published revision verification is
separate from a local pass.

## Interpretation and remaining physical gate

Success would establish dependence on overlap/order with subsequent
device/late initcalls; it would not identify a driver, clock, console or
production fix. Other threads/UMH/firmware waits can still run concurrently,
and worker printk/LSM/decompression/free/fput paths remain. Failure before
post-initcalls output cannot distinguish worker progress, scheduling,
firmware/output or earlier work. SysRq is disabled in the actual config;
detectors and trace-ring retrieval require execution/output progress and
are not a substitute for this discriminating comparison.

After protected reset recovery is verified, reserve board/UART and run:

```sh
python3 tools/mainline-drm-system-trial.py begin \
  --wait-initramfs-in-initcall \
  --bundle /nix/store/brmp1qf9cz65yciazabc8yg5j39nn643-k230-mainline-drm-trial-boot-files \
  --manifest ~/tmp/k230-mainline-initramfs-initcall-board/candidate-manifest.json \
  --normal-report ~/tmp/k230-mainline-initramfs-initcall-board/normal-report.json \
  --state ~/tmp/k230-mainline-initramfs-initcall-board/ordinary-state.json \
  --log ~/tmp/k230-mainline-initramfs-initcall-board/ordinary-uart.log \
  --result ~/tmp/k230-mainline-initramfs-initcall-board/ordinary-result.json
```

The already staged bundle/complete closure must pass the controller's
fresh persistent checks. Update the new protected report to the verified
reset boot ID first. Preserve the **whole** qualified boot phase: earlier
SBI records may precede the printed Linux banner. A ready candidate still
requires real glass `touch --real-touch` and protected `finish` postflight.
No ready/root/glass/automatic-return/production acceptance exists for this
new opt-in. Task 5b.5 remains unchecked; unknown completion sends no command
or guessed recovery. Operator reset may be needed again.
