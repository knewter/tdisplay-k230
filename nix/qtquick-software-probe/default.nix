{ stdenv, cmake, qt6Packages, buildPackages }:

stdenv.mkDerivation {
  pname = "qtquick-software-probe";
  version = "0.1";
  src = ./.;
  # Host-side Qt tools (QmlTools, ShaderTools) are needed by the target CMake packages.
  nativeBuildInputs = [ cmake qt6Packages.wrapQtAppsHook buildPackages.qt6Packages.qtdeclarative buildPackages.qt6Packages.qtshadertools ];
  buildInputs = with qt6Packages; [ qtbase qtdeclarative qtwayland ];
  # The wrapper fixes the renderer: software scene graph on the Wayland QPA,
  # scene-graph info logging, and no inherited RHI backend forcing.
  preFixup = ''
    qtWrapperArgs+=(
      --set QT_QPA_PLATFORM wayland
      --set QT_QUICK_BACKEND software
      --set QSG_INFO 1
      --unset QSG_RHI_BACKEND
    )
  '';
  meta.description = "Opt-in primitive Qt Quick software Wayland probe";
}
