{ stdenv, cmake, qt6Packages, buildPackages }:

let
  host = buildPackages.qt6Packages;
  shaderToolsTools = "${host.qtshadertools}/lib/cmake/Qt6ShaderToolsTools";
  # The pinned nixpkgs cross build of qtdeclarative configures with
  # "Qt Quick support: no" ("not built due to not finding the qtshadertools
  # 'qsb' tool", docs/evidence/qtquick/qt-cross-build.md). Handing it the build
  # platform's Qt6ShaderToolsTools is the one bounded correction; nothing else
  # in the closure is changed.
  qtdeclarative = qt6Packages.qtdeclarative.overrideAttrs (old: {
    cmakeFlags = (old.cmakeFlags or [ ]) ++ [ "-DQt6ShaderToolsTools_DIR=${shaderToolsTools}" ];
  });
in
stdenv.mkDerivation {
  pname = "qtquick-software-probe";
  version = "0.1";
  src = ./.;
  nativeBuildInputs = [ cmake qt6Packages.wrapQtAppsHook ];
  buildInputs = [ qt6Packages.qtbase qtdeclarative qt6Packages.qtwayland ];
  # The target Qt CMake packages need the build platform's Qt tools. They are passed
  # as paths, not as inputs, so the qtbase hook does not see two Qt ABIs.
  cmakeFlags = [
    "-DQT_HOST_PATH=${host.qtbase}"
    "-DQt6QmlTools_DIR=${host.qtdeclarative}/lib/cmake/Qt6QmlTools"
    "-DQt6ShaderTools_DIR=${host.qtshadertools}/lib/cmake/Qt6ShaderTools"
    "-DQt6ShaderToolsTools_DIR=${shaderToolsTools}"
  ];
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
