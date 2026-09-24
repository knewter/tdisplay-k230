# Deck appearance receiver: source and headless QEMU checkpoint

Observed 2026-09-24 UTC. Source `42b75286f814439cf2a0570e9561c20e2a0fc873`
cross-built `.#card-shell` to
`/nix/store/glwlqyiaqnkjmz5hbff9rkvs730f29l8-k230-card-shell` with Sway
`/nix/store/qwja5838kgidxzvii70l0smf72snzsqs-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`.
The first build stopped at `M_PI` under pinned C11 compilation; source
`42b75286` replaced it with a literal and the corrected build passed. The
failing log is `/tmp/k230-card-appearance-build.log`; the passing log is
`/tmp/k230-card-appearance-build-v2.log`.

The private deck endpoint is opt-in through
`SWAY_K230_CARD_APPEARANCE_SOCKET`, `SWAY_K230_CARD_THEME_STATE_ROOT`, and
`SWAY_K230_CARD_THEME_DEFAULT`. It uses the existing protocol 1
prepare/commit/rollback exchange and same-UID 0600 Unix socket. It stages a
bounded report and appearance payload by immutable generation identity;
commit redraws deck canvas, card backgrounds and labels before ACK. Authored
`card.canvas`, `card.background`, and `card.selected-background` brushes use
their typed gradient stops, angle and alpha in cached Cairo scene buffers.
Absent card roles use the reported palette. A selected still background makes
the deck canvas transparent when no explicit card canvas is authored; the
separate Rust background layer owns media decoding and placement, so this
checkpoint does not prove wallpaper display.

Native receiver check: `python3 tests/test_card_shell_appearance.py` passed
6 cases including changed generation, repeated commit, rollback after failed
prepare, private socket mode, fresh home fallback, RGBA palette, and FIFO
rejection without blocking the compositor. The exact target was then run in
headless QEMU with a live synthetic card and a 568×1232 Pixman output:

```sh
python3 tests/test_card_shell_appearance_runtime.py \
  --sway /nix/store/qwja5838kgidxzvii70l0smf72snzsqs-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --client /nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client \
  --output /tmp/k230-card-appearance-repro-qemu
```

PASS. The test staged a synthetic card generation with a horizontal red→blue
canvas and green→yellow selected-card background, committed it, then rolled
back to the pinned default. [before.png](before.png), [themed.png](themed.png),
and [restored.png](restored.png) were visually reviewed. The canvas at
`(10,500)` changed from `(30,30,46)` to `(250,0,5)` and returned to
`(30,30,46)`. The themed canvas right edge at `(558,500)` was `(4,0,251)`;
the card margins at `(80,500)` and `(480,500)` were `(8,255,0)` and
`(242,255,0)`. [result.json](result.json) preserves exact sampled values.
The synthetic source pixels remained visible in the themed capture.

This is host-native protocol and headless QEMU pixel proof, not physical panel
or finger proof. It does not verify the Rust wallpaper layer, coordinated
two-endpoint failure rollback, arbitrary third-party themes, latency, CPU
budgets, or restored appearance after an on-device reboot. Those gates remain
open and no physical OpenSpec task is checked.
