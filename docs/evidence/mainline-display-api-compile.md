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

## Reproducible check

`tools/mainline-display-object-check.sh` stages the DRM sources and
external-module Makefiles from `nix/patches/mainline/drm/`, copies the
prepared kernel build output into this checkout's ignored `.scratch/`
directory, and invokes Kbuild. The check held the shared build slot with
`flock`:

```sh
flock /tmp/k230-nix-build.lock bash -c \
  'MAINLINE_KERNEL_SRC=/nix/store/302cz10wl1g77aspr3gc2hm999rr5701-linux-mainline-k230-drm-src \
   tools/mainline-display-object-check.sh'
```

The script applies the DRM symbols from `nix/kernel-mainline-drm.nix` to a
copy of the prepared `.config`, then runs `olddefconfig` against the patched
mainline source output. Effective config retained `DRM=y`,
`DRM_CANAAN=y`, `DRM_CANAAN_DSI=y`, `DRM_PANEL_CANAAN_UNIVERSAL=y`,
`DRM_LONTIUM_LT9611=y`, `DRM_CLIENT_SETUP=y`,
`DRM_FBDEV_EMULATION=y`, and `DRM_MIPI_DSI=y`. The complete sanitized
stdout/stderr log is committed beside this report as
`docs/evidence/mainline-display-api-compile.log`.

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
