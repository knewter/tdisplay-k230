# Integrated Rust reveal under headless QEMU

Evidence class: headless QEMU compositor and Rust Wayland client, with synthetic
wlroots touch input and synthetic live app pixels. Run on 2026-09-23. The
compositor sender source is `d9b24140273a2d7ca24f137e9097b88f307448e5`
(sender code `ea920846ae44d602c21953b0cbb97f2289662590`). Its exact
cross-built card package is
`/nix/store/13mxaxxmldpmcx418d6cq9bjvcc72ifb-k230-card-shell`; QEMU ran the
package's unwrapped RISC-V ELF
`/nix/store/6a0jd8i6sg8ix6j9mkhz72wnb4h5diyg-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`.
The Rust receiver source is
`a8fa5d3283e679724a554d9db52203b98f90ce0e` and exact RISC-V ELF is
`/nix/store/kn3x90rplwfrf83z1nk0jjpa0whigrk1-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust`.
The live source was the host package
`/nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client`.

From this branch, the reproducible command is:

```sh
python3 tests/card_shell_runtime.py \
  --sway /nix/store/6a0jd8i6sg8ix6j9mkhz72wnb4h5diyg-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --client /nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client \
  --rust-reveal-client /nix/store/kn3x90rplwfrf83z1nk0jjpa0whigrk1-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust \
  --output /tmp/k230-reveal-integrated-qemu-a8fa --touch-first --native-touch
```

Result: `PASS Rust reveal receiver: actual QEMU pixels, reversal, settle and
input routing; no physical touch`. The five attached 568×1232 captures were
visually inspected; they contain only synthetic probe card pixels and ordinary
installed desktop-entry names. They show the live deck, an intermediate Rust
drawer over the same live card, a reversed drawer, settled open drawer, and
intermediate shade. At background sample `(10,1000)`, deck was RGB
`(17,24,39)`, drawer mid `(21,33,46)`, reversed `(17,24,39)`, and open
`(26,41,54)`; at `(10,100)`, shade mid was `(25,39,52)` versus deck
`(17,24,39)`. The receiver's log had no `touch-down 80` during the
compositor-owned finger stream, then logged `touch-down 82 284.0 1000.0`
after the drawer settled open. All five images and their hashes are in
`docs/blob-inventory.md`.

This proves actual headless compositor/receiver pixels and input-region
routing for this synthetic path. A `grim` capture is not a panel presentation
or real-finger observation. It does not establish board CPU/frame budgets,
theme appearance, private-card handling, or failure recovery. Those gates
remain open in the coherent-shell and card changes.
