# Two-axis card entry, synthetic native QEMU

On 2026-09-24, `tests/test_card_shell_two_axis_runtime.py` ran the actual
cross-built Sway card shell under headless QEMU with two public synthetic
Wayland clients (`k230.card.one` blue and `k230.card.two` purple). Sway's
test-only native Wayland touch handler injected one contact through the real
compositor input and scene paths. No physical board or touch panel was used.

Source `532115c23074fdc390e21efd1417d43b7aedc294`; exact build:

```text
nix build .#card-shell --max-jobs 1 --cores 4 --no-link --print-out-paths --show-trace
/nix/store/516x3gx841c565f5p3ql0jgqwxs02g3i-k230-card-shell
```

Its unwrapped compositor was
`/nix/store/ixamm5fj89083y41g55x8p46wfsgbllf-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`.
The immutable client was
`/nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client`.

```sh
CARD_SHELL_SWAY=/nix/store/ixamm5fj89083y41g55x8p46wfsgbllf-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  python3 tests/test_card_shell_two_axis_runtime.py
# PASS two-axis app entry: native QEMU pixels, hold/reversal, quick opposite,
# privacy and exit; no physical touch
# Ran 1 test ... OK
```

The full screenshots were reviewed. On a 100 px upward drag, the blue client
mask's lower edge moved from y=1086 to y=976 (110 px; proportional scaling
changes the visible edge slightly). At the same vertical position, a 134 px
leftward drag moved its right edge from x=504 to x=370, exactly 134 px. A 1 px
horizontal bend did not alter vertical bounds; a stationary hold retained the
same bounds. Reversal moved the blue mask back before release. The fixture
also checked the purple target was visibly raised after release, the opposite
bottom gesture returned to blue, the private target exposed only a neutral
card before its safe focus restore, and a target that exited during drag was
not substituted with another app.

The adjacent PNGs are selected unedited headless captures of synthetic apps.
Host policy tests separately prove the projected source point follows both
finger coordinates exactly before release, bounded edges and release
thresholds, snapshotted order, keyboard/app-region exclusion, reduced motion,
second-contact cancellation, and disappearing source/target behavior.

This does not prove real-glass reachability, touch ownership against actual
applications or the keyboard, finger alignment, animation smoothness, or
latency. Those physical gates remain **UNVERIFIED**.
