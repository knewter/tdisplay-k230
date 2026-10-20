# Optional opaque interiors — 2026-10-20 UTC

The source2636ea7c diagnostic measures1.492ms for repeatedly converting an
unchanged313,208-pixel XRGB card while retaining full precision for corners.
The selected correction keeps that immutable full-precision image and adds
an optional preconvertedRGB565 interior **inside the same8MiB app-pixel cache
budget**. Only repeated cache requests allocate it; requests are not claimed
to equal presentations. A new client commit/quality/geometry generation gets
a new canonical buffer under the existing invalidation policy; no freshness cap.

A narrow wlroots addon owns only a borrowed Pixman view. It adds no client
buffer reference. The existing scaled-buffer destruction calls buffer_finish,
which finishes the addon view **before** the producer frees either plane.
Registration failure retains no pointer and charges no bytes. Both package
variants receive the API; only eligible rotatedRGB565 outputs prepare planes.

The renderer selects the auxiliary image only for an untransformed, unmasked
opaque XRGB interior targetingRGB565. Rounded corner masks, global alpha,
ARGB OVER, scaling/transforms, other destinations and invalid auxiliary
geometry/format keep full precision. Native512 pixel cases select64 eligible
paths and include32 sentinels that **fail** if corners use quantized pixels.
They also exercise bad auxiliary geometry/format, reuse,8MiB accounting,
allocation/registration failure and balanced teardown. Existing160 cached,
352 three-buffer frames/lifecycle,288 guarded full copies,768 conversion,
1152 affine and288 rounded comparisons pass. See native-tests.log.

## Isolated on-board comparison

The sole board lock was held while baseline48af continued running. No
modesetting or compositor replacement: fresh heap and **unattached** DRM
buffers use actual logical1232×568 destination geometry/stride2464. Main
source833×376 at(200,132), and a190-pixel cropped side card at(0,132) with
sourcex643, test both ordinary and alignment-sensitive row copies. Rounded
edges always use the original source. Complete destination pixels/padding
match before timing. Three alternating12-frame rounds follow warmup.

Selected median CPU per draw:

| Memory | Geometry | Previous unscaled conversion | Auxiliary interior | Speedup |
| --- | --- | ---: | ---: | ---: |
| Heap | Main | 1.778ms | 0.295ms | 6.02× |
| Unattached DRM | Main | 1.781ms | 0.303ms | 5.88× |
| Heap | Cropped side | 0.906ms | 0.282ms | 3.21× |
| Unattached DRM | Cropped side | 0.901ms | 0.286ms | 3.15× |

Cold helper setup was observed once per memory class: **2.303/2.399ms**,
including conversion/allocation and a Pixman view. These are two observations,
not a setup-cost distribution or full wlroots-addon measurement. Auxiliary
pixels628,672B plus canonical1,252,832B total1,881,504B, charged before reuse.
All setup work still counts in the later integrated end-to-end test.

The initial scalar16-bit stores cost5.563/5.403ms setup; packed32-bit pairs
reduce that. A packed64-bit constructor regressed setup to3.489/3.680ms and
was rejected. The selected32-bit constructor retains8-byte row alignment,
which helps the hot memcpy path. Previous variants, exact source snapshots,
commands, timestamps, binary/source hashes and every raw row are adjacent.
Only the selected constructor is integrated. Its publication comment says
"cache request" to distinguish the reuse gate from presentation counts;
experimental snapshots preserve their original comments unchanged.

Patch contexts were refreshed together for the extra optional argument; both
normal and quarter-turn stacks apply to the pinned0.20.2 source. The final
patched C difference adds only the public Pixman API, its renderer addon and
the unscaled call/log selection. No output-cache/damage behavior was changed
by the context refresh. Whitespace checks distinguish required blank unified
context prefixes from actual added source whitespace.

The exact cross-build, quiet paired full/reduced workload, changing clients,
camera/default/archive gates remain open. No synthetic result is an integrated
latency,52Hz, optical or real-glass claim. The serialized pair wrapper restores
its owned mode immediately after reduced capture, including on errors; only
pre-injection hide-route readiness failures get one bounded retry.
