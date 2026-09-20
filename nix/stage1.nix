# Stage 1: the boot chain that runs before our kernel.
#
#   BootROM -> U-Boot SPL (+ DDR PMU training firmware)
#           -> U-Boot 2022.10 -> OpenSBI 1.4 -> our kernel
#
# THE BINARIES ARE NOT IN GIT. There are two ways to get them, and both end
# at the same bytes:
#
#   locally   ./tools/gen-stage1.sh  builds them from the K230 Linux SDK in a
#             container and drops them in firmware/stage1/, which is
#             gitignored. Because a flake only sees git-tracked files, a
#             local build is NOT picked up automatically -- point at it
#             explicitly and evaluate impurely:
#
#                 K230_STAGE1_DIR=$PWD/firmware/stage1 \
#                   nix build --impure .#sdImage
#
#             That is deliberate. Silently preferring untracked local
#             binaries over a pinned release would make a build depend on
#             what happens to be lying in your working tree.
#
#   released  .github/workflows/stage1.yml builds the same thing in CI and
#             publishes stage1.tar.gz to a release. `release` below fetches
#             it by hash, so a fresh clone needs no Docker, no 284 MB SDK
#             checkout and no 1.9 GB vendor toolchain.
#
# A local build wins when present, so a developer testing a firmware change
# is never silently served the released copy. Everything carries a hash, so
# neither path can substitute different bytes unnoticed.
#
# What is and is not from source: U-Boot, its SPL and OpenSBI are all
# compiled from published source. The DDR PHY training firmware inside SPL
# is a genuine binary blob with no source we have found, and the build runs
# Canaan's stripped `k230_priv_gzip` to compress U-Boot. Both are tracked in
# docs/blob-inventory.md rather than glossed.
{ lib, fetchurl, runCommand, stdenvNoCC }:

let
  files = [ "fn_u-boot-spl.bin" "fn_ug_u-boot.bin" "env.env" "fw_jump.bin" "fw_jump_add_uboot_head.bin" ];

  # Only set under --impure; empty otherwise.
  envDir = builtins.getEnv "K230_STAGE1_DIR";
  localDir = if envDir == "" then null else /. + envDir;
  haveLocal = localDir != null
    && builtins.all (f: builtins.pathExists (localDir + "/${f}")) files;

  # Set once .github/workflows/stage1.yml has published a release. Until
  # then a fresh clone must run tools/gen-stage1.sh, and the error below
  # says so rather than failing obscurely.
  release = null;
  # release = fetchurl {
  #   url = "https://github.com/knewter/tdisplay-k230/releases/download/stage1-<sha>/stage1.tar.gz";
  #   hash = "sha256-...";
  # };

  fromRelease = runCommand "k230-stage1" { } ''
    mkdir -p $out && tar -xzf ${release} -C $out
  '';

  src =
    if haveLocal then builtins.path { path = localDir; name = "k230-stage1-local"; }
    else if release != null then fromRelease
    else throw ''
      Stage-1 firmware is missing and no release is pinned yet.

      Build it locally, then point at it:
          ./tools/gen-stage1.sh
          K230_STAGE1_DIR=$PWD/firmware/stage1 nix build --impure .#sdImage

      Or pin a release in nix/stage1.nix once the "stage 1" workflow has
      published one. The binaries are deliberately not committed.
    '';
in
{
  inherit src;
  source =
    if haveLocal then "local build (K230_STAGE1_DIR=${envDir})"
    else if release != null then "published release"
    else "NONE — run tools/gen-stage1.sh, or pin a release in nix/stage1.nix";

  # Raw offsets on the card, from the SDK's genimage_cfg/genimage.cfg.
  layout = {
    spl = { file = "fn_u-boot-spl.bin"; offsets = [ 1048576 1572864 ]; };
    uboot = { file = "fn_ug_u-boot.bin"; offsets = [ 2097152 ]; };
    env = { file = "env.env"; offsets = [ 3145728 3276800 ]; };
  };

  vendored = true;
  builtFromSource = true;   # by us, from the SDK -- see the header

  provenance = {
    sdk = "kendryte/k230_linux_sdk";
    branch = "dev";
    boardConfig = "k230_canmv_v3_defconfig";
    opensbi = "1.4 + Canaan T-Head overlay, FW_TEXT_START=0";
    uboot = "2022.10, Canaan fork";
  };
}
