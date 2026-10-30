# ttfx v0.5.1 with the no_std engine patch (nix/ttfx-nostd/ttfx-nostd.patch).
# The patch keeps the std CLI building and passing its own tests (default
# features) and adds `--no-default-features --features nostd`: the animation
# engine on core + alloc, with hashbrown and libm.  Written to be sent upstream.
{ applyPatches, fetchFromGitHub }:

applyPatches {
  name = "ttfx-nostd-src-0.5.1";
  src = fetchFromGitHub {
    owner = "omacom-io";
    repo = "ttfx";
    rev = "v0.5.1"; # commit 14ed274, the revision nix/ttfx.nix pins
    hash = "sha256-/cECljrthspJsg6fgWMm4QIv8V3FJLuP/pbZoRKFVAc=";
  };
  patches = [ ./ttfx-nostd.patch ];
}
