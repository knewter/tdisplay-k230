# The mainline Linux SOURCE, unpatched. Parallel to nix/kernel-src.nix, which
# pins the vendor Xuantie tree the shipped image actually boots.
#
# openspec/changes/the-board-runs-a-mainline-kernel: this pin exists so a
# mainline cross-build and forward-ported patches have somewhere to live
# while mainline Canaan K230 support is still incomplete (no display, touch,
# audio, RTC, PMU/power-key, thermal, ADC, PWM, GPIO or crypto driver; no
# merged SD/MMC driver; a USB PHY driver merged but not yet wired into
# k230.dtsi). It does NOT feed nix/kernel.nix, nix/device-tree.nix, or any
# nixosConfigurations output -- the shipped image is unaffected by this file
# existing.
#
# Why v7.3-rc5, not a stable release: basic Canaan K230 support (ARCH_CANAAN,
# PINCTRL_K230, RESET_K230, COMMON_CLK_K230, arch/riscv/boot/dts/canaan/
# k230.dtsi + k230-canmv.dts + k230-evb.dts) merged for the v7.3 merge
# window. Checked directly: `git show v7.2:arch/riscv/boot/dts/canaan/`
# lists only K210/Sipeed files, no k230.dtsi; the same listing against
# `master` (currently v7.3-rc5) has it. v7.2.8 is kernel.org's current
# "latest stable" (2026-09-25) and does not carry K230 at all; there is no
# tagged stable release with K230 support yet, so this pins the newest
# available -rc that has it rather than an unreleased "latest" moving
# target. Re-pin to the eventual v7.3 stable tag once it exists.
{ fetchFromGitHub }:

fetchFromGitHub {
  owner = "torvalds";
  repo = "linux";
  # v7.3-rc5, dereferenced tag -> commit (`git ls-remote --tags`,
  # `refs/tags/v7.3-rc5^{}`), 2026-09-29.
  rev = "72d3fcf802c45d00b300f25b848a93c3a2bd7c7e";
  hash = "sha256-NrTyfot19uJ1SulXU98z2V+leOjjjLmoueX8pnyvn+o=";
}
