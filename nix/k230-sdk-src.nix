# Canaan's K230 Linux SDK, pinned by commit, fetched sparsely.
#
# Stage 1 is vanilla U-Boot 2022.10 and vanilla OpenSBI 1.4 with Canaan's
# changes rsynced over the top: not a patch series, a directory. The SDK's
# own build says so -- `UBOOT_OVERLAY_DIRS` at buildroot-overlay/boot/uboot/
# uboot.mk:581 and `OPENSBI_OVERLAY_DIRS` at the end of
# buildroot-overlay/boot/opensbi/opensbi.mk are each one `rsync -a`. This
# derivation fetches only what those two overlays need plus the default
# U-Boot environment, so a build of stage 1 does not pull 235 MB of vendor
# rootfs packages -- several of which carry firmware blobs this project
# lists in docs/blob-inventory.md §B and does not want in its closure.
#
# Every file this fetch produces is text. Checked 2026-09-22 with `file
# --mime-type` over the two overlay trees and the env directory: 264 files,
# 264 text/*. tools/blob-scan.py is pointed at the same commit to keep it
# that way.
#
# BSD-2-Clause, per the SDK's LICENSE.
{ fetchFromGitHub }:

fetchFromGitHub {
  owner = "kendryte";
  repo = "k230_linux_sdk";
  # `dev` on 2026-09-20; firmware/stage1/PROVENANCE.txt records the same
  # commit for the Docker build this replaces.
  rev = "1104236db4d1e47873bd68924f912747b820228c";
  sparseCheckout = [
    "buildroot-overlay/boot/uboot"
    "buildroot-overlay/boot/opensbi"
    "buildroot-overlay/board/canaan/k230-soc/env"
    "buildroot-overlay/configs"
  ];
  hash = "sha256-P3XkeyJPkpe/h0oHAHCiz8a0VXofw1zsQ3YSa6UcG8w=";
}
