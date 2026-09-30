# Mainline DRM forward-port API compile check

## Result

On 2026-09-29, the copied Canaan DRM/DSI, universal panel, and LT9611
objects compiled and linked as external modules against prepared Linux
7.3.0-rc5 headers. The source pin in `nix/kernel-mainline-src.nix` is
`72d3fcf802c45d00b300f25b848a93c3a2bd7c7e` (v7.3-rc5).

This is an object/external-module API check only. It does not prove that the
full `kernelMainlineDrm` derivation builds, that the drivers are linked
in-tree, that the DTB is valid for the board, or that any device probes or
drives the panel/touch hardware.

## Command

The compile used the existing prepared kernel dev output and cross compiler;
the build directory was copied to `/tmp` so Kbuild could write generated
objects without changing the store. `flock /tmp/k230-nix-build.lock` held the
shared build slot while running this loop:

```sh
DEV=/nix/store/0148bw9nb2cb9prgj6505kywvy2096bw-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev/lib/modules/7.3.0-rc5
SRC="$DEV/source"
BUILD=/tmp/k230-mainline-dev-build
MOD=/tmp/k230-mainline-drm-objects
CC=/nix/store/4j2mwxqjvnyr6da0925sp0bm4jaj5r5i-riscv64-unknown-linux-gnu-gcc-wrapper-15.3.0/bin/riscv64-unknown-linux-gnu-
for part in canaan panel bridge; do
  make -s -C "$SRC" O="$BUILD" M="$MOD/$part" ARCH=riscv \
    CROSS_COMPILE="$CC" KBUILD_MODPOST_WARN=1 modules
done
```

`BUILD` was copied from `$DEV/build`. The three `M=` directories held the
changed files from `nix/patches/mainline/drm/`; the Canaan directory's Kbuild
combined the DRM core objects and built the DSI host object, while panel and
LT9611 were each built separately. Prepared `.config` had
`CONFIG_DRM_CLIENT_SETUP=y` and `CONFIG_DRM_FBDEV_EMULATION=y`.

## Output and limits

Kbuild produced `canaan-drm.ko`, `canaan_dsi.ko`,
`panel-canaan-universal.ko`, and `lontium-lt9611-k230.ko`. It emitted
missing-prototype warnings for existing port functions and modpost warnings
for symbols unavailable to these external modules, including the in-tree
Canaan component symbol, `drm_bridge_connector_init`, and HDMI helper symbols.
Those warnings were allowed by `KBUILD_MODPOST_WARN=1`; they are why this is
not evidence of an in-tree kernel build. The command exited 0.

The full `nix build .#kernelMainlineDrm` command has not been rerun. In the
previous attempt it could not evaluate/build because this environment could
not connect to `/nix/var/nix/daemon-socket/socket` (`Operation not permitted`).
No board, serial port, display, or touch test was performed.
