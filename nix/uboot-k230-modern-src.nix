# The upstream U-Boot source the modern stage 1 builds from, pinned by the
# hash of what it unpacks to.
#
# v2026.10 (tag object 5508406582...), the newest stable release on
# 2026-10-30. It carries K230 support since v2026.01
# (arch/riscv/cpu/k230, board/canaan/k230_canmv, configs/k230_canmv_defconfig).
# Fetched from the GitHub mirror because ftp.denx.de had not published
# u-boot-2026.10.tar.bz2 on 2026-10-30 (the directory listing stops at
# 2026.07). Re-pin to the tarball once it exists if a Denx hash is wanted;
# the tree is the same.
# openspec/changes/the-board-boots-a-modern-u-boot.
{ fetchFromGitHub }:

{
  version = "2026.10";
  src = fetchFromGitHub {
    owner = "u-boot";
    repo = "u-boot";
    rev = "5508406582f6f7120dce0c4b3059819a41788db2";
    hash = "sha256-BXIpyAY+uKSohrdG4BxAo0zq4CYmh2z9rFw1jA7Yu8s=";
  };
}
