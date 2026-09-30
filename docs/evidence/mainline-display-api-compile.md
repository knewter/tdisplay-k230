# Mainline DRM forward-port API compile check

## Result

On 2026-09-29, the copied Canaan DRM/DSI, universal panel, and LT9611
objects compiled and linked as external modules against prepared Linux
7.3.0-rc5 headers. The source pin in `nix/kernel-mainline-src.nix` is
`72d3fcf802c45d00b300f25b848a93c3a2bd7c7e` (v7.3-rc5). This is a narrow
object/config check; the full candidate kernel, DTB, and boot-files builds
are separately proven by `docs/evidence/mainline-display-nix-build.md`. No
part of these host checks proves physical probe or display/touch operation.

## Reproducible check

`tools/mainline-display-object-check.sh` stages the DRM sources and
external-module Makefiles from `nix/patches/mainline/drm/`, copies the
prepared kernel build output into this checkout's ignored `.scratch/`
directory, and invokes Kbuild. The successful run used the matching outputs
from the full build and held the shared build slot:

```sh
flock /tmp/k230-nix-build.lock bash -c \
  'MAINLINE_KERNEL_DEV=/nix/store/2awaim3qqiwrmqi4gbg9fghwsw9c8r6h-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev/lib/modules/7.3.0-rc5 \
   MAINLINE_KERNEL_SRC=/nix/store/vzv8v6pfxa2yxnzhiywmjwmp8aykmlj3-linux-mainline-k230-drm-src \
   tools/mainline-display-object-check.sh'
```

The script applies the candidate DRM and input symbols to a copy of the
prepared `.config`, then runs `olddefconfig` against the patched source.
Effective config included `DRM=y`, `DRM_CANAAN=y`, `DRM_CANAAN_DSI=y`,
`DRM_PANEL_CANAAN_UNIVERSAL=y`, `DRM_LONTIUM_LT9611=y`,
`DRM_CLIENT_SETUP=y`, `DRM_FBDEV_EMULATION=y`, `DRM_MIPI_DSI=y`,
`DRM_DISPLAY_HELPER=y`, `DRM_BRIDGE_CONNECTOR=y`,
`INPUT_TOUCHSCREEN=y`, and `TOUCHSCREEN_GOODIX_BERLIN_I2C=y`. The complete
stdout/stderr log is `docs/evidence/mainline-display-api-compile.log`.

The first complete-kernel attempt reached the final vmlinux link and found
that `drm_bridge_connector_init` was not linked. The pinned source builds
this helper only with `CONFIG_DRM_BRIDGE_CONNECTOR` inside
`DRM_DISPLAY_HELPER`; Canaan Kconfig now selects both, following upstream
bridge-driver practice. The corrected external-module check resolved both
symbols to `y` and emitted no unresolved `drm_bridge_connector_init`
warning. The complete in-tree build then succeeded. Both attempts are kept
in `docs/evidence/mainline-display-full-build-failure.log` and
`docs/evidence/mainline-display-full-build.log`.

## Output and limits

Kbuild produced `canaan-drm.ko`, `canaan_dsi.ko`,
`panel-canaan-universal.ko`, and `lontium-lt9611-k230.ko`. It emitted
missing-prototype warnings for existing port functions and modpost warnings
for symbols unavailable to these separately built external modules, including
the in-tree Canaan component and PHY symbols and HDMI helper symbols. Those
warnings were allowed by `KBUILD_MODPOST_WARN=1`; they are why this external
module check alone is not an in-tree link proof. The corrected command exited
0, and the complete in-tree kernel build separately links these components.
No board, serial port, display, or touch test was performed.
