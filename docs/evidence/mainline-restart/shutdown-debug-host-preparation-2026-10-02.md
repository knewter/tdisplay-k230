# Shutdown debug preparation — host only

Prepared on `2026-10-02`, starting from reviewed integration revision
`47a1157e`, in `/home/jadams/tmp/k230-mainline-restart` on
`mainline-restart-port`. This changes the controller, its host tests, this note,
and an append-only 5d.4 preparation note. No kernel build or board operation
was performed. Automatic restart and usable mainline root remain **UNVERIFIED**.

The existing exact candidate remains kernel
`/nix/store/4wkhxf55y1abg1kg2xd0acsfjqr64j0h-linux-riscv64-unknown-linux-gnu-7.3.0-rc5`,
bundle `/nix/store/asj7l4zj5jrjkgng4nrcx3y72p7jf7aa-k230-mainline-drm-trial-boot-files`,
and matching system
`/nix/store/v9qc1sf0iz53s3x6g6vwfyaxghkfpnyk-nixos-system-nixos-26.11.20260919.20b1ddd`.
Artifact byte counts/hashes, matching init, protected normal checks, and
persistent boot selection rules are preserved.

`--debug-shutdown` is an explicit minimal-only discriminator. It appends
`initcall_debug loglevel=8` after `rdinit=/bin/sh` to volatile U-Boot bootargs
and requires the complete printed value to match exactly before booting.
Existing bundle loglevels 4/7 are retained; the final 8 takes precedence.
Existing initcall/debug/quiet/dynamic-debug arguments, preexisting loglevel 8,
and malformed loglevels are rejected before serial or board access. Other
modes reject this flag; the clock discriminator remains label-only.

The corrected candidate source
`/nix/store/jvz4v73g8a67pqwm06v079h6s1cpqr9s-linux-mainline-k230-drm-src`
is based on Linux `72d3fcf802c45d00b300f25b848a93c3a2bd7c7e` plus the optional
restart patch. `init/main.c:794–795` exposes `initcall_debug`; the installed
System.map contains its parameter. `drivers/base/core.c:4917–4929` prints
per-device shutdown entry messages when enabled, and
`drivers/base/syscore.c:125–128` prints syscore callback symbols. The installed
config has PRINTK, KALLSYMS, DYNAMIC_DEBUG and DYNAMIC_DEBUG_CORE enabled;
MAGIC_SYSRQ is unset. No dynamic-debug query is added by this discriminator.

These messages are entry checkpoints. Probe waits and cpufreq suspend precede
the first device message; device/parent locks and runtime-PM barriers also
precede each message. The last printed device is therefore a useful boundary,
not proof that its shutdown callback is the cause. No print site in the K230
restart callback proves invocation. The previous [dispatch audit](restart-dispatch-audit-2026-10-02.md)
explains why userspace `Rebooting.` and the pretrial normal kernel announcement
do not establish candidate dispatch.

Verbose output exposed a host-controller bug: its 128 KiB rolling buffer used
a fixed recovery offset, which could hide all new recovery text once full.
The controller now clears the parsed buffer immediately before the candidate
reboot request, retaining the complete private UART log, and scans that fresh
rolling phase. It checks already-received output before reading again and
requires a normal login prompt at a line boundary. Old pretrial markers and
echoed login/refusal text do not satisfy recovery.

Host proof commands, run at approximately `2026-10-02T17:30Z` and repeated
after the final prompt-parser adjustment:

```sh
python3 -m unittest discover -s tests -p test_mainline_drm_initrd_shell_trial.py -q
openspec validate the-board-runs-a-mainline-kernel --strict
git diff --check
```

The initial suite passed 71 tests, retaining all 62 base tests. New checks cover the
mode/conflict gates, exact printed debug bootargs before candidate boot,
explicit result selection, and the actual capped serial pump with more than
128 KiB of simulated output. They include split fresh login/refusal markers,
pretrial markers, echoed text, and a login already received alongside the
reboot receipt. These are host simulations, not physical recovery proof.

After review/landing, the sole board operator can use the same inspected bundle
with a fresh protected normal report and matching private manifest. This is a
documented next command, not an executed board trial:

