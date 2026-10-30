# What VG-Lite is best used for on this device

**Evidence class: analysis of committed board profiles (2026-10-22, injected
touch, no GPU involved) plus SDK/driver source reading. No new board access was
made for this document** (the board was being rebooted by the coordinator), and
nothing here is a GPU measurement on the mainline kernel. Estimates are marked
**UNVERIFIED** and become tasks in the draft successor
`openspec/changes/the-compositor-rotates-scanout-on-the-gpu`.

## Sources

| Input | Where |
| --- | --- |
| Drawer scroll, client + sway CPU profile (`perf`, 30 s, build `z1basiwi`) | `docs/evidence/interaction-jank/drawer-profile/profile-after2/{folded.txt,summary.json}` |
| Sway profile on the drawer for the RVV-turn build, and its prose | `.../compositor-repaint/prof-k-drawer`, `compositor-repaint/README.md` |
| Sway profile over eight keyboard cycles | `.../compositor-repaint/prof-m-kbd` |
| Sustained drawer scroll, traced scene rebuild | `.../drawer-scroll/README.md` (commit `9dba3161`) |
| Rotation timing | `K230_PIXMAN_OUTPUT_TURN ... rotation_cpu_ns=` in `.../compositor-repaint/run-m/drawer/shell-journal.txt` (117 samples) |
| What a private-buffer VG-Lite job costs | `docs/evidence/gpu-validation/cpu-timing-pass.txt`, `docs/evidence/vglite-scene-board/context-lifetime/README.md` |
| What the SDK build supports | `VGLite/vg_lite_options.h` in the pinned SDK `1104236d...` |

All profiles: board DSI panel, landscape 1232x568 logical (rotated to 568x1232
RGB565 scanout), 52.19 Hz, one online CPU, `perf record -e cpu-clock -F 199`.
[`categorise-folded.py`](categorise-folded.py) buckets self time by the leaf
frames; outputs are `categories-*.txt` here. The buckets are by symbol name, so
"other user code" is unattributed, not free.

## Where the CPU goes today

Sway (the compositor), drawer scroll, 30 s window, 3,925 ms sampled
(`categories-drawer-client-and-sway.txt`; the earlier `prof-k-drawer`, 2,854 ms,
has the same shape):

| Category | Share of sway | Notes |
| --- | ---: | --- |
| Output rotation (`k230_turn_*`) | 28.9% | `rotation_cpu_ns` 3.4 ms median per rotated frame in run-m (up to ~4.0 ms in other runs); destination is the scanout buffer, bound by the writes, not instructions (RVV tile version halved it in isolation, 10.3 -> 4.5 ms, and gained nothing in sway). |
| OVER composite of ARGB surfaces into RGB565 (`composite_over_8888_0565`) | 28.4% | Blends the drawer sheet (alpha 0.95) over the wallpaper. |
| Opaque blit/convert into the output (`k230_rgb565_blit`) | 15.9% | |
| Kernel (syscalls, page faults, scheduling) | 15.0% | |
| Other user code | 11.7% | |

Sway keyboard cycles, 7,518 ms (`categories-keyboard-sway.txt`): OVER composite
40.4%, rotation 20.7%, other 14.5%, kernel 14.0%, `rgb565_blit` 8.4%. Three ARGB
surfaces are blended per frame (`keyboard-blend/README.md`).
Sway used about 7.5 ms CPU per presented drawer frame
(`compositor-repaint/README.md`), so by share: rotation ~2.2 ms and OVER ~2.1 ms
per frame (journal rotation timing, 3.4-4.0 ms, is larger than the profile
share implies; the two are different samples, so quote the range).

The shell client (`k230-shell-rust`), same capture, 2,121 ms
(`categories-drawer-client-and-sway.txt`; render median 6.3 ms/frame):

| Category | Share of client |
| --- | ---: |
| Path / rect / gradient fills | 43.8% |
| Kernel | 16.8% |
| Other user code | 14.5% |
| Buffer copy / memset | 12.8% |
| Text / glyphs | 10.9% |
| Image / icon blits (pixman combine/fetch) | 1.2% |

Full-scene rebuild: before the cached-scene fix every scroll frame rebuilt the
scene, 33.8 ms thread CPU (`drawer-scroll/README.md`); after it the client
renders in 6.3 ms and the fills above are what remains. That cost is now an
algorithm/damage question first, not a GPU one.

## Why the September trial lost, and the rule it gives

In the committed wlroots-renderer trial the GPU pass cost 44 ms against Pixman's
36.5 ms. The GPU itself was ~2.4 ms; an immutable copy of every client buffer
(~20 ms) and conversion/upload into GPU memory (~17 ms) dominated
(`context-lifetime/README.md`). A private-buffer 568x1232 job needs only 0.10 ms
process CPU for `vg_lite_finish` versus 1.70 ms for Pixman, at 1.97 vs 1.78 ms
wall (`cpu-timing-pass.txt`).

