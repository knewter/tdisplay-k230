#!/usr/bin/env python3
"""Allowlisted journal excerpt for the apply trial (host).

  sanitize_journal.py PRIVATE_JOURNAL.txt > excerpt.txt

Keeps only touch, picker-memory, theme-command, appearance-*, optimistic-apply and THEME_TIMING lines, drops the host name and
process ids, and replaces catalog and generation identifiers with labels. Anything else is discarded.
"""
import re
import sys

IDS = {"972f1bd5258532d1bb3125fd": "catppuccin", "10db74a93cd95c1d02dd1371": "catppuccin-latte",
       "e662802bdec2": "gen-light", "2135c502caa9": "gen-dark"}
KEEP = re.compile(r"rust-shell \d+ms (touch-(down|up) |theme-command |appearance-(prepare|commit)-accepted|optimistic-apply |picker-memory )|THEME_TIMING (activate_generation|handle (list|preview|activate)|helperd (list|preview|activate)|app_deferred|keyboard_deferred)")
# `journalctl -o short-iso-precise`; the swapped shell runs as `wrapper`.
LINE = re.compile(r"^\S+T(\d\d:\d\d:\d\d\.\d+)\S* \S+ (wrapper|k230-shell-rust|k230-theme-timing)\[\d+\]: (.*)$")


def main(path):
    for raw in open(path):
        m = LINE.match(raw.rstrip("\n"))
        if not m or not KEEP.search(m[3]):
            continue
        text = m[3]
        for k in sorted(IDS, key=len, reverse=True):
            text = text.replace(k, IDS[k])
        if "touch-down" in text:
            text = re.sub(r"(touch-down \d+) [\d.]+ [\d.]+", r"\1 x y", text)
        assert not re.search(r"\d+\.\d+\.\d+\.\d+|/home/|/run/", text), text
        print(m[1], text)


if __name__ == "__main__":
    main(sys.argv[1])
