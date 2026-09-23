{ wlroots_0_20, vgliteProbe }:

# Opt-in checkpoint: WLR_RENDERER=vglite selects the guarded VG-Lite route.
# Every unsupported or failed pass is replayed completely through Pixman.
wlroots_0_20.overrideAttrs (old: {
  pname = "wlroots-vglite-full-pass-fallback";
  patches = (old.patches or []) ++ [ ./patches/wlroots-vglite-full-pass-pixman.patch ./patches/wlroots-vglite-meson.patch ];
  buildInputs = (old.buildInputs or []) ++ [ vgliteProbe ];
  postPatch = (old.postPatch or "") + ''
    mkdir -p render/vglite include/wlr/render
    cp ${./wlroots-vglite/renderer.c} render/vglite/renderer.c
    cp ${./wlroots-vglite/meson.build} render/vglite/meson.build
    cp ${./wlroots-vglite/include/wlr/render/vglite.h} include/wlr/render/vglite.h
    substituteInPlace render/vglite/meson.build \
      --replace-fail '@VGLITE_INCLUDE@' '${vgliteProbe}/include' \
      --replace-fail '@VGLITE_LIB@' '${vgliteProbe}/lib'
  '';
  passthru = (old.passthru or {}) // {
    k230VgliteStatus = "real-rgb565-rect-shm-upload-route-with-pixman-fallback";
  };
})
