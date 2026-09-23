# VG-Lite renderer host correction evidence

Captured 2026-09-23, 06:29–06:34 UTC. Worktree
`/tmp/k230-vglite-composition-apply`, branch `apply/vglite-composition`, base
`4eab0e7cd177a5a45883ccd6ec045354d71c60e4`.
Renderer artifact SHA256:
`bcfbbabd923874f238e0e391a62f818f722acb5ca3e451b756473beee00c499d`.
No board, serial port, display owner, or deployed system was changed.

## Commands and results

```sh
WLROOTS_SOURCE=/nix/store/r2zcb3d3dgmz09qjaqsy945inal2h41r-source \
VGLITE_SOURCE=/tmp/k230-sdk-vglite-src/buildroot-overlay/package/vg_lite \
  tools/test-vglite-renderer.sh
```

Exit 0, with ASan/UBSan and `-Wall -Wextra -Werror`:

```text
PASS: production renderer snapshots, RGB channel order, padded upload, crop/scale translation, alpha/clip/partial-damage replay, exact opt-in, record/map/init/command/finish failures, completion quarantine; real pinned Pixman output comparison
```

The wlroots source is pinned 0.20.2 from the Nix derivation. The SDK checkout
reports `1104236db4d1e47873bd68924f912747b820228c`, the same pin as the packaged
library. The test compiles production `renderer.c` and the pinned
`render/pixman/pass.c`, `render/pass.c`, and `util/box.c`. Its surrounding
wlroots buffer/texture objects are host test doubles; Pixman image composition
is real. Mock GPU work is delayed until finish and asserts if storage is freed
before completion. Failed finish is exercised in a subprocess that retains all
potentially live GPU resources through exit. This is a lifetime/geometry/error
contract test, not an emulator of physical GPU color precision or caches.

Additional cases cover a scene-shaped clipped background plus unscaled opaque
XRGB texture, realloc failure after 16 recorded operations, snapshot OOM,
texture allocation failure before/after GPU commands, a second-command failure,
unimplemented timeline/color-transform/timer contracts, and rejected target
planes/offset/modifier/dimensions/descriptor/format. Every comparison checks all
pixels and row padding against the pinned Pixman pass.

```sh
nix build .#shell-compositor-vglite --no-link --print-out-paths
```

Exit 0. Cross-built opt-in package:

```text
/nix/store/r9z3grgfnq82mvjyvnr97jyqqp302f6s-sway-1.12
```

wlroots derivation:
`/nix/store/pfyg9xl2pzm2i57nvs7irnq4kx3rgjvm-wlroots-vglite-full-pass-fallback-riscv64-unknown-linux-gnu-0.20.2.drv`.
The first build caught strict C23 rejecting `asm` in a register declaration;
using `__asm__` corrected it and the rebuild passed. This package was not
installed on the board and is not part of the default image.

```sh
python3 tools/test-vglite-fallback.py
openspec validate the-shell-trials-vglite-composition --strict
./tools/blob-scan.py --no-vendor
git diff --check
```

All exited 0. The first is source wiring only. Blob scan reports every binary
accounted for; this correction adds source, tests and documentation only.

## Remaining physical and access gates

**UNVERIFIED:** live Sway GPU scene use, exact source RGBA/target RGB565 samples,
premultiplied alpha blending to RGB565, partial-damage GPU preservation, C908
cache direction and scanout visibility, failed-completion hardware recovery,
fallback rates, touch/keyboard/Apps/Back/Home/Terminal/Monitor/system controls,
and matched repeated-scene timing. Group 2 tasks remain open where they require
these observations. The prior private-buffer probe is not live-output proof.

There is also a concrete access prerequisite: the normal systemd shell service
runs as `shell`, while the pinned library directly opens `/dev/vg_lite` in
`VGLiteKernel/linux/vg_lite_ioctl.c:95`. Its ioctl interface accepts GPU command
addresses without a suitable client security boundary. Do not grant that device
to the shell group/UID: ordinary launched Wayland clients share that identity.
A compositor-only privileged access arrangement must be established before a
normal-service GPU trial. No device permissions were changed by this work.

The reserved board operator can gather the narrow **read-only prerequisite**
record with:

```sh
./tools/console.py /dev/ttyACM0 --wait=3 \
  'stat -c "%a %U %G" /dev/vg_lite; systemctl show shell -p User -p Group -p ExecStart; systemctl is-active shell seatd'
```

That command is not the live rendering gate. Once the access boundary is
resolved, the operator must run the built Sway with `WLR_RENDERER=vglite` and
`K230_VGLITE_ALLOW_UNPROVEN_CACHE=1`, retaining the same wlroots DRM backend and
using exactly one compositor. Capture debug messages proving actual
`VG-Lite full frame submitted` operations, whole-pass fallback messages, output
samples and the physical interactions above. Repeat matched scenes with the
flag set to `0` for Pixman. Restore the normal shell and record its health.
Until those results are committed, this remains an unsupported opt-in diagnostic
and Pixman remains the default. Review, merge, push and deployment verification
are coordinator work; no physical gate is closed by this host result.