```sh
python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal --debug-shutdown \
  --bundle /nix/store/asj7l4zj5jrjkgng4nrcx3y72p7jf7aa-k230-mainline-drm-trial-boot-files \
  --manifest "$HOME/tmp/k230-mainline-restart-board/candidate-manifest.json" \
  --normal-report "$HOME/tmp/k230-mainline-restart-board/normal-report.json" \
  --log "$HOME/tmp/k230-mainline-restart-board/shutdown-debug-uart.log" \
  --result "$HOME/tmp/k230-mainline-restart-board/shutdown-debug-result.json"
```

The controller still requires exclusive board ownership, live normal preflight,
bounded probe stages, and protected normal postflight. The operator retains
recovery ownership if automatic return fails. Task 5d.4 stays unchecked until
its named automatic restart proof exists; task 5b.5 stays open separately.

## Follow-up: bounded initrd readiness and unknown results

Prepared from `f463e88d` after the first debug attempt, at approximately
`2026-10-02T17:52Z`. Only the controller, its tests and this host note changed.
This follow-up performed no board input or build.

For `--debug-shutdown`, the controller now waits read-only for up to 90 seconds
before sending reception attempts. It requires an anchored kernel banner for
the pinned `7.3.0-rc5` candidate and, within that candidate phase, the complete
timestamped kernel line `Run /bin/sh as init process`. Pretrial normal text,
command echoes, another init path, and incomplete lines do not satisfy the
gate. The phase remains valid when the verbose trace rolls the banner out of
the capped parsed buffer. The private raw log remains complete.

Pinned `init/main.c:1472–1484` prints this entry checkpoint immediately before
`kernel_execve`; lines 1590–1595 use that path for the selected `rdinit`.
It does not prove successful exec or shell reception. After this checkpoint,
the original bounded fresh-token receipt protocol provides reception proof.
The ordinary minimal path retains its existing reception timing.

Minimal readiness or protocol errors now write a mode-0600 structured result
with schema `mainline-initrd-minimal-unknown-v1`, the failed stage, unknown
recovery, no observed reboot receipt, and unchanged persistent selection. A
debug result also records whether the readiness checkpoint was observed. The
controller closes without sending more probe input, `exit`, or candidate
reboot. Subsequent recovery remains the board operator's responsibility.

The original operator-owned private debug capture was 130,995 bytes, below the
128 KiB parsed-buffer cap, and contained no shell-init entry or reception
receipt. Approximately 99,964 bytes followed the candidate banner; 83,568 were
initcall trace. At 115200 8N1, that candidate volume alone represents about
8.7 seconds of UART transmission. Reception previously began immediately at
the early banner with eight nominal one-second attempts. All 624 observed
initcall entries had matching returns; the final observed return was at kernel
uptime 4.036685. No panic/Oops/BUG trace was observed. These facts expose a
premature-readiness risk but do not identify the physical stop's cause.

The coordinator subsequently reported zero new bytes in 15- and 90-second
passive captures and a panel still showing boot text. The physical state
therefore remains unknown; this note does not claim that longer readiness
would have completed that boot. Operator recovery/postflight is separate from
these host changes. See the coordinator's committed [physical debug evidence](physical-shutdown-debug-2026-10-02/README.md)
at `6533f27a`; this private capture is not copied.

One safe kernel diagnostic in the original capture reported the
`91101000.reset-controller` probe with `k230-rst` returned 0. Because the pinned
probe returns the managed restart registration result, this supports successful
registration in that boot. It does not show callback execution or automatic
reset, and does not close task 5d.4.

The same narrow unittest command above passes 76 tests after this follow-up;
strict change validation and `git diff --check` pass. New real-pump simulations
cover more than 128 KiB and more than eight virtual seconds of boot trace with
no premature input, followed by readiness and the minimal protocol. They also
cover stale/echoed/incomplete entry text, an entry already read with its banner,
and structured minimal readiness/reception failures with no later board input.
The first new run had two fixture assertions omit the existing Ctrl-C byte in
pre-candidate normal-prompt preparation; the expectations were corrected without
changing that controller behavior. These tests remain host-only proof.

