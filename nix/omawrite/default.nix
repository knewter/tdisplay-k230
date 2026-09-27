{ lib, stdenv, fetchFromGitHub, cmake, qt6Packages }:

stdenv.mkDerivation {
  pname = "omawrite";
  version = "0-unstable-2026-08-07";
  src = fetchFromGitHub {
    owner = "omacom";
    repo = "omawrite";
    rev = "8f98892b26768236b2c20f4e637cf4b102d898bf";
    hash = "sha256-yS3GOL/kc03qx4naWzUdSZwAYxMuCjvrgmhexpwjsfA=";
  };
  patches = [ ./handheld.patch ];
  nativeBuildInputs = [ cmake qt6Packages.wrapQtAppsHook qt6Packages.qtdeclarative ];
  postPatch = ''
    cp ${./CMakeLists.txt} CMakeLists.txt
    cp ${./HandheldFileDialog.qml} src/HandheldFileDialog.qml
  '';
  buildInputs = with qt6Packages; [ qtbase qtdeclarative qtwayland qtsvg ];
  enableParallelBuilding = true;
  preFixup = ''
    qtWrapperArgs+=(
      --set QT_QPA_PLATFORM wayland
      --set QT_QUICK_BACKEND software
      --unset QSG_RHI_BACKEND
    )
  '';
  meta = {
    description = "Omawrite Markdown editor adapted for the handheld";
    homepage = "https://github.com/omacom/omawrite";
    license = with lib.licenses; [ mit ofl ];
    platforms = lib.platforms.linux;
    mainProgram = "omawrite";
  };
}
