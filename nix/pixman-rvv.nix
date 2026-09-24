# Tested CPU-vector recipe, used by the ordinary board package overlay and
# diagnostic output. Runtime hwprobe still controls RVV use; unsupported
# kernels/CPUs retain Pixman's scalar fallback.
{ pixman }:
pixman.overrideAttrs (old: {
  patches = (old.patches or [ ]) ++ [ ./patches/pixman-rvv-hwprobe.patch ];
  mesonFlags = (old.mesonFlags or [ ]) ++ [ "-Drvv=enabled" ];
})