## Follow-up: runtime shutdown tracing, host preparation only

Prepared from integration base `0ae69369` at approximately
`2026-10-02T18:12Z`, after reviewing the exact path and boolean semantics in
[the source feasibility note](runtime-shutdown-trace-feasibility-2026-10-02.md).
Only this note, the controller and its tests changed. No board operation or
kernel/bundle build was performed; physical runtime availability, tracing and
restart remain **UNVERIFIED**.

The explicit `--runtime-shutdown-trace` flag is minimal-only and excludes the
boot-debug and label-clock flags. It preserves ordinary matching bootargs:
there is no boot-time `initcall_debug` or appended `loglevel=8`. Existing
debug/quiet/dynamic-debug arguments or loglevel 8 are rejected before serial
access. The exact kernel, bundle, init, artifact checks and normal protection
remain those recorded above.

Only after fresh reception, true, proc setup and uptime gates pass does the
controller send six separate bounded stages, each with its own fresh nonce:

1. Create `/sys` and preserve mkdir status.
2. Inspect `/proc/mounts`. Require exactly one sysfs entry at `/sys`; reject
   another filesystem or duplicates. If absent, mount sysfs exactly once with
   `nosuid,nodev,noexec`, then verify the mount table again. Redirection and
   mount errors remain failures; a nonmatching final row does not hide status.
3. Require the exact `/sys/module/kernel/parameters/initcall_debug` file to be
   regular, readable and writable.
4. Require a complete prior `N` value, rejecting missing newline/extra lines.
5. Write `1` through the supported sysfs bool setter and preserve its status.
6. Independently require a complete `Y` readback.

Each marked stage has a positive finite deadline of at most 20 seconds.
Generated commands are 331–1005 bytes. Only successful returned status and
expected-value matching at every stage permit the existing single reboot
command and bounded protected normal-return checks. No full init activation,
root mount, repair, unbind or persistent boot-selection write is added.

Known failures preserve their RC/match and skip all remaining input. Missing,
stale, duplicated, truncated, inconsistent or malformed markers preserve a
structured unknown result with completed gates and stop further input. There
is no retry, rollback, Ctrl-C, exit or reboot after an unsafe runtime stage.
The `enable_verified` field becomes true only after `Y` readback. Parameter
state is `N` only after the prior gate; it becomes `UNVERIFIED` before the write
and stays so after a failed/unknown write or readback, even if write acknowledgment
was received. Raw parameter contents and mount-table rows are not published.
Stderr redirection does not establish that `/dev/null` is a device node.

The narrow unittest command above passes 87 tests, retaining all 76 prior
tests; strict OpenSpec validation and cached diff checks pass. Coverage includes
the full ordered protocol, every stage's known failure and timeout, freshness
and parser failure cases, no premature toggle/reboot, result selection and
partial write acknowledgment with unverified state. Generated shell is also
executed under bash and sh with **all** target paths, `/bin/mount` and
`/bin/mkdir` replaced by isolated `~/tmp` fixtures/stubs. Those checks cover
absent/existing/duplicate/wrong mounts, failed redirection and utility status,
exact bool reads, permission gates and write syntax. No host sysfs, real mount
or debug state is changed. An initial new prerequisite fixture changed both
mkdir and mount RCs; it was corrected to inject the intended mount failure.
These remain host simulations, not physical parameter or recovery proof.

After review/landing and independently verified protected normal recovery, the
sole operator may use fresh private paths for this next bounded trial:

```sh
python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal --runtime-shutdown-trace \
  --bundle /nix/store/asj7l4zj5jrjkgng4nrcx3y72p7jf7aa-k230-mainline-drm-trial-boot-files \
  --manifest "$HOME/tmp/k230-mainline-restart-board/candidate-manifest.json" \
  --normal-report "$HOME/tmp/k230-mainline-restart-board/normal-report.json" \
  --log "$HOME/tmp/k230-mainline-restart-board/runtime-trace-uart.log" \
  --result "$HOME/tmp/k230-mainline-restart-board/runtime-trace-result.json"
```

