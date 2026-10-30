{ stdenv, cmake, qt6Packages, buildPackages }:

stdenv.mkDerivation {
  pname = "qtquick-software-probe";
  version = "0.1";
  src = ./.;
  nativeBuildInputs = [ cmake qt6Packages.wrapQtAppsHook ];
  # The target Qt CMake packages need the build platform's Qt tools. They are passed
  # as paths, not as inputs, so the qtbase hook does not see two Qt ABIs.
  cmakeFlags = let host = buildPackages.qt6Packages; in [
    "-DQT_HOST_PATH=${host.qtbase}"
    "-DQt6QmlTools_DIR=${host.qtdeclarative.dev}/lib/cmake/Qt6QmlTools"
    "-DQt6ShaderTools_DIR=${host.qtshadertools.dev}/lib/cmake/Qt6ShaderTools"
  ];
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
