# Coordinator review of the opt-in product card adapter

Reviewed source commits `9865d65` and `3d1ae3f`, plus independent touch receiver
fixture `321601d`. Root integration equivalents are `1284122`, `523c5a4` and
`952c20e`. No default-image integration or product board deployment is claimed.

The root coordinator reviewed output/seat teardown, touch ownership, wrapper
runtime dependencies and telemetry/commit correlation. The pinned wlroots DRM
backend requires `DRM_CAP_TIMESTAMP_MONOTONIC` in `backend/drm/drm.c`; native
headless presentation uses the corresponding monotonic backend path. Output
teardown disarms the benchmark before releasing output-owned state.

Review found two concrete input bugs: the hidden Cards/edge regions could steal
Apps touches, and a second contact on the top bar could forward a down while
swallowing its up. Both were corrected before this handoff. Separately, the
author found XDG popups outside the mirrored content tree and added explicit
normal-mode fallback rather than leaving an unscaled/private popup above cards.

The root independently reran:

```sh
python3 tests/card_shell_runtime.py \
  --sway /nix/store/x95yrya49qds0qzrxfyqp000b01pggsp-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --client /nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client \
  --native-touch --output /mnt/MediaVolume/home/jadams/k230-root-card-product-review
python3 tests/test_card_touch_routing.py \
  --sway /nix/store/x95yrya49qds0qzrxfyqp000b01pggsp-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --output /mnt/MediaVolume/home/jadams/k230-root-touch-routing-review
```

PASS: seventeen product runtime assertions, seven independent Wayland receiver
pairing/recovery cases, and clean compositor/client exits. Input travels through
a registered test wlroots touch device, cursor, seat and protocol delivery.
This is stronger host routing evidence than direct calls to card handlers; it
remains injected headless execution and cannot prove the board's touch hardware
or real-finger feel. The native protocol fixture's normalized evidence is in
`../card-touch-routing-host/`; adapter evidence and rejected host cost acceptance
are in `headless/`.

The final reviewed package is
`/nix/store/c41z2czaiana4dh8a7a2w6pwrqkawdgj-k230-card-shell`. It remains opt-in.
The earlier measured headless benchmark exceeded the frame-interval budget and
lacked isolated-session memory accounting; those results remain diagnostic
FAIL/INCOMPLETE, never product acceptance. Default Pixman board cost, integrated
controls, QEMU system-image smoke, physical gestures and optical review remain
open in the product proposal. No timeout or card-count reduction substitutes
for those requirements.
