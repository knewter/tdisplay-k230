# Opt-in CPU-vector trial. Runtime hwprobe still controls RVV use; unsupported
# kernels/CPUs retain Pixman's scalar fallback. Default package set is unchanged.
{ pixman }:
pixman.overrideAttrs (old: {
  patches = (old.patches or [ ]) ++ [ ./patches/pixman-rvv-hwprobe.patch ];
  mesonFlags = (old.mesonFlags or [ ]) ++ [ "-Drvv=enabled" ];
})
