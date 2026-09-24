# App-to-card direct drag: host and QEMU checkpoint

Source: `7eff7613733c05aa4bf9f4fe23911fb59e25d03d`, after the local
cherry-picks of the drawer/shade travel correction (`c5cf6146`) and diagonal
reveal correction (`48f9a8fa`). The exact cross-built card package was
`/nix/store/j4cq3c28dnk6jybi66k32a1ydzx80ffr-k230-card-shell`; its
unwrapped compositor was
`/nix/store/6jx6nlxxc2hy5viidq7msnlpshidd5w6-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`.

Commands and results on 2026-09-24:

```text
python3 -m unittest tests.test_card_shell_state tests.test_card_shell_route tests.test_card_shell_reveal -q
Ran 27 tests ... OK

nix build .#card-shell --max-jobs 1 --cores 4 --no-link --print-out-paths --show-trace
/nix/store/j4cq3c28dnk6jybi66k32a1ydzx80ffr-k230-card-shell

CARD_SHELL_SWAY=/nix/store/6jx6nlxxc2hy5viidq7msnlpshidd5w6-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  python3 tests/test_card_shell_touch_first_runtime.py
PASS touch-first drawer route: actual cross-built Sway under QEMU; no physical touch
PASS continuous reveal IPC: QEMU Sway and mapped overlay; no Rust pixels/physical touch
Ran 1 test ... OK
```

The native policy fixture checks the projected point under the accepted finger
at multiple displacement and reversal coordinates, a stationary held contact,
one-time geometry capture, release below and above the separate 72 logical px
commit threshold, post-release settlement, interruption, privacy/source loss,
and cancellation. The QEMU fixture checks live entry frame changes and
reversal against the real cross-built Sway executable; it does not measure
physical display pixels or finger alignment on the panel. Real-glass movement,
latency, and animation smoothness remain **UNVERIFIED**.
