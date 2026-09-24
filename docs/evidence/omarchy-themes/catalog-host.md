# Theme chooser catalog and preparation interface

2026-09-24; branch `impl/theme-catalog`, based on `1d2efe3f`. This checkpoint
adds a language-neutral JSON interface for a future real chooser. It does
not implement the touch UI or prove decoded wallpapers, surface rendering,
or reboot behavior. The themes proposal remains open.

The `handheld-theme-command` package now also exposes:

```sh
k230-theme list --json
k230-theme preview THEME_ID --json
k230-theme preview THEME_ID --background BACKGROUND_ID --json
k230-theme activate THEME_ID --background BACKGROUND_ID --expected-generation GENERATION --json
```

Omit `--background` in both preview and activation to use the source's
default choice. `THEME_ID`, `BACKGROUND_ID`, and `GENERATION` are returned by
the preceding commands. Activation requires the exact reviewed generation;
an updated clone or different background choice requires a new preview.
The normal `omarchy-theme-set NAME` command is unchanged.

The catalog discovers pinned built-ins, unchanged standalone clones under
`~/.config/omarchy/themes/NAME`, and collection clones with `themes/NAME`
children. It never runs Git or theme scripts. Duplicate built-in/user names
remain separately selectable. IDs survive content updates; generation IDs
still include the source content, path, selected asset, and trusted adapter
identity. Listing uses bounded directory metadata, without preparing every
theme or decoding images. Symlink children and invalid names are skipped;
the 512-entry scan limit includes ignored files and collection children.

Preview uses the existing upstream resolver and immutable staging path. Its
palette, appearance JSON path, icon selector, compatibility diagnostics and
background entries are suitable for a Rust, C or QML consumer. Background
paths refer to staged assets and each explicitly says `decode_status:
unverified`. Suffix-based image/video classification does not prove the
file's actual format or codec. The compatibility `applied` list describes
resolver inputs, not observed rendering by all shell surfaces.

Cancel requires no mutation: discard the preview response. Preview never
changes the active pointer. Apply reuses the existing prepare/commit/rollback
acknowledgement transaction and returns success only after it completes.
The active selection is reported from the committed pointer; a removed
source can leave a usable retained generation with no catalog entry ID.

Host command:

```text
python3 tests/test_theme_catalog.py
PASS: 8 tests
```

Tests exercise unchanged standalone/collection discovery, origin collisions,
cheap bounded listing, source preservation, staged asset retention after
source removal, cancel/no active mutation, opaque asset choice, stale preview
rejection, missing receiver, successful acknowledged commit and commit
rollback. The acknowledgement cases use the actual transaction with a host
fake transport; they do not prove a shell receiver or visible scene switch.

Remaining: cross-build the changed command output, consume this interface
in a real chooser, bounded thumbnail decode/cache, per-theme wallpaper
memory, user overlays/fit options, video playback, all themed surfaces and
physical touch/reboot/performance proof. No OpenSpec task is checked by this
partial backend checkpoint. The narrow package command, when the reserved
Qt build releases the slot, is `nix build .#handheld-theme-command --max-jobs
1 --cores 4 --no-link --print-out-paths`.
