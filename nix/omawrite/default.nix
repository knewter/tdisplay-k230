{ lib, stdenv, fetchFromGitHub, cmake, qt6Packages, pkgsBuildBuild }:

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
  nativeBuildInputs = [ cmake qt6Packages.wrapQtAppsHook ];
  cmakeFlags = lib.optionals (stdenv.buildPlatform != stdenv.hostPlatform) [
    "-DQt6QmlTools_DIR=${pkgsBuildBuild.qt6.qtdeclarative}/lib/cmake/Qt6QmlTools"
    "-DQt6QuickTools_DIR=${pkgsBuildBuild.qt6.qtdeclarative}/lib/cmake/Qt6QuickTools"
  ];
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
