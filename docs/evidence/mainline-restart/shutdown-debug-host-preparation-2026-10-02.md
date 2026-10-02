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
pre-candidate U-Boot interception; the expectations were corrected without
changing that controller behavior. These tests remain host-only proof.
