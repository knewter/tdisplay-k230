# Fixed initrd manager logging: controller host proof

Prepared on 2026-10-05 UTC (final focused run after 02:19 UTC) in branch `mainline-initrd-debug-controller`, worktree
`~/tmp/k230-mainline-initrd-debug-controller`, based on
`c41217b59710ba6fc9093de97546ed39f25d88e1`. Owned paths are the ordinary trial
controller, its new focused test file, and this note. No board, UART or build
reservation was taken. This is task 5o.1 host preparation; actual artifact
qualification and physical capture are separate gates.

The begin-only `--initrd-debug-logging` selector requires both
`--wait-initramfs-in-initcall --without-boot-markers`. It adds exactly
`rd.systemd.log_level=debug rd.systemd.log_target=console`. The p2 policy fixture
changes 299 to 356 argument bytes and 317 to 374 literal U-Boot command bytes,
within the unchanged 512-byte bound. Invalid types, phases, parent selections,
inherited plain/initrd logging aliases and competing targets, masks, debug
shells, tracing, reporter, clock and timer controls fail before output creation
or UART opening. Saved selection is typed and restored for touch/finish; old
state without the field defaults false. Existing unselected arguments,
transport commands and preparation defaults remain unchanged.

The focused fixtures execute the actual pump with more than 131072 bytes of
split verbose output: the full private wire log is preserved while the rolling
buffer stays bounded. Stale login/prompt text cannot replace a fresh candidate
banner/login/prompt. Full transport fixtures verify five loads and five CRC
checks, exact printed arguments, saved-mode continuation and exact live command
line. Readiness/read errors and accepted boot writes with unknown flush results
produce no further candidate input. The current readiness and identity gates,
180-second bound and protected normal-return policy are unchanged.

Commands, run with `TMPDIR="$HOME/tmp"` and `PYTHONDONTWRITEBYTECODE=1`:

```sh
python3 -B tests/test_mainline_initrd_debug_logging.py
python3 -B tests/test_mainline_drm_system_trial.py
openspec validate the-board-runs-a-mainline-kernel --strict
git diff --check
```

Results: 13 focused tests passed in the final 0.621-second run and 36 existing
ordinary-controller tests passed in 1.088 seconds;
strict validation and whitespace checking passed. The focused test file uses
isolated temporary files, fake normal/candidate protocol responses and write
spies. Its p2 command-length fixture uses the public selected system identity;
it does not open UART or perform actual artifact preparation.

Source SHA256:

```text
602f0d591f09d29421692015f82383ad3dc1bbd18c0ae8e5c3c8662dfb02ce11  tools/mainline-drm-system-trial.py
1c0e7b8a799bfca90a5a5c520c98442374dcc1b07548430d179dbb73e588be70  tests/test_mainline_initrd_debug_logging.py
```

The coordinator's actual preparation API is
`prepare(bundle, manifest, normal_report, wait_initramfs_in_initcall=True, without_boot_markers=True, initrd_debug_logging=True)`.
Before physical use, that gate must qualify the same immutable artifacts and
protected normal anchors; a NEW protected recovery and exclusive operator
reservation remain required. Private output paths must be fresh. The bounded
operator invocation adds `--initrd-debug-logging` to the existing ordinary
`begin --wait-initramfs-in-initcall --without-boot-markers` command with its
reviewed bundle, manifest, normal report, state, log and result paths.

[The selected archive/source audit](../../../research/mainline-initrd-debug-logging-2026-10-05.md)
grounds these manager logging settings. They can expose service spawn/exec,
state transitions and completion; they do not trace silent closure-finder Bash
subcommands or establish a blocked syscall. Verbose output can change timing
or console pressure. A missing final line does not identify the last executed
instruction. This proof does not establish ordinary root/login, panel/glass,
candidate reboot or protected normal recovery. Task 5b.5 remains **UNVERIFIED**.
