{ lib, rustPlatform, fetchFromGitHub }:

# ttfx: a Rust port of terminaltexteffects (MIT), pinned to the v0.5.1 tag.
# The exhibition (nix/exhibition) pipes a committed K230 banner into it.
# Cargo.lock is committed beside this file (copied from the tag) so the
# build needs no import-from-derivation; cargoSetupHook fails the build if it
# ever differs from the lock inside the source. Licence text: ./ttfx/LICENSE
# and ./ttfx/NOTICE are installed under share/doc/ttfx.
rustPlatform.buildRustPackage {
  pname = "ttfx";
  version = "0.5.1";
  src = fetchFromGitHub {
    owner = "omacom-io";
    repo = "ttfx";
    rev = "v0.5.1"; # commit 14ed274
    hash = "sha256-/cECljrthspJsg6fgWMm4QIv8V3FJLuP/pbZoRKFVAc=";
  };
  cargoLock.lockFile = ./ttfx/Cargo.lock;
  # The test suite compares against an upstream clone fetched on demand and
  # a riscv64 test binary cannot run on the build host.
  doCheck = false;
  postInstall = ''
    install -Dm644 ${./ttfx/LICENSE} $out/share/doc/ttfx/LICENSE
    install -Dm644 ${./ttfx/NOTICE} $out/share/doc/ttfx/NOTICE
  '';
  meta = {
    description = "Terminal text effects, a Rust port of terminaltexteffects";
    homepage = "https://github.com/omacom-io/ttfx";
    license = lib.licenses.mit;
    mainProgram = "ttfx";
  };
}