This command is documented, not performed by this work. A returned parameter
toggle would prove the runtime gate only. Shutdown messages remain entry
checkpoints, and automatic restart still requires the separate real reset,
fresh normal boot and protected postflight proof in task 5d.4. That task and
the usable-root/touch gate 5b.5 stay open.


## All-mode passive shell readiness follow-up (2026-10-02 18:51 UTC)

Host source/test work uses branch `mainline-all-readiness`, worktree
`/home/jadams/tmp/k230-mainline-all-readiness`, base
`6c03cc496fe8f74d1222099280fe0de458d8b05e`. No serial, board input, kernel build
or physical recovery was performed by this work. Automatic restart and usable
mainline root remain **UNVERIFIED**; tasks 5d.4 and 5b.5 remain open.

The ordinary controller path previously began its bounded receipt attempts
immediately after the Linux version banner; only `--debug-shutdown` waited
for init entry. The later runtime trial reached shell entry but returned no
fresh executed receipt. Receipt command echoes and a continuation prompt are
not reception proof. See the coordinator's separate physical evidence and
[source UART audit](../../research/mainline-uart-readiness-2026-10-02.md).
That source audit grounds the timing risk, not the exact physical cause.

The exact candidate source above opens `/dev/console` after basic setup and
initramfs completion (`init/main.c:1632–1645,1677–1680`). It prints
`Run /bin/sh as init process` **before** `kernel_execve` (`1472–1484`). Serial
startup applies console termios (`drivers/tty/serial/serial_core.c:304–336`)
and clears FIFOs (`drivers/tty/serial/8250/8250_port.c:2325–2331`). Thus the
kernel banner and init entry alone do not establish shell command reception.

Every rdinit diagnostic mode now performs the same read-only wait, bounded
at 90 seconds, before the first receipt attempt. It requires the fresh exact
candidate banner, the complete timestamped `/bin/sh` init-entry line, then
an initial `sh-<major>.<minor># ` prompt at the end of the current output.
The selected initrd's observed prompt is `sh-5.3# `. Multiline anchoring admits
the observed two shell warning lines before that prompt; split serial reads
are retained. Pre-entry prompts, echoed/incomplete entry lines, incomplete
prompts and continuation `> ` prompts cannot satisfy the gate. An old primary
prompt followed by command text or a continuation cannot satisfy it either.
Candidate/init phase state survives the rolling 128 KiB cap; raw logs remain
untouched. The prompt is a scheduling gate; only a fresh executed receipt
permits the existing true/proc/uptime and later diagnostic stages.

All modes record `initrd_readiness_observed`. A readiness or protocol timeout
preserves a structured recovery-required unknown result, now including survey,
and sends no additional probe, shell repair, reboot or recovery input. Exact
bootargs, artifact counts/hashes, matching init and normal protection are
preserved. Runtime tracing still uses ordinary bootargs and its existing
separate sysfs gates; this change does not enable boot-time debug output.

At 2026-10-02 18:51 UTC the narrow command
`python3 -m unittest discover -s tests -p test_mainline_drm_initrd_shell_trial.py -q`
passed **92 tests** (11.334 seconds), retaining all 87 previous tests. The
real capped serial pump and production orchestration are exercised for
ordinary minimal, runtime tracing, boot-time debug, label with/without the
clock flag, root-mount and survey. Each waits through more than eight seconds
and 128 KiB of boot output before its first receipt; each readiness timeout
records unknown with zero candidate input. Fresh receipt followed by nonzero
true stops every mode before further children, trace toggles or reboot.
Additional tests cover warnings, split prompts, post-entry cap rollover and
false prompt/entry matches. Initial new fixture failures (synthetic U-Boot
prompt, reused private log paths and a missing receipt newline after PS1)
were corrected; they were not hardware failures or passes. Strict OpenSpec
validation and `git diff --check` also pass. Cached work-status was run at
start and launched again for handoff.

After review/landing and independently verified protected normal recovery,
the sole operator may use the same explicit runtime-trace command above with
fresh protected log/result paths. A new receipt pass would apply only to that
trial; missing readiness remains unknown. No task checkbox or published
capability acceptance is changed by these host tests.
