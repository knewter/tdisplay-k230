# Native Wayland touch-routing regression

Recorded 2026-09-23T07:26:31Z. PASS: seven scenarios, all native receiver
processes and the QEMU-hosted compositor exit 0. The fixture is
`tests/test_card_touch_routing.py` with compiled `tests/card_touch_receiver.c`.

Source under test: adapter correction `3d1ae3f4e1991d6c13b25a11671dfd3dfb740f4f`
on top of product adapter `9865d65b80e9540ade89f70b81d4f69549057f4f`.
Actual executable:
`/nix/store/x95yrya49qds0qzrxfyqp000b01pggsp-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`.
Executable SHA-256:
`e5c9ff4faa7836a27e270b016c961a199e4eabaae6e54b05d32fb35de4c9f1b1`.

Reproduce with host C compiler, pkg-config, wayland-client development headers,
wayland-scanner, wayland-protocols and qemu-riscv64-static installed:

```sh
python3 tests/test_card_touch_routing.py \
  --sway /nix/store/x95yrya49qds0qzrxfyqp000b01pggsp-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --output /tmp/card-touch-routing-final
```

Use a new or empty output directory. The runner builds the native receiver from
source and starts a single 568x1232 headless Pixman output. It explicitly enables
`SWAY_K230_CARD_TEST_INPUT=1` and calls `card_shell test-touch` to register a real
`wlr_touch` device and emit its signals. Sway input-manager, cursor, seat handling
and actual `wl_touch` client delivery participate. The device hook independently
requires a headless backend. No direct calls to card gesture handlers fabricate
the receiver's events.

| Case | Actual receiver observation |
| --- | --- |
| Launcher footer overlapping bottom entry edge | Launcher receives id1 down/up at output (284,1195). |
| Launcher over hidden Cards button | Launcher receives id2 down/up at output (480,90). |
| Card-owned second contact on top bar, lifted first | Bar receives no id11 down; later id12 down/up is paired. |
| Card-owned second contact on reserved keyboard, lifted first | Keyboard receives no id41 down; later id42 down/up is paired. |
| Normal app after card recovery | App two receives id13 down/up. |
| Device cancel, with no later up | Fresh id21 selects the card and produces normal restoration. |
| Device removal, with no later up | Client observes removed/rebound touch capability; fresh id31 selects the card, and bar id32 down/up remains paired. |

The keyboard fixture is a real bottom layer-shell surface with a 300-pixel
exclusive zone. The bar is a real top layer-shell surface reserving 56 pixels.
The launcher fixture has namespace `k230-launcher`, full-output anchors and
layer-shell overlay placement. These are synthetic protocol fixtures, not the
installed launcher or keyboard implementation. Receiver coordinates in the JSON
are surface-local (keyboard y168 corresponds to output y1100).

`result.json` is the runner's result. The five JSONL files preserve complete
receiver events, including zero-contact exit. `adapter-events.log` contains only
constant-prefixed product metadata from the same run; debug paths and unrelated
session output were discarded. The runner rejects unpaired up/motion, duplicate
down, remaining live contacts, failed receiver exit and failed compositor exit.
It also observes actual normal restoration after each cancellation recovery.

## Evidence limits and remaining gates

This is native Wayland protocol evidence with QEMU-hosted Sway and injected
headless device events. It proves the tested ownership and pairing behavior,
not touch hardware delivery, on-glass latency, optical presentation, panel motion
quality, power or board memory/CPU budgets. Physical finger/keyboard/Apps pairing
and all declared card motion and board acceptance gates remain **UNVERIFIED**.
The root operator retains the board reservation; this runner performs no board,
UART, deployment, Nix build or normal-session modification.
