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

The initial package build passed before follow-up input and strip fixes; its
measurements below are retained only as a historical record. The corrected
source requires the replacement build tracked in `tasks.md` before this is
current validation. The initial package output was
`/nix/store/07w3dmc4d79c86cjafc2n28xj6khhnlg-k230-touch-launcher`; its complete
closure is 192.7 MiB, including the existing RISC-V Bash, glibc, and Wayland
runtime graph. The native RISC-V launcher ELF itself is 34,265,384 bytes.

For an offline test deployment, the complete closure was exported as
`/tmp/k230-touch-launcher-07w3dmc-closure.nar.xz` (51 MiB,
SHA-256 `01a9a9ad273a3f71325c6576c9d3577d0503d8abb393752faf3dd43ef6e5a007`).
A normal integrated system closure is preferred because it can share these
runtime references instead of importing them separately.

`touch-launcher-preview.svg` is a labelled source layout preview. This
validation establishes compilation, emitted menu JSON, and stubbed actions
only. It is not evidence of real glass touch, panel readability, or an
application launch on the board; those remain hardware checks in the change
tasks.
