# Opt-in opaque mirror scale cache: host proof only

This experiment targets the Pixman build stage of the card repaint. It is off
unless `SWAY_K230_CARD_SCALED_CACHE=1`. The same package can be run with the
variable set to `0` or `1`; the normal card shell remains unchanged by default.
It does not establish a board performance improvement or complete task 4.2.

The cache applies only to an opaque XRGB8888 or RGB565 SHM scene surface on an
RGB565, scale-one, normal-transform output. The source crop must cover the
whole buffer, destination size must equal its source size, color metadata must
match the ordinary SHM defaults, and the scaled mirror must be wholly inside
the card content clip. Other cases use the existing scene-surface rendering
path. One cache per mirror keeps independently committing subsurfaces separate.
The original `wlr_scene_surface` and its node remain live, retaining wlroots
buffer ownership, frame callbacks and output sampling. Each surface commit
increments a generation, so rewriting and recommitting the same SHM buffer
rebuilds cached pixels. Source loss, privacy changes, normal-mode restoration
and output loss destroy mirror caches. At most 8 MiB of cache pixel buffers can
be live; allocation failure falls back to the original path.

`K230_CARD_SHELL scaled-cache hits=N misses=N fallbacks=N bytes=N` reports
cumulative mirror sync decisions and currently allocated cache pixel bytes.
These counts are diagnostic; a hit does not by itself prove that the mirror
was sampled in a submitted frame. The board-session exporter has an explicit grammar for these rows. The
[physical paired trial](../scaled-cache-board/README.md) exercised the cache
but did not improve the required workload, so it remains disabled by default.

Host checks from this branch:

```
python3 tests/test_card_scaled_cache.py
# PASS: direct Pixman RGB565 output equals scaled-then-blitted output for
# XRGB8888/RGB565, up/down scales; same SHM allocation with changed pixels
# produces different and still matching output.

nix build .#card-shell --max-jobs 1 --cores 8 --print-out-paths --no-link
# /nix/store/hxilq8jdlb0b8mj8jzmvhwsw9mwnr69y-k230-card-shell

python3 tests/test_card_shell_scaled_cache_runtime.py
# PASS: actual cross-built Sway and live Wayland clients under QEMU,
# RGB565 cache off and on; each run passed the existing interaction,
# subsurface frame-callback, privacy, popup, restore and teardown checks.
```

The cache-enabled QEMU run exercised nonzero hits and misses, allocated cache
pixels while active, and reported zero retained bytes after normal restoration.
The runtime uses injected input and a headless output; it is not physical
finger, optical, or board CPU evidence. Cached and uncached screenshots from
the continuously animated client are not frame-synchronized, so exact pixel
equivalence is established by the native Pixman test for the restricted path,
not by visually comparing those captures. The board experiment must compare
the same package with the flag off/on using the same workload and preserve all
interaction and privacy gates before judging cost.
