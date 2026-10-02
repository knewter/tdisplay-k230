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

The suite passes 71 tests, retaining all 62 base tests. New checks cover the
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
