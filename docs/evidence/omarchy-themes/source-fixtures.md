# Direct source fixture checkpoint

Observed 2026-09-23. The acquisition tool cloned two public repositories at
exact commits into a new disposable directory; it did not run installers or
edit the source clones. The full fixture trees are **not** committed or placed
in the normal image. The manifest below records content hashes of each theme
directory, excluding Git metadata, after checkout.

| Fixture | Repository revision | Content SHA-256 | License |
| --- | --- | --- | --- |
| Built-in dark `themes/catppuccin` | [`omacom/omarchy` `28ceaae70ebac3a0edcc21f2faa77a90dc6d404c`](https://github.com/omacom/omarchy/tree/28ceaae70ebac3a0edcc21f2faa77a90dc6d404c/themes/catppuccin) | `d8fdd69348ebe8eb7ec77c4bccd3ad3c5a52b0be2e6fbb04f91d321af47301f0` | Repository MIT `LICENSE`, SHA-256 `717ba1949502290f8e47688ae2e323acd06c8ca47aec9f7596b15f678c1af4a2`. Asset-level attribution still needs review before redistribution. |
| Built-in light `themes/catppuccin-latte` | same repository revision | `e8fef3c4fbe616ace82f90c190af526b887963ae1edda6f583554080c4b02689` | Same repository license; asset-level review still open. |
| Community `Fuchsblau` with four `shell.*.toml` section overrides | [`fuchsblau/omarchy-fuchsblau-theme` `aa7fde043ae60603c3ecc6fd6ac3b6674cacab04`](https://github.com/fuchsblau/omarchy-fuchsblau-theme/tree/aa7fde043ae60603c3ecc6fd6ac3b6674cacab04) | `3de9c6c83493757b9b85f780a2ee1ce5cd6af480c066097cc9bdbf0bfaf179a8` | Repository MIT `LICENSE`, SHA-256 `f91c73acfdd4ee9ac072d3ef30b29b000f32ab10399c42db3111b938b777d59171`. Asset-level review still open. |

```text
python3 tools/theme_sources.py acquire /tmp/k230-omarchy-theme-fixtures
  PASS: exact HEADs above; both new clone statuses empty.
python3 tests/test_omarchy_theme_sources.py
  PASS: 3 host tests for exact-revision acquisition, unchanged source clones,
  .git directory/.git file/no-Git source layouts, path escapes, and content refresh.
python3 tests/test_omarchy_theme_resolution.py
  PASS: 4 host tests against the byte-verified pinned upstream helpers for
  aliases, explicit ANSI/selection/custom values, mode precedence and fallback,
  mix/gradient expansion, full-file and section-replacement precedence.
```

The content digests are fixture identities, not proof of image licensing,
physical appearance, live activation, or compatibility of all arbitrary
themes. Acquiring a pinned source does not pull or modify a person's existing
checkout. Subsequent update detection must hash current source bytes rather
than trust Git HEAD alone.
