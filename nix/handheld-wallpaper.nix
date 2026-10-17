# The video wallpaper's only costly dependency, built on its own: the minimal
# ffmpeg/ffprobe pair that the Rust shell's decoder child
# (nix/rust-shell-client/src/video_wallpaper.rs) runs. The decode logic itself
# is a module of the shell client crate (it shares frame_bytes and the
# appearance types), so a separate Rust crate would be a copy, not an
# isolation; what can be built and sized independently is this pair. It is the
# same store path nix/shell.nix points K230_WALLPAPER_FFMPEG/FFPROBE at.
#
# Building proves the decoder closure cross-builds. It decodes nothing and says
# nothing about CPU, memory or frame budgets (openspec task 3.3, board).
{ runCommand, callPackage }:
let
  inherit (callPackage ./video-probe.nix { }) ffmpeg;
in
runCommand "handheld-wallpaper" { passthru = { inherit ffmpeg; }; } ''
  mkdir -p $out/bin $out/share/handheld-wallpaper
  ln -s ${ffmpeg}/bin/ffmpeg $out/bin/ffmpeg
  ln -s ${ffmpeg}/bin/ffprobe $out/bin/ffprobe
  cat > $out/share/handheld-wallpaper/environment <<'ENV'
  K230_WALLPAPER_FFMPEG=@out@/bin/ffmpeg
  K230_WALLPAPER_FFPROBE=@out@/bin/ffprobe
  ENV
  sed -i -e 's/^  //' -e "s|@out@|$out|" $out/share/handheld-wallpaper/environment
''
