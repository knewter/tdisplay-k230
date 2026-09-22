# Touch launcher laptop validation

Date: 2026-09-22

The persistent menu protocol/action test confirms that Apps starts the native
launcher while Windows, Keyboard, and System retain their status-bar routes.
It also covers the prior Terminal/Monitor focus-or-start and deliberate New
terminal action paths.

```sh
python3 tests/test_touch_menu.py
nix build .#touch-launcher --option max-jobs 1 --option cores 2 \
  --option substituters https://cache.nixos.org
nix path-info -Sh .#touch-launcher
nix eval --raw .#nixosConfigurations.k230.config.system.build.toplevel.drvPath
openspec validate the-shell-launches-apps-without-a-keyboard --strict
```

All commands passed against the corrected source. The package output is
`/nix/store/7rrd0aq28knmxwvij2cpq3abxd1xn6gs-k230-touch-launcher`; its complete
closure is 192.7 MiB, including the existing RISC-V Bash, glibc, and Wayland
runtime graph. The stripped native RISC-V launcher ELF is 27,120 bytes
(27,616 bytes Nix store payload); the closure figure is not its executable
size.

For an offline test deployment, the complete closure was exported as
`/tmp/k230-touch-launcher-current-closure.nar.xz` (51 MiB,
SHA-256 `61681a2c898b731cd6a368497fb46871386d6f6670e63b830dee80a90b8fe802`).
A normal integrated system closure is preferred because it can share these
runtime references instead of importing them separately.

`touch-launcher-preview.svg` is a labelled source layout preview. This
validation establishes compilation, emitted menu JSON, and stubbed actions
only. It is not evidence of real glass touch, panel readability, or an
application launch on the board; those remain hardware checks in the change
tasks.
