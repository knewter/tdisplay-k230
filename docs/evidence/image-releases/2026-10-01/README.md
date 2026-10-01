# GitHub development image release, 2026-10-01

Published development prerelease: [dev-coherent-65c0a71d1db5](https://github.com/knewter/tdisplay-k230/releases/tag/dev-coherent-65c0a71d1db5) at `2026-10-01T17:29:28Z`.
The final task returned 0, GitHub reports `draft=false` and `prerelease=true`, and
its lightweight Git tag points exactly at source `65c0a71d1db55b819633ba7ef9f3040a525ae3ee`.

## Source and outputs

The selected snapshot was current master `65c0a71d1db55b819633ba7ef9f3040a525ae3ee`
at the build decision. Later host-tooling/planning commits are not claimed as its
source. Target `sdImage-coherent` selects the coherent Rust shell configuration
`k230-coherent-shell` and normal vendor Xuantie kernel `6.6.36-xuantie`.
Mainline, SMP and RVV trial image targets were excluded.

- Image: `/nix/store/hl8xjdwm2ihlcs54zk5mr9zkpxk9vny9-k230-sd-image.img`
- System: `/nix/store/xphf8zb00gz9hiyqkkh399rldr2ljykb-nixos-system-nixos-26.11.20260919.20b1ddd`
- Kernel: `/nix/store/03zyl0mjsxbjyisb3lhjaxswpxm71ap6-linux-riscv64-unknown-linux-gnu-6.6.36-xuantie`
- Device tree: `/nix/store/yfda1lasmlgyappdgf6f49g7yj7m8mjd-k230-tdisplay.dtb`
- Raw image: `5,438,128,128` bytes, SHA256 `67f28f35b97bbea32c146dbb313e8fa587fb925f34faf990eaa81a101512f32d`.

Exact derivations, pinned build commands, lock-file SHA256, staging timestamp
`2026-10-01T16:59:30.612191+00:00`, sizes and digests are in `release-metadata.json`.
The source snapshot's Spec site CI passed:
<https://github.com/knewter/tdisplay-k230/actions/runs/36895050850>.
This CI is documentation/host verification, not image deployment or board proof.

## Commands and actual checks

Run from the isolated `change/repeatable-github-image-release` worktree:

```bash
python3 tools/release-image.py stage \
  --revision 65c0a71d1db55b819633ba7ef9f3040a525ae3ee \
  --directory "$HOME/tmp/k230-release-65c0a71d1db5" \
  --validation-note 'At this snapshot, the-coherent-shell-boots-the-selected-system remains open. A matching configured vendor-kernel manual trial reached root/services but did not establish accepted startup Home behavior. The restored known-good persistent board boot uses an older vendor system/kernel; newer coherent userspace has been activated temporarily on that older kernel. The local SD image build reuses exact cached target closure outputs exported from the board and independently checksum-checked before import.'
python3 tools/release-image.py publish \
  --directory "$HOME/tmp/k230-release-65c0a71d1db5"
python3 tools/release-image.py publish \
  --directory "$HOME/tmp/k230-release-65c0a71d1db5" --finish-draft
```

The exact build argv are preserved in the metadata. Stage returned 0: Nix
realized the pinned image/system/kernel/device-tree outputs with max-jobs 1,
cores 8, and registered outside-repository GC roots. The image's local U-Boot,
stage 1 packaging, rootfs ext4 and SD assembly builds completed. Its DOS layout
has a 112 MiB boot partition at 4 MiB and root partition at 128 MiB; raw stage 1
slots were populated by the builder. `stage.log` and `image-build.log` preserve
that host evidence.

A first staging attempt at `b57ba41` was deliberately interrupted before the
expensive missing userspace rebuild. Host GC had removed 36 exact target outputs,
including the `xph` system; the root coordinator exported those outputs from the
running board without changing boot/runtime state. The coordinator independently
matched the exported gzip SHA256 against the host stream; this agent imported
those exact topologically ordered paths with `gzip -dc ... | nix-store --import`,
validated `xph` and registered a GC root. Transfer: 56,197,550 bytes, SHA256
`08ecae171018d65242c7f49171dc6c2e58377f985a86ac5e4168722c47bcdbe1`.
The local image build reused those cached target outputs. This is not a claim
that every userspace dependency was freshly cross-compiled or that the resulting
SD image booted physically. Both the original and selected revisions evaluate to
the same image derivation/output.

The initial publication invocation uploaded all four assets to its owned draft
ID `401176498` but returned 1: GitHub's tag endpoint returned HTTP 404 because a
draft may have no Git tag yet. `initial-publication.log` retains this failure.
The corrected repeatable task uses authenticated list/numeric-ID lookup, records
the draft/source/asset digests locally before uploading, and provides explicit
`--finish-draft` continuation without re-uploading or replacing assets. For this
already-created transaction, the exact draft ID/tag/source were independently
inspected and its local receipt recorded with `save_draft_receipt`; that helper
is committed in `tools/release-image.py`. The receipt remained outside Git.
The explicit final command above returned 0; `finish-draft.log` preserves it.

Final verification re-evaluated the pinned source outputs, kernel version and
lock hash; checked compressed and decompressed image hashes against the exact
Nix output; checked the recorded draft identity and complete remote asset set;
downloaded all four assets and matched every byte count and SHA256; then
published and verified the actual Git tag SHA. `publication.json` preserves the
final public URLs and digests. Host safety tests passed with
`python3 tests/test_release_image.py` (9 tests), including draft-without-tag,
dirty source, staging inside Git metadata, existing release/tag refusal,
source/asset receipt mismatch, and leaving a bad remote asset draft unpublished.

## Published assets

| Asset | Bytes | SHA256 |
| --- | ---: | --- |
| `release-metadata.json` | 3,936 | `0ae73e708f84d671448681e637a53278c4ea04119034cc862eb12aa2bc07f92d` |
| `release-notes.md` | 1,394 | `1c1d86906d78bdd6cfd0018270c6b0ac0108e1a4035f2e309ff67400114f6eab` |
| `SHA256SUMS` | 280 | `c86a695f24caebb45b15039bd9930399d070e006e3569e08ea4dfd727e2bba42` |
| `tdisplay-k230-coherent-65c0a71d1db5.img.xz` | 1,036,505,548 | `14693f6ea2940053ed67332b34bc22e1d73b9deade6cb47a1d54d680b38d7b40` |

The image, NAR export, staging outputs and GC roots are outside Git under
`~/tmp/k230-release-65c0a71d1db5` and the earlier cache-transfer directory.
Only small provenance, logs and documentation are committed here. Roots are
retained after publication for coordinator use; no board or serial resource was
reserved or accessed by this agent.

## Limits and remaining physical gate

This proves local pinned image construction, release publication and downloaded
asset integrity. No QEMU boot, full-image flash, cold boot, physical Home/startup
acceptance or finger interaction was performed for this image. Existing
[matching-kernel manual boot observations](../../boot-verification/2026-10-01/README.md)
reached root/services but left initial Home behavior unaccepted; the known-good
persistent normal boot uses an older vendor system/kernel and newer userspace
was activated temporarily there. Those observations do not verify this full image.

`the-coherent-shell-boots-the-selected-system` retains that deployment and
physical proof separately. An authorized board operator can qualify the raw
artifact using the existing guarded flashing procedure:

```bash
./tools/flash.sh /nix/store/hl8xjdwm2ihlcs54zk5mr9zkpxk9vny9-k230-sd-image.img \
  /dev/disk/by-id/<operator-confirmed-card-reader>
./tools/console.py /dev/ttyACM0 --wait=3 \
  'readlink -f /run/current-system; uname -r; systemctl is-active shell.service shell-ui.service'
```

The operator must also preserve photographs/real interaction and ordinary reboot
selection proof required by that open change. These commands were not run for
this release. Its prerelease designation is deliberate.
