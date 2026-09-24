# Cached selection and pinned default checkpoint

Observed 2026-09-23. The opt-in launcher trial loads the selected generation
from the private `current/active` pointer before its first Wayland scene. If
that cached generation is absent or invalid, it keeps the immutable Nix
Catppuccin palette subset; the normal option remains disabled. A fresh home
needs no writable state to display that default. The command can select
`catppuccin` by name from the same pinned data files. No theme source checkout
is changed or refreshed implicitly.

The default includes exact upstream `colors.toml`, `icons.theme` and MIT
license bytes at Omarchy commit `28ceaae70ebac3a0edcc21f2faa77a90dc6d404c`.
[`SOURCE.md`](../../../nix/handheld-theme-default/SOURCE.md) records per-file
hashes. Its derived report and installed source are deliberately a
palette/icon-selector subset: upstream media is not redistributed or implied
to work. `current/theme`, `current/theme.name` and `current/background` are
stable relative symlinks through the atomic `active` pointer after a selection;
`background` may be dangling when a source has no background. Existing
nonmatching files at those names are refused, not overwritten. A prepared
generation remains usable after its source clone is removed. A broken
`active` pointer can be replaced by a later valid selection.

```text
python3 tests/test_handheld_theme_default.py
  PASS: exact file hashes, derived generation ID, parsed palette and icon
  selector, source revision and explicit no-media report.
python3 tests/test_omarchy_theme_activation.py
  PASS: 8 host tests including stable public paths after clone removal.
python3 tests/test_omarchy_theme_transaction.py
  PASS: 13 host tests including incompatible path refusal, in-cache broken
  pointer replacement, and foreign dangling-pointer refusal.
python3 tests/test_shell_appearance_receiver.py
  PASS: 5 native host socket tests including fresh-home startup, reopened
  selected palette and unavailable cached selection fallback.
python3 tools/omarchy-theme-set catppuccin --builtins nix/handheld-theme-default --tools nix/omarchy-theme-tools/upstream --state-root /tmp/k230-omarchy-default-prep-check --prepare-only
  PASS: 56 resolved keys, Yaru-purple selector, no background candidates.
nix build .#handheld-theme-default --max-jobs 1 --cores 4 --no-link --print-out-paths
  PASS: /nix/store/qlrciqqmh3s80rc755p9dgm3plw1w1r4-handheld-theme-default-28ceaae7
nix build .#handheld-theme-command --max-jobs 1 --cores 4 --no-link --print-out-paths
  PASS: /nix/store/pd1igazqim6rzs515vbnq0ij11yn4nzj-handheld-theme-command-0.1
nix build .#touch-launcher --max-jobs 1 --cores 4 --no-link --print-out-paths
  PASS: /nix/store/5dzy6jj37xm7a1v40j9fdrmc7q4ih7dp-k230-touch-launcher
nix eval --json .#nixosConfigurations.k230.config.k230.shell.themeReceiverTrial
  PASS: false in the normal board configuration.
nix eval --impure --json --expr 'let f = builtins.getFlake (toString ./.); c = f.nixosConfigurations.k230.extendModules { modules = [ { k230.shell.themeReceiverTrial = true; } ]; }; in { enabled = c.config.k230.shell.themeReceiverTrial; installed = builtins.any (p: (p.pname or "") == "handheld-theme-command") c.config.environment.systemPackages; launcher = toString c.config.k230.shell.launcher; }'
  PASS: enabled=true, installed=true; the opt-in launcher wrapper is a new
  evaluated store path. No whole image or physical boot was built or observed.
```

Host startup and cache tests are not reboot or panel evidence. Full Omarchy
media, authored Foot overrides, cross-surface tokens, old real-directory
`current/` migration and physical persistence remain open. Tasks 2.1 and 2.3
are not checked from this bounded checkpoint.
