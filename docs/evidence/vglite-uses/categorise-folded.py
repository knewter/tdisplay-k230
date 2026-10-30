#!/usr/bin/env python3
"""Bucket perf folded stacks by the LEAF frame (self time). Usage: categorise-folded.py folded.txt

Corrected 2026-10-30: the first version matched the last eight frames, so
pixman work under a cairo fill frame was counted as "path fill". Self time only
is attributed here; "other" is unattributed user code.
"""
import collections
import re
import sys

RULES = [
    ("rotation (k230_turn_*)", r"k230_turn"),
    ("RGB565 blit/convert into output (k230_rgb565_blit)", r"k230_rgb565_blit"),
    ("pixman OVER composite", r"composite_over|combine_over|fast_composite|general_composite|pixman_composite|bits_image_fetch|iter_|scaled_|bilinear"),
    ("pixman opaque blit (rvv_blt)", r"rvv_blt|_blt"),
    ("pixman solid fill (rvv_fill)", r"rvv_fill|pixman_fill"),
    ("buffer copy (memcpy/wordcopy/memmove/memset)", r"memcpy|memmove|memset|wordcopy"),
    ("text/glyph (pango, harfbuzz, freetype)", r"pango|hb_|harfbuzz|FT_|freetype|glyph"),
]


def classify(stack):
    leaf = stack.split(";")[-1]
    if leaf.endswith("_[k]"):
        return "kernel (leaf in kernel)"
    for name, pat in RULES:
        if re.search(pat, leaf):
            return name
    return "other user code (unattributed)"


per_proc = collections.defaultdict(collections.Counter)
for line in open(sys.argv[1]):
    line = line.rstrip("\n")
    if not line:
        continue
    stack, _, val = line.rpartition(" ")
    per_proc[stack.split(";", 1)[0]][classify(stack)] += int(val)
for proc, cnt in sorted(per_proc.items(), key=lambda kv: -sum(kv[1].values())):
    s = sum(cnt.values())
    if s < 50e6:
        continue
    print(f"## {proc}: total {s/1e6:.0f} ms")
    for k, v in cnt.most_common():
        print(f"  {v/1e6:8.0f} ms {100*v/s:5.1f}%  {k}")