**Rule:** a use is only worth building if the GPU reads and writes memory that
already lives where the GPU can reach it. The CPU may not copy pixels to feed it.
The SDK driver imports a dma-buf by the *last* scatter-gather address
(`vg_lite_hal_map`), so buffers must be physically contiguous: DRM dumb buffers
or CMA, not memfd `wl_shm` pages (`DMABUF_HEAPS` is unset on the board kernel;
`udmabuf` gives scattered pages).

## Candidates, ranked

CPU saved is per presented frame on the drawer workload, from the numbers above.
Overheads: submit+finish CPU (0.1 ms measured in a private-buffer job), cache
clean of any CPU-written source (**UNVERIFIED**: size/throughput on the C908
unmeasured; a 1.4 MB source is the scale), and wall wait (~2 ms, but the CPU is
free to run other tasks on this one-core board while the GPU works).

| Rank | Use | CPU saved / frame | Overhead | Net | Why / blockers |
| ---: | --- | ---: | --- | ---: | --- |
| 1 | **Rotate the finished frame into scanout** (source: compositor's own RGB565 scratch, 1.4 MB; destination: padded scanout dumb buffer) | 3.4-4.0 ms measured (~30-35% of sway's repaint) | clean 1.4 MB source (UNVERIFIED); 0.1 ms submit; ~2 ms wall wait | **~3 ms, UNVERIFIED** | No client copy at all: both buffers are compositor-owned and can be contiguous. Removes the scanout-write stall that bound the RVV attempt. Padded 64-byte-aligned destination and BGR565 format are already proven (`vglite-scene-board/padded`). Narrow patch at the existing `K230_PIXMAN_OUTPUT_TURN` site (`nix/patches/wlroots-k230-output-turn.patch`) rather than a new renderer. Needs the kernel driver and the access broker. |
| 2 | **Shell client renders into a contiguous (DRM dumb/CMA) buffer shared with sway** | up to ~2.8 ms fills + 0.8 ms buffer copy of a 6.3 ms client frame if fills/gradients move to VG-Lite (hardware linear gradient/rect fill; SDK build has `RADIAL_GRADIENT 0`) | per-frame sync with sway; client rewrite; clean/flush per frame | **~2-3 ms, UNVERIFIED, high effort** | Only shell clients, not GTK/foot apps. Also unlocks rank 4 for the same surfaces. Needs dmabuf sharing with fences; do after rank 1. |
| 3 | **ARGB-over-RGB565 composition of those contiguous client surfaces** | OVER is 28-40% of sway: ~2.1 ms drawer, ~3 ms keyboard | needs sources in contiguous memory (rank 2), premultiplied SRC_OVER onto RGB565 (verified opaque; alpha blend on board UNVERIFIED) | **~2-3 ms, depends on 2** | Largest single sway bucket but impossible for `wl_shm` clients without the copy that sank September. |
| 4 | Overview / transition transforms (scale, rotate of card surfaces) | not profiled here: UNVERIFIED | none known if surfaces are contiguous | unknown | Needs its own CPU profile of the overview open/close before any claim. Compositor app scaling for tiny UI was rejected earlier, so only transition-time transforms are in scope. |
| 5 | Text/glyph rasterisation | ~0.7 ms (10.9% of a 6.3 ms client frame) | glyph path rendering needs tessellation buffer (renderer initialises with `(0,0)`) | small | Poor return; cache glyph runs on the CPU instead. |
| - | Full-scene rebuild | n/a | n/a | n/a | An algorithmic cost already fixed by caching and band damage, not a GPU job. |
| - | YUV conversion for video wallpaper | n/a | n/a | **blocked** | The pinned SDK build sets `gcFEATURE_VG_YUV_INPUT 0` and `gcFEATURE_VG_YUV_OUTPUT 0` in `vg_lite_options.h`, so this core build is not configured for YUV sources. A runtime `vg_lite_query_feature` on the board could still overrule this; UNVERIFIED. |

## Recommendation

Do rank 1 first: it has the best expected saving, needs no client changes and no
buffer the CPU must copy, and it is a small patch to code the repo already
carries. It also answers the original question (does VG-Lite reduce real shell
rendering cost) with one number that is easy to measure: sway CPU ms and
repaint wall per presented frame, drawer scroll and keyboard cycles, GPU vs
Pixman rotation, same build and boot. Rank 2 and 3 are one project (contiguous
shared client buffers) to scope only if rank 1 shows the cache-clean and wait
overheads are small. The draft successor is
`openspec/changes/the-compositor-rotates-scanout-on-the-gpu`.

Limits: profiles are 2026-10-22 builds (`z1basiwi`, `g2yjvzv4`), landscape, injected
touch, and have since changed; category shares are by symbol name from sampled
stacks; the rotation timing log is rate-limited (117 lines per 30 s), so it is a
sample of frames, not every frame.
