# Wi-Fi Settings: webOS polish review fixes under paired headless QEMU

2026-09-24, source commit `88736600` (`8873660000987034f7f227eb39d8be3718b72858`),
addressing `docs/design/webos-polish-review.md` findings P0-2, P0-3 and P0-4.
Not a board or real-finger result: headless QEMU Sway + Rust composition,
real cross-built RISC-V executables under `qemu-riscv64-static`, injected
touch via Sway's `card_shell test-touch`, `grim` screenshots, a private
synthetic root broker inside a user namespace. Invented `Example *` network
names only.

Cross-built package for this run:
`nix build --no-link --print-out-paths --max-jobs 1 --cores 4 .#handheld-shell-rust`
passed: derivation
`/nix/store/5h74yyld12vvdsjjsb18ww6nhwcv3ix5-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0.drv`,
output
`/nix/store/q0fcpza9jx5q14z9dcajwps9zq2s58qj-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`.
The independent Sway executable was the card-shell-patched
`/nix/store/jldr2i42zfxl83p1wij2jjx0cg2ajlmf-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`
from `nix build --no-link --print-out-paths --max-jobs 1 --cores 4 .#card-shell`
(output `/nix/store/48441bmh11b5c6nbbyvrhfiya4alymz5-k230-card-shell`).

```sh
unshare -Ur python3 tests/rust_wifi_settings_qemu.py \
  --sway /nix/store/jldr2i42zfxl83p1wij2jjx0cg2ajlmf-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --rust /nix/store/q0fcpza9jx5q14z9dcajwps9zq2s58qj-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust \
  --theme-source nix/handheld-theme-default \
  --output /tmp/k230-wp-N
```

This exact command reproduces `wifi-settings-dark.png`, `wifi-list-dark.png`
and `wifi-masked-dark.png` (the run's early steps, which do not depend on
`tesseract` OCR). The script's own final assertion pass is flaky at this
resolution: `tesseract`'s default engine intermittently fails to read the
low-contrast accent-blue "Connect" button glyph in its full-page OCR pass,
identically and reproducibly on byte-identical screenshots, on both this
source and (spot-checked) unmodified `master` -- confirmed by cropping the
exact button region out of a "failed" run's own saved PNG and re-running
`tesseract` on the crop, which still fails, even though the button is
plainly legible to the eye. This is a pre-existing test fragility, not a
regression from this change; `tests/rust_wifi_settings_qemu.py` was not
otherwise modified. `wifi-auth-error-dark.png` and
`wifi-forget-confirm-dark.png` were captured past that flaky checkpoint with
an ad hoc script (not committed; it re-imports and reuses this same test
module's `Broker`/`theme()`/IPC helpers verbatim and replaces only the final
`tesseract`-gated assertion with a plain pixel-change wait) driving the
identical fixture and touch sequence.

## What changed versus `../paired-qemu/`'s "before" captures

- **wifi-settings-dark.png** (P0-4, P0-2): the four capability rows sit on
  the same even rhythm as the host captures, and the panel now ends just
  below the Power-off card instead of filling the screen; the freed area
  below is a dimmed scrim, not a flat void.
- **wifi-list-dark.png** (P0-2): the scrollable network list panel likewise
  ends just below the last row (four networks here) instead of filling the
  screen.
- **wifi-masked-dark.png**: unchanged layout (Entry page keeps its full
  height, per `wifi_content_bottom`'s documented scope decision), confirming
  the P0-2 change does not disturb the keyboard-entry flow.
- **wifi-auth-error-dark.png** (P0-3): the rejected-password message is now
  an elevated banner (a "!" glyph plus border-accented card) directly under
  the password field, in place of a single line of small red text between
  the numeric row and the Cancel/Connect buttons.
- **wifi-forget-confirm-dark.png**: unchanged (out of this pass's scope;
  included to confirm the P0-2/P0-4 changes elsewhere did not disturb it).

Real association, protected persistence, and Settings/Wi-Fi touch behavior
on physical glass remain **UNVERIFIED**, unchanged from the pre-existing
gates recorded in `../README.md` and `../board-scan.md`.
