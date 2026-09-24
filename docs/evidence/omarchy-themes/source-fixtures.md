# Direct source fixture checkpoint

Observed 2026-09-23. The acquisition tool cloned two public repositories at
exact commits into a new disposable directory; it did not run installers or
edit the source clones. The full fixture trees are **not** committed or placed
in the normal image. The manifest below records content hashes of each theme
directory, excluding Git metadata, after checkout.

| Fixture | Repository revision | Content SHA-256 | License |
| --- | --- | --- | --- |
| Built-in dark `themes/catppuccin` | [`omacom/omarchy` `28ceaae70ebac3a0edcc21f2faa77a90dc6d404c`](https://github.com/omacom/omarchy/tree/28ceaae70ebac3a0edcc21f2faa77a90dc6d404c/themes/catppuccin) | `899c8ab2737415fd27578b2d1ebdb81cf169efaa68423fa93af3d3434bee92cc` | Repository MIT `LICENSE`, SHA-256 `717ba1949502290f8e47688ae2e323acd06c8ca47aec9f7596b15f678c1af4a2`. Asset-level attribution still needs review before redistribution. |
| Built-in light `themes/catppuccin-latte` | same repository revision | `171d885c948c6c200d739229c31a9e7cfdaedb30a17a9efa1511be353e4f8a8b` | Same repository license; asset-level review still open. |
| Community `Fuchsblau` with four `shell.*.toml` section overrides | [`fuchsblau/omarchy-fuchsblau-theme` `aa7fde043ae60603c3ecc6fd6ac3b6674cacab04`](https://github.com/fuchsblau/omarchy-fuchsblau-theme/tree/aa7fde043ae60603c3ecc6fd6ac3b6674cacab04) | `0b8f4bad3dd24f6662cacb5407b2b70025d095c7ac962ff797030395cd0848a9` | Repository MIT `LICENSE`, SHA-256 `f91c73acfdd4ee9ac072d3ef30b29b000f32ab10399c42db3111b938b777d59171`. Asset-level review still open. |

```text
python3 tools/theme_sources.py acquire /tmp/k230-omarchy-theme-fixtures
  PASS: exact HEADs above; both new clone statuses empty.
python3 tests/test_omarchy_theme_sources.py
  PASS: 4 host tests for exact-revision acquisition, unchanged source clones,
  .git directory/.git file/no-Git source layouts, path escapes, content refresh,
  digest framing and exact 40-hex revision validation.
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
