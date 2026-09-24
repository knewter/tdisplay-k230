# Selected card visibility: headless regression

At 2026-09-24T05:58:49Z, the installed unwrapped Sway executable was used as
a negative control against `tests/card_shell_runtime.py` at `a2f6fc02`:

```sh
python3 -u tests/card_shell_runtime.py \
  --sway /nix/store/qwja5838kgidxzvii70l0smf72snzsqs-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --client /nix/store/bxiz9zkb33m4v97gkgzx91aswfm7cf9f-card-composition-probe-client-riscv64-unknown-linux-gnu-0.1/bin/card-composition-probe-client
```

The new two-window assertion failed: the output pixel at `(284, 700)` was
`(32, 112, 176)` both before and after opening the second card, although the
IPC tree reported the second window focused. This reproduces a focused but
visually obscured floating window, without using application titles or
private content.

The same source built with the focus-raise fix:

```sh
nix build .#card-shell --max-jobs 1 --cores 4 --no-link --print-out-paths
# /nix/store/h3sk26nxgh4i64wbf7v0n0fx26psn3mw-k230-card-shell
python3 -u tests/card_shell_runtime.py \
  --sway /nix/store/ildcfqicn8j22yih16x42b4mmajqq6x8-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --client /nix/store/bxiz9zkb33m4v97gkgzx91aswfm7cf9f-card-composition-probe-client-riscv64-unknown-linux-gnu-0.1/bin/card-composition-probe-client
```

The suite passed all 17 headless scenarios. The pixel changed from the first
client's blue `(32, 112, 176)` to the selected second client's purple
`(72, 24, 64)`. The source-only follow-up `d455473a` changes indentation; the
built executable corresponds to `a2f6fc02`.

This is QEMU user-emulated compositor output with injected card commands. It
does not prove the patched image is installed, nor real-touch or panel behavior.
The device operator must install the combined image and repeat card selection
on glass before closing the physical gate.
