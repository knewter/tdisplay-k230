{ stdenv, cmake, qt6Packages }:

stdenv.mkDerivation {
  pname = "qtquick-software-probe";
  version = "0.1";
  src = ./.;
  nativeBuildInputs = [ cmake qt6Packages.wrapQtAppsHook ];
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
