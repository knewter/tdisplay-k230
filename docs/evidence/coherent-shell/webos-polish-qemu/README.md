# Card deck: webOS polish review fixes under paired headless QEMU

2026-09-24, source commit `ce9b006d` (`ce9b006da428606e65eacfe715573f3f5535c3c2`),
addressing `docs/design/webos-polish-review.md` findings P0-1 and the C
halves of P1-1/P1-2. Headless (`WLR_BACKENDS=headless`) real Sway/Wayland
compositor runtime under `qemu-riscv64-static`, injected touch/IPC through
`tests/card_shell_runtime.py`, `grim` screenshots. This is
**not** a board, glass, or real-finger result.

Cross-built inputs:
`nix build --no-link --print-out-paths --max-jobs 1 --cores 4 .#card-shell`
passed, output
`/nix/store/48441bmh11b5c6nbbyvrhfiya4alymz5-k230-card-shell`, providing
`/nix/store/jldr2i42zfxl83p1wij2jjx0cg2ajlmf-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`.
`nix build --no-link --print-out-paths --max-jobs 1 --cores 4 .#card-composition-probe`
passed, output `/nix/store/wjzw7jw21p8qq4dsbc8b3fky9233pgqq-k230-card-composition-probe`,
providing a synthetic live-card client (public fixture content, no real
application window).

```sh
python3 tests/card_shell_runtime.py \
  --sway /nix/store/jldr2i42zfxl83p1wij2jjx0cg2ajlmf-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --client /nix/store/wjzw7jw21p8qq4dsbc8b3fky9233pgqq-k230-card-composition-probe/bin/card-composition-probe-client \
  --output /tmp/k230-deck-cap --touch-first
```

Exit: `PASS touch-first drawer route: actual cross-built Sway under QEMU; no
physical touch`. The broader
`python3 tests/test_card_shell_composition.py` (same `--sway`/`--client`
pair, via `CARD_SHELL_SWAY`/`CARD_SHELL_CLIENT`) separately passed all 17
cases (`horizontal-live-deck`, `private-placeholder`,
`unavailable-placeholder`, `live-privacy-transition`, and 13 others),
confirming `sync_card`'s label and new badge wiring survive a real
Sway/Wayland runtime, not just the standalone C title-resolution unit test
in `tests/test_card_shell_deck_title.py`.

## `deck-home.png` (`before-expand.png` from the run above)

Shows the shipped `touch_first()` chrome with one live card:

- **"Home"** title, drawn with the explicit `CARD_SHELL_FONT_FAMILY`
  ("DejaVu Sans") instead of the bare `"sans"` alias (P1-1 C half; not
  visually different on this build host, since DejaVu Sans is what
  fontconfig's default already resolved "sans" to here -- the fix is about
  not depending on that resolution elsewhere, not a pixel change on this
  particular machine).
- A rounded icon badge reading **"C"** beside the card's label (P0-1): the
  probe client's app_id has no matching `.desktop` entry (it is a synthetic
  test fixture, not a real shipped app), so `card_display_title` correctly
  falls through to the client's own raw title, **"Card one: accepts
  close"**, and the badge takes its first letter -- exactly the
  documented, deliberate fallback path for an app_id outside the shipped
  three. The standalone dependency-free-scan resolution (an app_id that
  *does* match a `.desktop` `StartupWMClass=`) is covered instead by
  `tests/test_card_shell_deck_title.py`'s new temporary-file case, since
  this probe client cannot carry a real installed desktop entry.
- **"Swipe up for apps"**, now sentence case at the unified size 14 and a
  muted color approximation (`appearance_text_muted`), in place of the
  prior size-19 full-strength-color cue (P1-2 C half).

Real-glass legibility and contrast of the badge and the muted cue at actual
panel brightness remain **UNVERIFIED**, per AGENTS.md; this run supplies
build-and-composite proof only.
