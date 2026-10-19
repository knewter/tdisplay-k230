# Isolated opaque conversion — 2026-10-19

This source-built benchmark compares existing rounded Pixman compositing with
the proposed unscaled opaque XRGB8888→RGB565 path, into fresh heap and
**unattached** DRM dumb buffers. It neither modesets nor replaces the running
compositor. Existing baseline48af stayed active. The sole board lock was held.

Each size/memory class has three alternating12-frame rounds after warmup.
Whole destination buffers, including padding, matched byte-for-byte. The
833-wide dumb allocation requests834 pixels to meet Pixman's four-byte stride
requirement while keeping the image833 wide. The first unaligned benchmark
aborted before producing any dumb samples; it is excluded from these rerun
results. No integrated frame, latency, camera or glass claim follows.

| Memory | Pixels | Legacy median CPU | Candidate median CPU | Speedup |
| --- | --- | ---: | ---: | ---: |
| Heap | 833×376 | 4.639ms | 1.353ms | 3.43× |
| Unattached DRM | 833×376 | 4.615ms | 1.365ms | 3.38× |
| Heap | 1232×568 | 10.104ms | 2.869ms | 3.52× |
| Unattached DRM | 1232×568 | 10.069ms | 2.914ms | 3.46× |

Compile command, source snapshots/hashes, binary hash, start/end timestamps and
raw rows are adjacent. No new ISA is used. The renderer calls the path only
after clearing source transforms; masks, alpha sources and unsupported formats
fall back to Pixman. Native UBSan tests compare256 clipped/rounded/fallback
cases with Pixman; existing288 rounded and1152 transformed tests also pass.
A new exact-source build and quiet paired board trial are still required.
