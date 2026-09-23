# Default scene color metadata: narrow host proof

2026-09-23 UTC, branch `apply/vglite-composition`, base
`1b155b621303dc78c50a6ad1df224eafe5ce30fa`. This is source and host pixel evidence;
it does not prove GPU hardware fidelity, cache behavior, or a board frame.

## Source contract

Pinned wlroots 0.20.2 source:

- `types/scene/surface.c:290–318` gives ordinary surfaces the GAMMA22 transfer
  function and sRGB **primaries**, even absent a color-management request.
- `types/scene/wlr_scene.c:1529–1556` resolves those primaries and passes the
  metadata to the renderer. `render/color.c:408–432` gives GAMMA22 and SRGB
  transfer functions equal default luminance ranges, making the scene's
  luminance ratio exactly one. This does **not** equate their transfer curves.
- `render/pixman/pass.c:40–198` uses pixels, geometry, clip, opacity and blending
  but never applies texture transfer, primaries or luminance metadata. For the
  default tuple on the untransformed output it copies encoded RGB values,
  subject to RGB565 quantization. This is the existing renderer's reference
  behavior, not a new claim of general color-management support.

The local exception requires GAMMA22, a nonnull primaries object whose eight
coordinates exactly equal the pinned library's named sRGB values, and luminance
exactly one. Equality is per coordinate, with no epsilon or struct-padding
comparison; NaN cannot pass. Primaries are obtained through the actual pinned
`wlr_color_primaries_from_named` function. Metadata-less operations retain their
previous behavior. Incomplete tuples, SRGB/PQ or combined transfer flags,
other/nearby primaries, and changed luminance remain ineligible.

All other guards remain: RGB565 linear target layout, CPU RGB texture source,
normal geometry/transform, allowed filter, full redraw, source/destination
bounds, clip, opacity/blend, no encoding/range conversion, and no pass color
transform/timeline. The default image and device-access policy are unchanged.
The existing exact cache-experiment opt-in remains mandatory.

## Executed host tests

```sh
WLROOTS_SOURCE=/nix/store/r2zcb3d3dgmz09qjaqsy945inal2h41r-source \
VGLITE_SOURCE=/tmp/k230-sdk-vglite-src/buildroot-overlay/package/vg_lite \
  tools/test-vglite-renderer.sh
nix build .#shell-compositor-vglite --no-link --print-out-paths
```

The sanitizer-backed test compiles the production renderer, actual pinned
Pixman pass and actual pinned color helpers. Function/data section collection
omits unused color-transform implementation dependencies; the called helpers
are not mocks. VG-Lite remains an asynchronous host device model.

PASS: 46 metadata/blend cases each compare 1,024 RGB565 pixels, including every
8-bit value of each channel and mixed colors. Sources cover opaque ARGB/XRGB;
blend cases cover NONE and PREMULTIPLIED. The exact ordinary tuple executes the
modeled GPU path and matches the real Pixman pass byte-for-byte. Rejections
cover each of eight primary coordinates changed by one float ULP, NaN primary,
SRGB/PQ/combined transfer flags, missing or BT2020 primaries, absent transfer,
luminance 0.5/NaN/one ULP above one, nondefault encoding/range, opacity and
transform. Rejected cases perform zero GPU initializations and replay Pixman.

Existing crop/integer-scale, clip, partial-damage and alpha comparisons run
both with and without actual scene-default metadata. Caller metadata is mutated
after recording, alongside clip and texture destruction, to preserve the
snapshot contract. Full renderer failure/quarantine tests continue to pass.

## Remaining physical gate

The reserved board operator must capture `VG-Lite decision v=1` records from
this package in the bounded root scene harness, distinguish `result=attempt`
from `result=gpu`, compare the visible/captured output with a matched forced
Pixman scene, and verify restoration. An eligible default-color texture can
still fall back on clip, damage, source, target or device checks. This source
exception does not close tasks 2.1–2.5 or 3.1–3.4.

Cross-build PASS: `/nix/store/ifzikq31jbmczvvjpqcff1hymjd6f1d9-sway-1.12`.
Actual unwrapped executable: `/nix/store/z10vv6gwihm5b3w0msknykj60j79zq4w-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`.

After importing that closure, the reserved operator command is:

```sh
python3 tools/vglite-root-scene-trial.py --seconds 20 \
  --compositor /nix/store/z10vv6gwihm5b3w0msknykj60j79zq4w-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  -- <trusted-self-terminating-probe> <probe-arguments>
```
