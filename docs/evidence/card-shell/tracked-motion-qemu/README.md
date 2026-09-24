# Live-card motion in headless QEMU

Date: 2026-09-24 UTC. Source: clean `impl/live-card-integrated`
`aa9015191bc049a06d161392191c6e5745498cb6`, with motion commits and
host limits listed in [the host checkpoint](../tracked-motion-host.md).
The Nix build used `nix build .#card-shell --max-jobs 1 --cores 4 --no-link
--print-out-paths` and passed from this source. Final package:
`/nix/store/py8nv6xlf2wc66jxmy6byvf0hskdc7ja-k230-card-shell`;
derivation: `/nix/store/dkd44v0f6nnqv1nvrlldjzqqshzz1i15-k230-card-shell.drv`.
Its wrapper selects the actual RISC-V Sway executable at
`/nix/store/dcv9yzsa2mbbxmbiz1cp0dr5dkhlbxr8-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`
(SHA-256 `ff67a91c2544cabceefe2fc8d0177a8161e46053b2e8b3ab71aa1e1ac4ed3fbd`).
The live nested-surface fixture was
`/nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client`.

The exact cross-built Sway ran under `/usr/bin/qemu-riscv64-static` with a
568×1232 headless wlroots output, Pixman renderer, two live fixture views,
and `SWAY_K230_CARD_TOUCH_FIRST=1`. Commands and results:

```text
CARD_SHELL_SWAY=<Sway path above> CARD_SHELL_CLIENT=<fixture path above> \
  python3 tests/test_card_shell_touch_first_runtime.py
  PASS: one actual Sway/Wayland runtime case, including a mapped drawer layer,
  no legacy Back hit target, fixed drawer/shade routes, live entry, expansion,
  and restored focus.
python3 tests/card_shell_runtime.py --sway <Sway path above> \
  --client <fixture path above> --touch-first \
  --output /tmp/k230-live-card-motion-evidence
  PASS: retained the synthetic fixture screenshots copied beside this note.
CARD_SHELL_SWAY=<Sway path above> CARD_SHELL_CLIENT=<fixture path above> \
  python3 tests/test_card_shell_composition.py
  PASS: 17 headless runtime checks, including private/unavailable placeholders,
  live-to-private transition, nested surfaces, and clean teardown.
CARD_SHELL_SWAY=<Sway path above> CARD_SHELL_CLIENT=<fixture path above> \
  python3 tests/test_card_shell_gestures.py
  PASS: the same 17 headless runtime checks.
CARD_SHELL_SWAY=<Sway path above> CARD_SHELL_CLIENT=<fixture path above> \
  python3 tests/test_card_shell_recovery.py
  PASS when run alone: recovery and disabled-adapter runtime routes.
```

An initial recovery invocation ran concurrently with the gestures QEMU suite
and failed an existing one-second frame-callback increase assertion for one
fixture (`[5,4]` remained `[5,4]` while the other advanced `[26,25]` to
`[35,34]`). The identical recovery command passed when rerun alone. The
concurrent failure is retained as a harness timing limit; no source fix or
performance claim is inferred from the rerun.

The screenshots show actual compositor output of synthetic pixels. The purple
live content bounds move from roughly `(40,48)–(543,1087)` at entry start to
`(77,100)–(487,947)` in the middle and `(120,152)–(435,807)` at the end,
using the same color threshold in each image. `before-expand.png` and
`during-expand.png` show the selected live card growing toward the source view
geometry. These captures prove visible intermediate geometry in headless
QEMU, not physical panel presentation or a measured smooth frame cadence.

Remaining gates: inspect real-finger tracking and focus/cancel/privacy on the
reserved board and camera, establish an actual presented-frame transition and
CPU/frame budget profile with the integrated image, and record optical
acceptance. The policy's full-geometry timer dwell is not a Wayland frame or
output-presented acknowledgment. No hardware or performance task is checked
by this evidence.
