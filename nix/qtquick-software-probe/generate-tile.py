#!/usr/bin/env python3
"""Regenerate the original 32x32 checker PNG used only by the Qt probe."""

from pathlib import Path
import struct
import zlib


def chunk(name, data):
    return (struct.pack(">I", len(data)) + name + data
            + struct.pack(">I", zlib.crc32(name + data) & 0xffffffff))


size = 32
rows = []
for y in range(size):
    row = bytearray([0])
    for x in range(size):
        row.extend((255, 186, 93, 255) if (x // 8 + y // 8) % 2
                   else (67, 136, 207, 255))
    rows.append(bytes(row))
payload = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
           + chunk(b"IEND", b""))
Path(__file__).with_name("tile.png").write_bytes(payload)
