# Mainline DRM derivation build

## Successful result

On 2026-09-29, the coordinator ran the candidate kernel, DTB, and boot-files
outputs together under `/tmp/k230-nix-build.lock` with two Nix jobs and four
cores:

```sh
nix build .#kernelMainlineDrm .#deviceTreeMainlineDrm .#kernelMainlineDrmBootFiles \
  --print-out-paths --max-jobs 2 --cores 4
```

The command exited 0 and produced:

- Kernel: `/nix/store/qa041skh6iy7rmx86c5zfn2xyq036f0g-linux-riscv64-unknown-linux-gnu-7.3.0-rc5`
- DTB: `/nix/store/8v2v53z2qpxapsq507nvxsmld4y24d13-k230-tdisplay-mainline-drm.dtb`
- Boot-files pair: `/nix/store/bpbr6vldkm1y48k6wrdh7s6yv5szqa0k-k230-mainline-drm-boot-files`

The full stdout is committed in `mainline-display-full-build.log`. The
RISC-V Image is 38,530,048 bytes and the DTB is 10,553 bytes. `file` identifies
the Image as a little-endian RISC-V boot executable and the DTB as version
17. Both files in the boot-files output were compared byte-for-byte against
their source derivation outputs. `dtc -I dtb -O dts` round-trip inspection
found the DesignWare I2C/Goodix, Canaan display subsystem/VO/DSI, and universal
panel compatibles. The exact inspection commands and output are committed in
`mainline-display-artifact-inspection.log`.

## Failure and correction

The first complete kernel attempt failed at final vmlinux link because
`canaan_dsi_bind` referenced `drm_bridge_connector_init` but Canaan Kconfig
did not select its implementation. The pinned source declares the symbol in
`drivers/gpu/drm/display/drm_bridge_connector.c`; its Makefile includes the
object only with `CONFIG_DRM_BRIDGE_CONNECTOR`, which is nested under
`DRM_DISPLAY_HELPER`. The Canaan Kconfig now selects both symbols. The full
captured failure and successful retry logs are in
`mainline-display-full-build-failure.log` and
`mainline-display-full-build.log` respectively.

The corrected prepared-dev object/config check resolved
`CONFIG_DRM_DISPLAY_HELPER=y` and `CONFIG_DRM_BRIDGE_CONNECTOR=y` and compiled
the Canaan DRM/DSI, panel, and LT9611 external objects. This is a narrow host
object check; its expected unresolved cross-module modpost warnings are
recorded in `mainline-display-api-compile.log`. The in-tree Nix kernel build
above is the complete link evidence.

Earlier attempts in this checkout could not reach the daemon because the
default cache was read-only and, after redirecting the cache under `.scratch`,
the socket returned `Operation not permitted`; these are retained in
`mainline-display-nix-build.log`. No board or serial port was used. Kernel,
DTB, and boot-files derivation tasks are complete, but boot, display power,
panel illumination, and touch interaction remain unverified.
