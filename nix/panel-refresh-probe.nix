# Read-only DRM vblank sampler for the-card-deck-still-misses-its-frame-budget.
# See panel-refresh-probe.c for exactly which ioctls it issues (GET* and a
# non-signalling, non-flip WAIT_VBLANK only) and
# docs/evidence/card-shell/frame-budget/analysis.md for why.
#
# Standalone diagnostic, same pattern as c908-bitmanip-probe.nix: never in the
# normal image closure. The coordinator pushes the built binary to a running
# board with tools/push-file.py (an 11s transfer, like the DTB push this
# project already uses for candidate device-tree values) rather than
# rebuilding and reflashing the whole image for a one-off measurement.
{ stdenv, pkg-config, libdrm }:
stdenv.mkDerivation {
  pname = "k230-panel-refresh-probe";
  version = "0.1";
  dontUnpack = true;
  nativeBuildInputs = [ pkg-config ];
  buildInputs = [ libdrm ];
  buildPhase = ''
    runHook preBuild
    $CC -std=c11 -O2 -Wall -Wextra -Werror \
      $($PKG_CONFIG --cflags libdrm) \
      ${./panel-refresh-probe.c} $($PKG_CONFIG --libs libdrm) \
      -o panel-refresh-probe
    runHook postBuild
  '';
  installPhase = ''
    runHook preInstall
    install -Dm755 panel-refresh-probe $out/bin/panel-refresh-probe
    runHook postInstall
  '';
  meta.description = "Read-only DRM WAIT_VBLANK sampler, no modeset/flip/commit issued";
}
