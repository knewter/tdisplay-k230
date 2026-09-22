#!/usr/bin/env python3
"""Render the project boot-splash PNG without fonts or network assets.

The image is deliberately static: a dark field and a centred K230 mark.  Its
small built-in bitmap alphabet keeps the source portable and makes the PNG
reproducible with Python's standard library.
"""
import argparse
import struct
import zlib
from pathlib import Path

WIDTH, HEIGHT = 568, 1232
BACKGROUND = (10, 16, 32)
ACCENT = (82, 219, 215)
INK = (224, 247, 246)

GLYPHS = {
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00110", "00001", "00001", "10001", "01110"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
}


def rectangle(pixels, x, y, width, height, color):
    for row in range(max(0, y), min(HEIGHT, y + height)):
        start = (row * WIDTH + max(0, x)) * 3
        end = (row * WIDTH + min(WIDTH, x + width)) * 3
        pixels[start:end] = bytes(color) * max(0, min(WIDTH, x + width) - max(0, x))


def render_mark(pixels):
    scale = 22
    glyph_width, glyph_height, gap = 5 * scale, 7 * scale, scale
    text = "K230"
    mark_width = len(text) * glyph_width + (len(text) - 1) * gap
    left = (WIDTH - mark_width) // 2
    top = (HEIGHT - glyph_height) // 2

    # A restrained rule frames the mark without implying activity or status.
    rectangle(pixels, left, top - 42, mark_width, 4, ACCENT)
    rectangle(pixels, left, top + glyph_height + 38, mark_width, 4, ACCENT)
    for number, glyph in enumerate(text):
        origin = left + number * (glyph_width + gap)
        for row, cells in enumerate(GLYPHS[glyph]):
            for column, cell in enumerate(cells):
                if cell == "1":
                    rectangle(pixels, origin + column * scale, top + row * scale,
                              scale, scale, INK)


def png_chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)


def render(output):
    pixels = bytearray(bytes(BACKGROUND) * WIDTH * HEIGHT)
    render_mark(pixels)
    scanlines = b"".join(b"\0" + pixels[row * WIDTH * 3:(row + 1) * WIDTH * 3]
                         for row in range(HEIGHT))
    png = (b"\x89PNG\r\n\x1a\n" +
           png_chunk(b"IHDR", struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0)) +
           png_chunk(b"IDAT", zlib.compress(scanlines, level=9)) +
           png_chunk(b"IEND", b""))
    output.write_bytes(png)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("boot-splash.png"))
    render(parser.parse_args().out)
