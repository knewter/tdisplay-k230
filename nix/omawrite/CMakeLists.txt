# Same sources and Qt modules as upstream omawrite.pro. CMake resolves the
# build-host moc/rcc and target libraries explicitly when cross compiling.
cmake_minimum_required(VERSION 3.21)
project(omawrite LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
find_package(Qt6 REQUIRED COMPONENTS Core Gui Widgets PrintSupport Qml Quick QuickControls2 QuickDialogs2 DBus)
add_executable(omawrite src/main.cpp src/backend.cpp src/markdownhighlighter.cpp
  src/systemtheme.cpp src/backend.h src/markdownhighlighter.h src/systemtheme.h
  src/resources.qrc)
target_link_libraries(omawrite PRIVATE Qt6::Core Qt6::Gui Qt6::Widgets
  Qt6::PrintSupport Qt6::Qml Qt6::Quick Qt6::QuickControls2 Qt6::QuickDialogs2 Qt6::DBus)
install(TARGETS omawrite RUNTIME DESTINATION bin)
install(FILES pkgbuild/omawrite.svg DESTINATION share/icons/hicolor/scalable/apps)
install(FILES LICENSE fonts/OFL.txt DESTINATION share/licenses/omawrite)
# The image supplies k230-editor.desktop, preserving existing Home pins.
