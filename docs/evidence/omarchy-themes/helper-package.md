# Pinned helper package: host and cross-build checkpoint

Observed 2026-09-23, branch `implement/omarchy-themes`, based on icon-landed
master `fd8fcf32`. Upstream helper/template source is Omarchy Quattro
`28ceaae70ebac3a0edcc21f2faa77a90dc6d404c`, with byte hashes and the
single path patch documented in
[`nix/omarchy-theme-tools/SOURCE.md`](../../../nix/omarchy-theme-tools/SOURCE.md).

Commands and outcomes:

```text
python3 tests/test_omarchy_theme_tools.py
  PASS: 2 host tests; original-byte manifest and patched-versus-original
  generated tree parity under disposable staging paths.
nix build .#omarchy-theme-tools --max-jobs 1 --cores 4 --no-link --print-out-paths
  PASS: /nix/store/2l3cmjv3i2yzcnibx2sjjm6j5nzwqblf-omarchy-theme-tools-28ceaae7
nix path-info -S /nix/store/2l3cmjv3i2yzcnibx2sjjm6j5nzwqblf-omarchy-theme-tools-28ceaae7
  66,767,856 bytes closure size
nix-store -q --requisites /nix/store/2l3cmjv3i2yzcnibx2sjjm6j5nzwqblf-omarchy-theme-tools-28ceaae7 | wc -l
  17 store paths
nix hash path /nix/store/2l3cmjv3i2yzcnibx2sjjm6j5nzwqblf-omarchy-theme-tools-28ceaae7
  sha256-/GTMIJlNG3cgIGgN1EtKX7N2EbwSs/q79s+gtv4XwIM=
```

This proves package construction and host helper output parity. It does not
prove source checkout acquisition, theme activation, installed client
integration, board appearance, performance, or reboot persistence. The package
is an opt-in flake output and is not in the normal image closure.
