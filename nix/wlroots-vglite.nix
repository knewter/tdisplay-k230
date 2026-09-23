{ wlroots_0_20 }:

# Opt-in checkpoint: WLR_RENDERER=vglite selects a complete Pixman fallback.
# It validates selection and preserves the existing DRM owner; it makes no
# VG-Lite, dma-buf, scanout, or performance claim.
wlroots_0_20.overrideAttrs (old: {
  pname = "wlroots-vglite-full-pass-fallback";
  patches = (old.patches or []) ++ [ ./patches/wlroots-vglite-full-pass-pixman.patch ];
  passthru = (old.passthru or {}) // {
    k230VgliteStatus = "full-pass-pixman-fallback-no-gpu-claim";
  };
})
