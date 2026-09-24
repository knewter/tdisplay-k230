{ stdenv, pkg-config, qt6Packages }:

stdenv.mkDerivation {
  pname = "qtquick-software-probe";
  version = "0.1";
  src = ./.;
  nativeBuildInputs = [ pkg-config qt6Packages.wrapQtAppsHook ];
  buildInputs = with qt6Packages; [ qtbase qtdeclarative qtwayland ];
  preFixup = ''
    qtWrapperArgs+=(
      --set QT_QPA_PLATFORM wayland
      --set QT_QUICK_BACKEND software
      --set QSG_INFO 1
      --unset QSG_RHI_BACKEND
    )
  '';
  dontConfigure = true;
  buildPhase = ''
    runHook preBuild
    $CXX -std=c++17 -O2 -Wall -Wextra -Werror \
      main.cpp -o qtquick-software-probe \
      $($PKG_CONFIG --cflags --libs Qt6Quick Qt6Qml Qt6Gui Qt6Core)
    runHook postBuild
  '';
  installPhase = ''
    runHook preInstall
    install -Dm755 qtquick-software-probe "$out/bin/qtquick-software-probe"
    install -Dm644 Probe.qml "$out/share/qtquick-software-probe/Probe.qml"
    install -Dm644 tile.png "$out/share/qtquick-software-probe/tile.png"
    runHook postInstall
  '';
  meta.description = "Opt-in primitive Qt Quick software Wayland probe";
}
