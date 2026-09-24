# Quiet touch-first deck: native composed-pixel review

Captured 2026-09-24 07:42 UTC from exact compositor source `bfb553712993447d0a6e4ff32420975723c49b53` in a 568×1232 headless QEMU Sway session. The four PNGs are unedited compositor captures of a public synthetic app. The paired Rust wallpaper client and pinned Catppuccin/Latte generations supplied the actual theme surfaces. This is native composed-pixel and injected-command evidence, not the installed panel, real-finger motion, optical readability or a performance measurement.

The exact `nix build .#card-shell --no-link --print-out-paths --max-jobs 1 --cores 4` output was `/nix/store/3fyd7pkdp24xb2fapa2ybgyjnys1wcsh-k230-card-shell`; its unwrapped Sway executable was `/nix/store/4blrilfgpj2ipd89jg4slqljhg2swyfc-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway` (SHA256 `c0fc7127fc83d42e19bf304988f79618494b10488227c52cad29af4bb591fe6e`). The paired Rust, fixture client, theme bundle and icon root are the exact paths in the reproducible command:

```sh
python3 tests/test_real_theme_paired_runtime.py \
  --sway /nix/store/4blrilfgpj2ipd89jg4slqljhg2swyfc-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --rust /nix/store/l8i7g4y9c18gm8l10m7a61cjbpgxvby4-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust \
  --client /nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client \
  --theme-bundle /nix/store/aajw0dknkkwx4mdswaa0vd52li64d6i7-handheld-theme-default-28ceaae7 \
  --icons /nix/store/in3nc21zx02xiz2rdp5bpq36719x3axd-handheld-theme-icons-25.10.3 \
  --output /tmp/k230-deck-chrome-final-qemu --check-restart --deck-visual-states
```

The existing paired theme transaction, wallpaper, rollback and restart assertions passed. The added state fixture captured [dark ordinary](dark-ordinary.png), [Latte ordinary](latte-ordinary.png), [Latte private](latte-private.png), and [Latte empty](latte-empty.png). All are 568×1232. The private capture has no recognizable blue live-client pixels in the card region, retaining only the neutral private frame and label; the empty deck has a named state and the same drawer cue. Visual inspection finds the oversized generic `Cards` heading, procedural subtitle and `Selected:` prefix absent in touch-first mode. The old button/label path remains in the separately enabled rollback mode. Source-level card-title tests additionally preserve arbitrary app titles containing `@`, and map only image-managed `k230-terminal`, `k230-monitor` and `nnn` IDs to friendly names.

The large card silhouette, live app viewport geometry, and real themed desktop-entry icon in the card header remain open against the visual study. This focused chrome edit adds no icon decoder to the compositor; coherent-shell task 1.4 and the physical deck/gesture gates remain unchecked.
