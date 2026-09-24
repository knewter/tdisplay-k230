# Bundled theme icon data

The coherent Rust shell now receives Yaru, Yaru-purple and Yaru-blue in
`XDG_DATA_DIRS`, plus their Humanity and hicolor inheritance. Catppuccin selects
Yaru-purple and Catppuccin Latte selects Yaru-blue. Other user-selected icon
themes still require installation; existing app-specific icons remain fallbacks.

The icon data comes from the flake-pinned nixpkgs `yaru-theme` 25.10.3 package,
upstream <https://github.com/ubuntu/yaru/tree/25.10.3>. Its declared licenses are
CC-BY-SA-4.0, GPL-3.0-or-later, LGPL-2.1-only and LGPL-3.0-only; these are upstream
art, not original project art. The architecture-independent icon trees are
copied from the native package; GTK themes, sounds and executables are excluded.
All selected Yaru trees and their relative symlinks are preserved unchanged.
Humanity and hicolor retain their pinned Nix references.

Host package proof on 2026-09-24, branch `impl/theme-icons`, base `c0ffd54c`:

```sh
nix build --no-link --print-out-paths .#handheld-theme-icons
```

PASS output `/nix/store/in3nc21zx02xiz2rdp5bpq36719x3axd-handheld-theme-icons-25.10.3`;
derivation `/nix/store/rbhinhb3943pk3y47jxbjvgmzqj373ni-handheld-theme-icons-25.10.3.drv`.
All five index files are readable; the three copied Yaru trees have no broken
symlinks. Upstream Humanity has 20 dangling aliases, preserved rather than
rewritten. The existing resolver ignores missing targets and retains fallback.
Runtime references contain only Humanity and hicolor data packages, not the
native Yaru GTK package. This is package proof; actual Rust decoder use and
physical icon/theme switching are separate evidence gates.
