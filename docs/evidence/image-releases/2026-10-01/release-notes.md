Development snapshot of the coherent Rust handheld shell with the normal vendor Xuantie kernel 6.6.36-xuantie.

Source: `65c0a71d1db55b819633ba7ef9f3040a525ae3ee`
Target: `sdImage-coherent` / `k230-coherent-shell`
System: `/nix/store/xphf8zb00gz9hiyqkkh399rldr2ljykb-nixos-system-nixos-26.11.20260919.20b1ddd`
Kernel: `/nix/store/03zyl0mjsxbjyisb3lhjaxswpxm71ap6-linux-riscv64-unknown-linux-gnu-6.6.36-xuantie`

Validation: Host cross-build and uploaded-byte checks only. This exact full image has not been flashed or accepted on physical hardware and has no QEMU boot proof. Fresh-image startup/Home physical acceptance must be established separately.

At this snapshot, the-coherent-shell-boots-the-selected-system remains open. A matching configured vendor-kernel manual trial reached root/services but did not establish accepted startup Home behavior. The restored known-good persistent board boot uses an older vendor system/kernel; newer coherent userspace has been activated temporarily on that older kernel. The local SD image build reuses exact cached target closure outputs exported from the board and independently checksum-checked before import.

Download the `.img.xz`, `SHA256SUMS` and `release-metadata.json`. Run `sha256sum -c SHA256SUMS` in the download directory, then `xz -d <image>.img.xz` to obtain the raw SD image. Mainline, SMP and RVV trial image targets are excluded.
