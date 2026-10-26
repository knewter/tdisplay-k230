{ lib, runCommand, buildPackages }:

# Distinct launcher icons for the handheld's own apps. The four sgt-puzzles
# picks reuse the build platform's package: its icons are screenshots of the
# built games, which the riscv64 build cannot run to make. The icons are
# architecture-independent data, so they are copied under unique names and the
# curated desktop entries point at those names. The other icons are drawn here
# as plain flat SVGs (rounded plate, one glyph) for apps without any.
runCommand "handheld-app-icons" {
  meta = {
    description = "Launcher icons for the handheld's games and terminal apps";
    platforms = lib.platforms.all;
  };
} ''
  puzzles=${buildPackages.sgt-puzzles}/share/icons/hicolor
  for puzzle in net samegame sixteen fifteen; do
    found=0
    for icon in "$puzzles"/*/apps/$puzzle.png; do
      size="$(basename "$(dirname "$(dirname "$icon")")")"
      install -Dm644 "$icon" "$out/share/icons/hicolor/$size/apps/k230-puzzle-$puzzle.png"
      found=1
    done
    if [ "$found" = 0 ]; then
      echo "no sgt-puzzles icon for $puzzle" >&2
      exit 1
    fi
  done
  install -Dm644 ${./k230-2048.svg} $out/share/icons/hicolor/scalable/apps/k230-2048.svg
  install -Dm644 ${./k230-nethack.svg} $out/share/icons/hicolor/scalable/apps/k230-nethack.svg
  install -Dm644 ${./k230-clock.svg} $out/share/icons/hicolor/scalable/apps/k230-clock.svg
  install -Dm644 ${./k230-timer.svg} $out/share/icons/hicolor/scalable/apps/k230-timer.svg
''
