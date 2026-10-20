{ stdenv, lib }:
stdenv.mkDerivation {
  pname = "k230-settings-status";
  version = "0.1.0";
  src = ./settings-status.c;
  dontUnpack = true;
  buildPhase = ''
    runHook preBuild
    $CC -std=c11 -O2 -Wall -Wextra -Werror "$src" -o k230-settings-status
    runHook postBuild
  '';
  installPhase = ''
    runHook preInstall
    install -Dm755 k230-settings-status $out/bin/k230-settings-status
    runHook postInstall
  '';
  meta = {
    description = "Fresh read-only handheld Settings status without interpreter startup";
    license = lib.licenses.mit;
    mainProgram = "k230-settings-status";
  };
}
