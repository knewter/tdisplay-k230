# Rejected direct ARGB OVER — 2026-10-20 UTC

A direct unscaled premultiplied ARGB→RGB565 OVER loop matched Pixman for all
256 source alpha values, valid and malformed premultiplied colors (512 cases,
64 destination pixels each), plus256 clipped/rounded/mask cases under UBSan.
Opaque pairs use packed conversion, zero pixels skip writes, partial alpha
uses exact rounded8-bit blending/saturation. Pixel correctness did not make
it a suitable performance path: **dense alpha regressed about3.5×**.
The production source keeps ARGB OVER on Pixman.

Standalone on-board comparison into unattached DRM dumb buffers, three
alternating12-frame rounds per size/pattern, median CPU per copy:

| Pattern | Pixels | Pixman | Candidate |
| --- | --- | ---: | ---: |
| All opaque | 833×376 | 2.624ms | 1.980ms |
| Sparse alpha/zero | 833×376 | 2.623ms | 2.091ms |
| Dense alpha | 833×376 | 2.645ms | 9.278ms |
| All opaque | 1232×568 | 5.810ms | 4.189ms |
| Sparse alpha/zero | 1232×568 | 5.594ms | 4.788ms |
| Dense alpha | 1232×568 | 5.593ms | 20.427ms |

Source snapshots, exact compiler command, binary hash/timestamps and all raw
heap/DRM rows are adjacent. Every full destination, including padding, matches.
Baseline48af remained running under the sole board lock. No modesetting,
compositor replacement, integrated motion or optical claim.
