# Rust notification shade close: paired QEMU regression

Observed 2026-09-24 05:56 UTC on a 568×1232 headless Pixman output under
`qemu-riscv64-static`. The Sway binary was
`/nix/store/qwja5838kgidxzvii70l0smf72snzsqs-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`;
the live public card client was
`/nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client`.
The positive Rust target was
`/nix/store/rbvcqv3sjq87iami6iymwd9cx7nzhhma-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust`,
built from shade fix `062c6cfd` (derivation `v9ppq0klws51rnx8kcnmbki9fm9pq213`).

```sh
python3 tests/test_rust_shade_dismiss_runtime.py \
  --sway /nix/store/qwja5838kgidxzvii70l0smf72snzsqs-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --rust /nix/store/rbvcqv3sjq87iami6iymwd9cx7nzhhma-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust \
  --client /nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client \
  --output /tmp/k230-shade-dismiss-qemu-hotfix-01
```

PASS. A private desktop catalog contained only one `Public Fixture` entry.
After opening the [shade](shade-open.png) over the live deck, a 280-pixel
upward touch followed by `wl_touch.cancel` left it [mapped](shade-cancelled.png).
A second simultaneous contact also left it [mapped](shade-multitouch.png).
A sole upward touch release then produced a Rust `unmap`; the original
[live deck](deck-restored.png) pixel reappeared. Repeating the close over an
[ordinary app](app-shade.png) restored its [live app pixel](app-restored.png)
and the Sway tree still contained that app. `result.json` records exact target
paths and asserted outcomes. The PNGs were visually reviewed and contain
only synthetic public content.

As a negative control, the same fixture against the pre-fix Rust target
`/nix/store/g2sd1naq9f0r3ncg36kh9dw1d0rznhrb-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust`
reached the sole upward `touch-down`/`touch-move`/`touch-up` events, then
timed out waiting five seconds for `unmap`. The negative run's local log is
`/tmp/k230-shade-dismiss-qemu-negative-01/rust.log`; it is not committed.

This proves QEMU compositor output and synthetic input routing. It does not
prove real panel pixels, a physical finger gesture, notification history,
service availability, or the updated image boot. The reported on-device
failure and its installed fix require a separate board observation.
