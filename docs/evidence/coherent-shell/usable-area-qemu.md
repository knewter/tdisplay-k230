# Ordinary app usable-area geometry: headless QEMU

At 2026-09-24 04:47 UTC, source `7fa79b5c09e55c1fc36adb073753a4a9ea29df75`
cross-built `.#card-shell` as
`/nix/store/w395hanhg1p2hr5fca773f4inwzz2fdw-k230-card-shell`. Its Sway ELF is
`/nix/store/ix0gf208psg2f2z43p25hjrh2x79bbhm-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`.
The test used that ELF under `qemu-riscv64-static`, an actual cross-built
`wvkbd-mobintl` layer client, two cross-built live probe clients, and a host
Zenity window on a 568 × 1232 headless output:

```sh
python3 tests/test_card_shell_usable_area_runtime.py \
  --sway /nix/store/ix0gf208psg2f2z43p25hjrh2x79bbhm-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --client /nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client \
  --keyboard /nix/store/n7p6qfbyw30yany09x8kr95j2ar1fh7b-wvkbd-riscv64-unknown-linux-gnu-0.20/bin/wvkbd-mobintl \
  --dialog /usr/bin/zenity \
  --output /tmp/k230-card-usable-final-qemu
```

PASS. Both marked ordinary app rectangles were `(0,0,568,1232)` before the
keyboard, `(0,0,568,812)` while wvkbd reserved a 420-pixel exclusive zone,
and `(0,0,568,1232)` after it hid. The workspace rectangle changed in the
same sequence. The separately floating Zenity rectangle stayed
`(112,497,343,238)` while the keyboard mapped and after it hid. The runtime
saved exact tree snapshots and Sway/client logs in the named temporary
directory. The first implementation only restored the workspace on hide;
the final `arrange_layers()` usable-area hook is covered by this regression.

`python3 tests/test_card_shell_state.py` passed 25 tests;
`python3 tests/test_card_shell_route.py` and
`python3 tests/test_card_shell_reveal.py` passed one each.
`python3 tests/test_card_shell_touch_first_runtime.py` also passed its actual
cross-built Sway headless QEMU route and reveal checks. This is compositor
geometry evidence under headless QEMU. The Zenity window is an independent
floating window, not proof of parented transient semantics. It does not prove
a real panel, finger interaction, on-device keyboard/terminal readability,
theme integration, or the coherent image configuration; those gates remain
open. The normal image still needs the root-owned `for_window` criterion to
invoke `card_shell ordinary` only for ordinary apps, with video exclusions.
