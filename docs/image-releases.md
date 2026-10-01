# Development image releases

Build and publish the current committed master using the pinned Nix flake:

```bash
python3 tools/work-status.py
revision=$(git rev-parse master)
python3 tools/release-image.py stage --revision "$revision"
python3 tools/release-image.py publish --directory "$HOME/tmp/k230-release-${revision:0:12}"
```

Requirements: Linux x86_64 host with Nix flakes enabled, Git, Python 3, xz, and
`gh` authenticated with permission to create releases in `knewter/tdisplay-k230`.
Coordinate the image build slot first. The task builds with one Nix job and eight
cores and defaults to `~/tmp`; `--directory` selects another new directory outside
any Git checkout. Tracked source must be clean. Untracked unrelated files are not
included because Nix reads the exact committed revision.

The selected target is `sdImage-coherent`: coherent Rust shell,
`k230-coherent-shell`, normal vendor Xuantie kernel. The default `sdImage` remains
the older bar-session rollback. Mainline/SMP/RVV trial targets are excluded.

Staging builds exact image/system/kernel/device-tree outputs and keeps registered
Nix GC roots in `gc-roots/`. It creates a compressed `.img.xz`, `SHA256SUMS`,
`release-metadata.json` and `release-notes.md`. Git commits contain no images or
NARs. `--tag` can select a new tag; the default is `dev-coherent-<12-char-sha>`.
`--validation-note` can add observed operator context; it cannot remove the
mandatory statement that host build and upload checks do not prove boot.

Review the notes and metadata, then run publish. Publication re-evaluates the
source and checks compressed and decompressed image hashes, creates a draft
prerelease at that exact SHA, downloads all uploaded assets and checks their
sizes and hashes, and publishes only after those checks pass. Existing release
or tag names are refused. Authentication/network failures are errors, not proof
that a name is unused. A failure after creation leaves the draft for explicit
operator inspection; the task never overwrites or automatically resumes it.

Keep the staging directory through publication. After successful upload and
inspection of `publication.json`, it can be removed to release the GC roots.
Downloaded users run `sha256sum -c SHA256SUMS`, then decompress the `.img.xz` with
`xz -d`. Flashing and physical startup/Home acceptance require separate board
proof; these releases remain development prereleases.

Host safety tests: `python3 tests/test_release_image.py`.
