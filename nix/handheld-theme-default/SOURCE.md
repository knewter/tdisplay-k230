# Pinned Omarchy built-in themes

The Nix source is the immutable `omacom/omarchy` revision
`28ceaae70ebac3a0edcc21f2faa77a90dc6d404c`, fetched by
`fetchFromGitHub` with fixed-output hash
`sha256-wxvTIkTGJCwQI65KxAErhXhTrnpbWgIvNfDLG4pfJKs=`. The package copies
`themes/catppuccin` and `themes/catppuccin-latte` unchanged. These are direct
Omarchy collection members, including original static backgrounds and preview
assets. Their 20 file hashes are in `source-inventory.json`; their framed tree
digests are `72e8f8f39a1209893b30b651fece6c1d1ce47ec643df9e596c7cd282ea97d4c6`
and `11ea23e5a4659b09ecda0658dd86921489d6f536b86ffa60af2f601912a70cdc`.
The upstream repository `LICENSE` is included in the package (MIT).

The fresh-home default is a derived Catppuccin generation with the original
`backgrounds/2-waves.webp` selected. Its `report.json` and `appearance.json`
are committed as `bundled-*.json`. The 24-character generation identity is the
first 24 hex digits of SHA-256 over sorted JSON containing the prior palette
generation ID, pinned source revision and framed tree digest, selected
background path, and format version 1. This identity describes our bundled
default; later `k230-theme` activation uses its own coordinator identity.

The previous palette-only generation remains in the package as a recovery
default. Its `default-*.json`, pinned `colors.toml`, `icons.theme`, and terminal
fragments remain available. The new default does not imply video playback,
full background previews, or device performance proof.
