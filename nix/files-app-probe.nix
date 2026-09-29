# Scratch probe, not wired into flake.nix: cross-build feasibility check for
# candidate file managers (portfolio-filemanager, nautilus) on riscv64.
# Not part of the shipped configuration.
let
  nixpkgs = builtins.fetchTree {
    type = "github";
    owner = "NixOS";
    repo = "nixpkgs";
    rev = "20b1ddd1aa5ace70c9468305030aa4f9ef79671b";
  };
  pkgs = import nixpkgs { system = "x86_64-linux"; };
  pkgsCross = pkgs.pkgsCross.riscv64;
in
{
  portfolio = pkgsCross.portfolio-filemanager;
  nautilus = pkgsCross.nautilus;
  # Native (build-platform) copies of the same packages, for fast
  # host-rendered theming screenshots -- a distinct, faster-to-obtain
  # evidence class from the riscv64 cross-build above. Never shipped to the
  # board.
  portfolioNative = pkgs.portfolio-filemanager;
  nautilusNative = pkgs.nautilus;
  yaruThemeNative = pkgs.yaru-theme;
  gsettingsSchemasNative = pkgs.gsettings-desktop-schemas;
  xvfbRunNative = pkgs.xvfb-run;
  imagemagickNative = pkgs.imagemagick;
  schemaDirCheck = pkgs.writeText "schema-dir-check"
    (pkgsCross.glib.getSchemaDataDirPath pkgsCross.gsettings-desktop-schemas);
}
