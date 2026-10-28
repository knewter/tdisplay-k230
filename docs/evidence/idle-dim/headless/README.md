# Wake gate on a powered-off output: headless smoke (task 2.3)

Evidence class: **headless** (host run of the real cross-built RISC-V Sway under
`qemu-riscv64-static`, headless Pixman backend, injected `wlr_touch` events, a
real native `wl_touch` Wayland probe client). It is not a board, DRM panel or
finger observation. The board gate for the wake tap is task 3.1/3.3 and the
operator reports in `docs/evidence/idle-dim/`.

Run 2026-10-28T18:22:14Z to 18:22:15Z. Built with
`flock /tmp/k230-nix-build.lock nix build .#card-shell --max-jobs 1 --cores 4 --out-link <scratch>/cs`,
store path `/nix/store/bkl034mjl5yhjsa2ghjr2vllq7wxbrad-k230-card-shell`
(unwrapped compositor
`/nix/store/0695y4qc3k3w5zq11ci292q8mn8xw5x3-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`).

Command:

```
python3 tests/test_card_shell_wake_gate_runtime.py \
  --sway /nix/store/0695y4qc3k3w5zq11ci292q8mn8xw5x3-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --output /tmp/wgcs
```

Result: PASS. Sequence, as printed by the test:

```
2026-10-28T18:22:14Z probe mapped, output power true
2026-10-28T18:22:14Z output * power off; get_outputs power [False]
2026-10-28T18:22:14Z touch down id 7 injected; get_outputs power [True]
2026-10-28T18:22:15Z down/motion/motion/up completed; power [True]; probe touch events during sequence: 0
2026-10-28T18:22:15Z positive control: id 8 down and up reached the probe with output on
```

Files: `result.json` (steps and every touch event the probe logged),
`probe.jsonl` (the probe's raw log: only id 8, the positive control, appears;
id 7, the waking sequence, never does), `sway-log-excerpt.txt` (compositor log:
`output * power off`, then the gate's own `output * power on`, then the injected
operations).

Limits: the "output" is the headless backend's `wlr_output->enabled`, which is
what `get_outputs` reports as power; the panel backlight, DRM modeset and real
touch controller are not exercised. Input is injected through the guarded
`card_shell test-touch` device. The test shows the whole down/motion/up
sequence is swallowed and a later touch with the output on is delivered; it does
not show the swallowed contact behaves on glass (see 3.1 to 3.3).
