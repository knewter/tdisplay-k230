# Optional UART-only console comparison: host preparation

Worktree `~/tmp/k230-mainline-uart-observer-serial-console`, branch
`mainline-uart-observer-serial-console`, base
`667d45388ee1b5599278fdeb18e36528473a6b74`. Only the observer controller, its
tests and this note are owned. No board/UART, build, helper/Nix, card or profile
change was performed. This remains a bounded diagnostic within mainline 5b.5.

The [READY-only physical observation](../mainline-system-trial/uart-observer-physical-2026-10-03/README.md)
does not prove the helper's kernel-log write returned. A synchronous legacy
console flush after UART output is a source-supported hypothesis, not a proven
cause or proof of fbcon involvement. This option isolates the volatile console
selection without changing the built helper, kernel, initrd or hardware DT.

`--serial-console-only` requires exactly one `console=tty0`, exactly one
`console=ttyS0,115200n8` and exactly one `consoleblank=0` in the original bundle
arguments. Absent, duplicate or other console forms are rejected. It removes
only `console=tty0`; the consoleblank setting, sole immutable init, five
qualified controls and three fresh identity arguments remain. The default
argument string and default U-Boot append command remain unchanged.

For this comparison, U-Boot first imports the checked original artifact, then
sets the complete base argument value with only tty0 removed, then appends the
existing controls and identities. The prefix is computed against that replaced
base, preventing duplicate init/control arguments. Both literal values reject
expansion/substitution/quote/control syntax, each command is below a conservative
512-byte bound, and exact `printenv bootargs` equality remains required before
boot. Argument commands are validated during host preparation before opening
UART. No environment save or persistent boot selection is performed.

Host commands on 2026-10-03 UTC:

```sh
python3 -m unittest discover -s tests -p test_mainline_drm_uart_observer_trial.py
openspec validate the-board-runs-a-mainline-kernel --strict
git diff --cached --check
```

**32 focused tests passed** in 8.266 seconds; strict change validation passed.
New cases cover unchanged default arguments/transport, one-token comparison,
duplicate init/control prevention, unsafe console/shell syntax, result selector,
fresh normal identity selection, an actual command-transport model and refusal
to boot after a printed-argument mismatch. Existing observer/archive/unknown
recovery tests remain included. The actual `16cp…` bundle argument file was
also read without board access: a fixed host test nonce/UUID produced exactly
the one-token deletion and command lengths **28, 206, 387 bytes**.

After protected normal recovery is qualified and the root operator reserves the
board, use the already inspected/staged bundle with fresh private output paths:

```sh
nix shell --inputs-from . nixpkgs#dtc --command \
  python3 tools/mainline-drm-uart-observer-trial.py \
  --serial-console-only \
  --bundle /nix/store/16cpjjiifxgwyb6bndhi39vfmlvcdw6h-k230-mainline-uart-observer-boot-files \
  --manifest "$HOME/tmp/k230-mainline-uart-observer-board/candidate-manifest.json" \
  --normal-report "$HOME/tmp/k230-mainline-uart-observer-board/normal-report.json" \
  --blkid-result "$HOME/tmp/k230-mainline-blkid-board/trial-result.json" \
  --log "$HOME/tmp/k230-mainline-uart-observer-board/serial-console-uart.log" \
  --result "$HOME/tmp/k230-mainline-uart-observer-board/serial-console-result.json"
```

Host Python 3.14 Zstandard inspection remains required. The result explicitly
records the comparison selector and exact expected arguments. READY/before plus
a fresh primary prompt still permit only one receipt; afterward the host only
receives until fresh protected normal return permits postflight. Failed or
unknown observer work cannot become a passed diagnostic merely through reset
or normal return. No host reboot retry is added.

<!-- UNVERIFIED --> This comparison has not run physically. Automatic return,
ordinary usable mainline root, real glass touch and a diagnosed console fault
remain unverified by this source/test change. Task 5b.5 stays open; coordinator
review/landing precedes a separate reserved trial.
