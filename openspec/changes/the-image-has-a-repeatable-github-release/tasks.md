## 1. Repeatable host task

- [ ] 1.1 Implement manual stage/publish commands with exact revision evaluation, outside-Git staging, GC roots and fresh prerelease protection; prove with `python3 tests/test_release_image.py`.
- [ ] 1.2 Document the operator command and host/physical limits; prove with `python3 tools/release-image.py --help` and `openspec validate the-image-has-a-repeatable-github-release --strict`.

## 2. First development snapshot

- [ ] 2.1 Build and stage the coherent image from an exact master revision using `python3 tools/release-image.py stage --revision <full-master-sha> --directory ~/tmp/k230-release-<sha>`; its recorded `nix build <pinned-flake>#sdImage-coherent --max-jobs 1 --cores 8` proves host cross-build only.
- [ ] 2.2 Publish and verify fresh GitHub prerelease assets with `python3 tools/release-image.py publish --directory ~/tmp/k230-release-<sha>`; commit release URL, sizes, hashes and actual limits in `docs/evidence/image-releases/`. This proves publication and downloaded-byte integrity, not QEMU or hardware boot.

## 3. Closeout

- [ ] 3.1 Validate the completed change with `openspec validate the-image-has-a-repeatable-github-release --strict`; archive and sync only after committed publication evidence and all above tasks are complete. Physical image acceptance is explicitly outside this change and remains open in the coherent boot-selection proposal.
