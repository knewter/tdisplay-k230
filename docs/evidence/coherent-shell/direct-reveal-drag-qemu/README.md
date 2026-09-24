# Direct drawer and shade tracking: headless QEMU

Run at 2026-09-24 06:22 UTC. This is synthetic `card_shell test-touch` input in a
568×1232 headless Pixman Sway compositor under QEMU. The card is a public probe
fixture and the drawer catalog contains one temporary public desktop entry.
The adjacent PNGs are original compositor captures; `result.json` records the
measured panel edges. No physical finger, LCD, or latency/CPU measurement is
represented.

The combined compositor source is `7eff7613733c05aa4bf9f4fe23911fb59e25d03d`
(including the direct-travel denominator correction `c5cf6146` and diagonal
projection correction `48f9a8fa`). The card package was
`/nix/store/j4cq3c28dnk6jybi66k32a1ydzx80ffr-k230-card-shell` and the exact
Sway executable was
`/nix/store/6jx6nlxxc2hy5viidq7msnlpshidd5w6-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`
(SHA256 `cb94679b97cdab2c1b61743f163f74d97db8e20e459b1c20f1eb94aa53bbad36`).
The Rust receiver was
`/nix/store/rbvcqv3sjq87iami6iymwd9cx7nzhhma-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust`
(SHA256 `7b0b104cffdc9523f999b2a7bd9762e98bd5ff89a2f2a7e7c9861c7f5221275f`).
The synthetic live client was
`/nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client`.

Reproduce from this repository with:

```sh
python3 tests/test_direct_reveal_drag_runtime.py \
  --sway /nix/store/6jx6nlxxc2hy5viidq7msnlpshidd5w6-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --rust /nix/store/rbvcqv3sjq87iami6iymwd9cx7nzhhma-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust \
  --client /nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client \
  --output /tmp/k230-direct-drag-qemu-positive-01
```

The original control run with the prior Sway executable
`/nix/store/qwja5838kgidxzvii70l0smf72snzsqs-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`
failed as intended: a 100 px drawer finger move shifted the captured panel
edge 135 px (observed y=1097; exact 1:1 expected y=1132). With the combined
candidate, the drawer edge after 100 px was 1132, held at 1132 during a
250 ms pause and a 100 px horizontal perturbation at unchanged y, returned to
1172 after a 40 px reverse, and settled at 234 after a separate full swipe.
The corresponding shade edges were 100, 100, 60, and 801. Both below-threshold
reversed gestures unmapped and restored the deck. The pixel assertions allow
2 px for movement/reversal and 1 px for no-drift hold.

The test exercises composed intermediate pixels and the existing synthetic
input route. It does not establish glass finger tracking, panel presentation
timing, real touch controller sampling, or the strict device frame/CPU budget.
Those remain separate physical gates.
