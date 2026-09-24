# Rust theme chooser: paired QEMU touch checkpoint

On 2026-09-24, `tests/rust_theme_chooser_qemu.py` drove actual Wayland touch
through the cross-built Sway compositor and corrected Rust frontend under
headless QEMU. The theme command was a local synthetic fixture that logged
argv and returned the installed command's schema-1 JSON shape. It never called
the production theme transaction or changed user themes.

Exact artifacts:

- Rust frontend source `f80eedcd19e563d2804fe682ed9d75deac9a3adb`, target
  `/nix/store/rlb1kr180g8khgnqx83kfynl5lyvv0h5-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust`.
- Sway target
  `/nix/store/6jx6nlxxc2hy5viidq7msnlpshidd5w6-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`,
  from the direct-drag package
  `/nix/store/j4cq3c28dnk6jybi66k32a1ydzx80ffr-k230-card-shell`.

```sh
python3 tests/rust_theme_chooser_qemu.py \
  --sway /nix/store/6jx6nlxxc2hy5viidq7msnlpshidd5w6-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --rust /nix/store/rlb1kr180g8khgnqx83kfynl5lyvv0h5-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust \
  --output /tmp/k230-theme-chooser-qemu-f80-2
# PASS paired Sway/Rust theme chooser QEMU touch, synthetic backend; no physical touch
```

The test injected Settings → Themes, a 300 px list scroll, a row preview,
selection of a different still background, Cancel, a second preview, and
Apply. It compared screenshot pixels at each scene transition; the preview
and selected-background images were opened and visually inspected. The
fixture's complete command sequence was `list`, `preview`, `preview
--background`, `list`, `preview`, `activate --expected-generation --background`.
Only the final explicit Apply produced `activate`; its generation matched the
reviewed preview. Both theme identities and images were synthetic, and no
private app screenshot or secret was recorded.

This proves the cross-built chooser's route, touch hit areas, scroll rendering,
selection feedback, and command dispatch in QEMU. It does **not** prove a
production theme transaction, installed image, real panel response, physical
touch, video background playback, or all-theme compatibility. Those gates
remain **UNVERIFIED**.
