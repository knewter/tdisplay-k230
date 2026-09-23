# Retain the serialized GPU context across frames

The [board cost profile](../cost-profile/README.md) measured about 107 ms of
initialization/cleanup in a 149 ms GPU pass. Pinned kernel source confirms that
opening and closing its last context triggers clock/reset sequences with sleeps.
The opt-in renderer now retains one process-global context under its existing
mutex and closes it when the last renderer owner is destroyed.

Only clear and image-blit operations are admitted. Initialization uses `(0, 0)`
to omit unused tessellation storage; the pinned SDK demonstrates this in
`test/samples/imgIndex/main.c` and `imgIndex.c`. Its `VGLite/vg_lite.c`
`set_render_target` updates target dimensions per pass, so output-size changes
do not depend on tessellation dimensions. Source ownership, per-pass imported
targets, whole-pass replay, and explicit finish before release are unchanged.

A failed finish still disables GPU use and quarantines context, source memory,
and target mapping for process lifetime. Last-owner destruction does not call
close in that state. A failed shutdown close similarly prevents a second close
or reinitialization; future renderer instances use Pixman. Successful final
shutdown permits a later new owner to initialize a fresh context.

The ASan/UBSan production-renderer suite passes. New tests cover repeated
frames at different dimensions, two renderer owners, first-owner destruction,
last-owner close, subsequent reinitialization, shutdown-close failure, and
last-owner destruction after failed-finish quarantine. Existing exact Pixman
pixel, crop, scale, fallback, and failure tests remain passing.

```sh
TMPDIR=/mnt/MediaVolume/home/jadams \
WLROOTS_SOURCE=/nix/store/r2zcb3d3dgmz09qjaqsy945inal2h41r-source \
VGLITE_SOURCE=/nix/store/pvpqrg3diyi9mcgmqjc0f80hpdmk699p-source/buildroot-overlay/package/vg_lite \
  tools/test-vglite-renderer.sh
nix build .#shell-compositor-vglite --max-jobs 1 --cores 8 --no-link --print-out-paths
```

The narrow cross-build passes:
`/nix/store/rr671hlb8pg35qx2fl9hwxl42rlj7bgg-sway-1.12`.
Board cost, capture and recovery comparisons remain pending at this checkpoint.
Retaining a context also retains its allocations and active device clock state
between frames; idle-power impact is unmeasured. This is still opt-in, with the
normal shell on Pixman and every broader acceptance gate unchanged.
