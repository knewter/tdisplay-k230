# Minimal CPU-Wayland video probe; default image integration remains in progress.
{ pkgs }:
let
  ffmpeg = (pkgs.ffmpeg.override {
    withHeadlessDeps = false;
    withSmallDeps = false;
    withFullDeps = false;
    withGnutls = true;
    withXml2 = true;
    withZlib = true;
    withNetwork = true;
    withV4l2M2m = true;
    withSafeBitstreamReader = true;
    buildAvcodec = true;
    buildAvdevice = true;
    buildAvfilter = true;
    buildAvformat = true;
    buildAvutil = true;
    buildSwresample = true;
    buildSwscale = true;
    buildFfmpeg = true;
    buildFfprobe = true;
  }).overrideAttrs (old: {
    configureFlags = old.configureFlags ++ [
      "--disable-everything"
      "--enable-decoder=h264,h264_v4l2m2m,aac,mp3"
      "--enable-encoder=wrapped_avframe,pcm_s16le,rawvideo"
      "--enable-parser=h264,aac,mpegaudio"
      "--enable-demuxer=mov,hls,mpegts,dash"
      "--enable-muxer=null,rawvideo"
      "--enable-protocol=file,pipe,http,https,tcp,tls,crypto,data"
      "--enable-filter=scale,crop,fps,format,aresample,anull,null,aformat,volume"
    ];
  });
  placebo = (pkgs.libplacebo.override { vulkanSupport = false; }).overrideAttrs (old: {
    buildInputs = [ pkgs.xxhash pkgs.vulkan-headers ];
    mesonAutoFeatures = "disabled";
    mesonFlags = old.mesonFlags ++ [
      "-Dvulkan=disabled" "-Dopengl=disabled" "-Dshaderc=disabled"
      "-Dlcms=disabled" "-Ddovi=disabled" "-Dlibdovi=disabled" "-Dunwind=disabled"
    ];
  });
  player = (pkgs.mpv-unwrapped.override {
    inherit ffmpeg;
    libplacebo = placebo;
    archiveSupport = false; bluraySupport = false; cacaSupport = false;
    cmsSupport = false; drmSupport = false; dvbinSupport = false;
    dvdnavSupport = false; javascriptSupport = false; openalSupport = false;
    pipewireSupport = false; pulseSupport = false; rubberbandSupport = false;
    vaapiSupport = false; vdpauSupport = false; vulkanSupport = false;
    x11Support = false; zimgSupport = false;
    waylandSupport = true; alsaSupport = true;
  }).overrideAttrs (old: {
    buildInputs = [ pkgs.bash ffmpeg pkgs.freetype pkgs.libass placebo
      pkgs.libpthread-stubs pkgs.libuchardet pkgs.alsa-lib pkgs.wayland
      pkgs.wayland-protocols pkgs.libxkbcommon ];
    patches = (old.patches or [ ]) ++ [ ./patches/mpv-k230-presentation-trace.patch ];
    postFixup = "rm -f $out/bin/umpv $out/bin/mpv_identify.sh";
    mesonFlags = old.mesonFlags ++ [ "-Dlibmpv=false" "-Dgl=disabled" "-Dvulkan=disabled" "-Dwayland=enabled" "-Dlua=disabled" ];
  });
in { inherit ffmpeg player; }
