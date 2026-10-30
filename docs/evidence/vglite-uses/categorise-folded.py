#!/usr/bin/env python3
"""Categorise perf folded stacks (self time) by leaf-first rules. Usage: cat.py folded.txt"""
import sys, re, collections

RULES = [
    ("rotation (k230_turn_*)", r"k230_turn"),
    ("RGB565 blit/copy into output (k230_rgb565_blit)", r"k230_rgb565_blit"),
    ("OVER composite into output (pixman composite_over*_0565)", r"composite_over_8888_0565|composite_over_.*_0565|rvv_composite_over_8888_0565"),
    ("pixman combine/fetch (OVER/bilinear image blit, client)", r"combine_over|bits_image_fetch|fast_composite|general_composite|pixman_composite|combine_|iter_|scaled_|bilinear"),
    ("text/glyph (pango, harfbuzz, freetype, cairo glyphs)", r"pango|hb_|harfbuzz|FT_|freetype|cairo_show_glyph|_cairo_.*glyph|glyph|font"),
    ("path/rect/gradient fill (cairo/tiny-skia fill, rasterise)", r"fill|rasteri|stroke|path|gradient|tessell|clip_rect|rounded|span"),
    ("buffer copy / memset (memcpy, memmove, memset)", r"memcpy|memmove|memset|__memcpy|copy_rect|_copy"),
    ("kernel (all [k] frames)", r"_\[k\]"),
]

def classify(stack):
    frames = stack.split(";")
    leaf = frames[-1]
    # kernel leaf wins first, then match leaf-first through the last 6 frames
    if leaf.endswith("_[k]"):
        return "kernel (all [k] leaf frames)"
    for f in reversed(frames[-8:]):
        for name, pat in RULES:
            if re.search(pat, f):
                return name
    return "other user code"

tot = collections.Counter()
per_proc = collections.defaultdict(collections.Counter)
for line in open(sys.argv[1]):
    line = line.rstrip("\n")
    if not line:
        continue
    stack, _, val = line.rpartition(" ")
    proc = stack.split(";", 1)[0]
    c = classify(stack)
    v = int(val)
    per_proc[proc][c] += v
for proc, cnt in sorted(per_proc.items(), key=lambda kv: -sum(kv[1].values())):
    s = sum(cnt.values())
    if s < 50e6:
        continue
    print(f"## {proc}: total {s/1e6:.0f} ms")
    for k, v in cnt.most_common():
        print(f"  {v/1e6:8.0f} ms {100*v/s:5.1f}%  {k}")
