# Offline application host evaluation

2026-09-23 host-only target evaluation. `nano` resolved to
`/nix/store/ddlmrxj9qxwm2k22b7qh4qyzkx8v8y8s-nano-riscv64-unknown-linux-gnu-9.2.drv`.
`nnn` resolved to `/nix/store/y6ljii8gl8x4xh5frb1ck32mmvzgwcvb-nnn-riscv64-unknown-linux-gnu-5.3.drv`
and built successfully with `nix build .#nixosConfigurations.k230.pkgs.nnn --option max-jobs 1 --option cores 8`.
`lf` resolved to `/nix/store/bzkn9wjy9kx9i2b56gzc7iy11dxnz011-lf-riscv64-unknown-linux-gnu-42.drv`; closure inspection triggered its uncached Go module derivation, so it is not selected or marked built.

This is host/package evidence only. No image, startup, injected input, or physical touch claim is made.
