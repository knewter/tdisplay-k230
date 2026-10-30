#!/usr/bin/env python3
"""Turn the output of the pinned `ttfx` into deterministic character-cell frames.

Used by the-boot-plays-terminal-text-effects.  `ttfx --seed N --parity-dump`
(a flag its own parity harness uses; hidden from --help) writes each frame as
`<decimal byte length>\\n<frame bytes>\\n`.  A frame is UTF-8 text, rows joined
by `\\n`, every visible cell prefixed by `ESC[38;2;r;g;bm` and followed by
`ESC[0m`; blank cells are plain spaces.  Over the K230 banner all 37 effects
use only SGR 0 and 38;2.

Subcommands:
  sequence  run ttfx, write a TFXS cell-sequence file, print hashes
  survey    run every effect twice, print a markdown table
  hashes    print per-frame cell-grid hashes of a TFXS file

TFXS (little-endian):
  0   char[4] "TFXS"
  4   u16 version (1)       6  u16 cols      8  u16 rows     10 u16 fps
  12  u32 frame count       16 u32 seed (low 32 bits)
  20  u32 args digest       24 u32 payload bytes
  28  u32 FNV-1a(payload)
  32  frames: u16 changed-cell count, then per cell
        u16 cell index (row * cols + col), u16 code point, u8 r, u8 g, u8 b
A frame lists the cells that differ from the previous frame (frame 0 differs
from an all-blank grid).  Blank = code point 0x20 with colour 0; a space is
always stored with colour 0.

Cell-grid hash (also computed by src/textfx.c): FNV-1a 32 over, for every
cell in index order, cp low byte, cp high byte, r, g, b.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
import subprocess
import sys
import unicodedata

FNV_OFFSET = 0x811C9DC5
FNV_PRIME = 0x01000193
MAGIC = b"TFXS"
VERSION = 1
HEADER = struct.Struct("<4sHHHHIIIII")  # magic ver cols rows fps nframes seed digest payload fnv
assert HEADER.size == 32

EFFECTS = (
    "beams binarypath blackhole bouncyballs bubbles burn colorshift crumble "
    "decrypt errorcorrect expand fireworks highlight laseretch matrix middleout "
    "orbittingvolley overflow pour print rain randomsequence rings scattered "
    "slice slide smoke spotlights spray swarm sweep synthgrid thunderstorm "
    "unstable vhstape waves wipe"
).split()


class TfxError(ValueError):
    pass


def fnv1a(data: bytes, h: int = FNV_OFFSET) -> int:
    for b in data:
        h = ((h ^ b) * FNV_PRIME) & 0xFFFFFFFF
    return h


Cell = tuple  # (codepoint, r, g, b)
BLANK: Cell = (0x20, 0, 0, 0)


def grid_bytes(cells: list[Cell]) -> bytes:
    out = bytearray()
    for cp, r, g, b in cells:
        out += bytes((cp & 0xFF, cp >> 8, r, g, b))
    return bytes(out)


def grid_hash(cells: list[Cell]) -> int:
    return fnv1a(grid_bytes(cells))


def ttfx_command(ttfx: str, effect: str, seed: int, cols: int, rows: int,
                 fps: int, max_frames: int | None, extra: list[str]) -> list[str]:
    cmd = [ttfx, "--seed", str(seed), "--parity-dump",
           "--canvas-width", str(cols), "--canvas-height", str(rows),
           "--ignore-terminal-dimensions", "--frame-rate", str(fps),
           "--anchor-canvas", "c", "--anchor-text", "c"]
    if max_frames is not None:
        cmd += ["--max-frames", str(max_frames)]
    return cmd + [effect] + extra


def split_dump(stream: bytes) -> list[bytes]:
    """Split a --parity-dump stream into frame byte strings."""
    frames, pos = [], 0
    while pos < len(stream):
        nl = stream.index(b"\n", pos)
        n = int(stream[pos:nl])
        start = nl + 1
        frame = stream[start:start + n]
        if len(frame) != n or stream[start + n:start + n + 1] != b"\n":
            raise TfxError(f"truncated or malformed frame at byte {pos}")
        frames.append(frame)
        pos = start + n + 1
    return frames


def parse_frame(frame: bytes, cols: int, rows: int) -> list[Cell]:
    """Parse one frame into rows*cols cells; reject anything outside SGR 0 / 38;2."""
    text = frame.decode("utf-8")
    lines = text.split("\n")
    if len(lines) != rows:
        raise TfxError(f"frame has {len(lines)} rows, expected {rows}")
    cells: list[Cell] = []
    for y, line in enumerate(lines):
        fg = (0, 0, 0)
        col = 0
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == "\x1b":
                if line[i + 1:i + 2] != "[":
                    raise TfxError("unsupported escape")
                end = line.index("m", i)
                params = line[i + 2:end].split(";")
                if params == ["0"] or params == [""]:
                    fg = (0, 0, 0)
                elif len(params) == 5 and params[0] == "38" and params[1] == "2":
                    fg = tuple(int(p) for p in params[2:])
                    if any(not 0 <= c <= 255 for c in fg):
                        raise TfxError("colour out of range")
                else:
                    raise TfxError(f"unsupported SGR {line[i + 2:end]!r}")
                i = end + 1
                continue
            if unicodedata.east_asian_width(ch) in ("W", "F"):
                raise TfxError(f"double-width character U+{ord(ch):04X}")
            if ord(ch) > 0xFFFF:
                raise TfxError(f"character outside the BMP U+{ord(ch):06X}")
            cp = ord(ch)
            cells.append(BLANK if cp == 0x20 else (cp, *fg))
            col += 1
            i += 1
        if col != cols:
            raise TfxError(f"row {y} has {col} cells, expected {cols}")
    return cells


def run_ttfx(ttfx: str, banner: bytes, effect: str, seed: int, cols: int, rows: int,
             fps: int, max_frames: int | None, extra: list[str]) -> list[bytes]:
    cmd = ttfx_command(ttfx, effect, seed, cols, rows, fps, max_frames, extra)
    p = subprocess.run(cmd, input=banner, capture_output=True, timeout=300)
    if p.returncode != 0:
        raise TfxError(f"{effect}: ttfx exit {p.returncode}: {p.stderr.decode(errors='replace')[:200]}")
    return split_dump(p.stdout)


def encode_sequence(frames: list[list[Cell]], cols: int, rows: int, fps: int,
                    seed: int, digest: int) -> bytes:
    payload = bytearray()
    prev = [BLANK] * (cols * rows)
    for cells in frames:
        changed = [i for i, c in enumerate(cells) if c != prev[i]]
        if len(changed) > 0xFFFF:
            raise TfxError("too many changed cells")
        payload += struct.pack("<H", len(changed))
        for i in changed:
            cp, r, g, b = cells[i]
            payload += struct.pack("<HHBBB", i, cp, r, g, b)
        prev = cells
    head = HEADER.pack(MAGIC, VERSION, cols, rows, fps, len(frames), seed & 0xFFFFFFFF,
                       digest & 0xFFFFFFFF, len(payload), fnv1a(bytes(payload)))
    return head + bytes(payload)


def decode_sequence(data: bytes):
    """Return (header dict, list of per-frame cell lists)."""
    if len(data) < 32:
        raise TfxError("short")
    magic, ver, cols, rows, fps, n, seed, digest, plen, pfnv = HEADER.unpack_from(data)
    if magic != MAGIC or ver != VERSION:
        raise TfxError("bad magic or version")
    payload = data[32:32 + plen]
    if len(payload) != plen or fnv1a(payload) != pfnv:
        raise TfxError("payload checksum")
    cells = [BLANK] * (cols * rows)
    frames, pos = [], 0
    for _ in range(n):
        (k,) = struct.unpack_from("<H", payload, pos)
        pos += 2
        for _ in range(k):
            i, cp, r, g, b = struct.unpack_from("<HHBBB", payload, pos)
            pos += 7
            cells[i] = (cp, r, g, b)
        frames.append(list(cells))
    if pos != plen:
        raise TfxError("trailing payload bytes")
    return dict(cols=cols, rows=rows, fps=fps, frames=n, seed=seed, digest=digest), frames


def args_digest(effect: str, extra: list[str], banner: bytes, cols: int, rows: int, fps: int) -> int:
    ident = "|".join([effect, *extra, str(cols), str(rows), str(fps)]).encode() + b"|" + banner
    return fnv1a(ident)


def build_sequence(ttfx, banner, effect, seed, cols, rows, fps, max_frames, extra):
    raw = run_ttfx(ttfx, banner, effect, seed, cols, rows, fps, max_frames, extra)
    frames = [parse_frame(f, cols, rows) for f in raw]
    data = encode_sequence(frames, cols, rows, fps, seed,
                           args_digest(effect, extra, banner, cols, rows, fps))
    return raw, frames, data


def cmd_sequence(a):
    banner = open(a.banner, "rb").read()
    raw, frames, data = build_sequence(a.ttfx, banner, a.effect, a.seed, a.cols, a.rows,
                                       a.fps, a.max_frames, a.extra)
    if a.out:
        with open(a.out, "wb") as f:
            f.write(data)
    changed = [sum(1 for i, c in enumerate(fr) if c != (frames[k - 1][i] if k else BLANK))
               for k, fr in enumerate(frames)]
    print(f"effect={a.effect} seed={a.seed} grid={a.cols}x{a.rows} fps={a.fps} frames={len(frames)}")
    print(f"sequence bytes={len(data)} sha256={hashlib.sha256(data).hexdigest()}")
    print(f"changed cells per frame: max={max(changed)} mean={sum(changed) / len(changed):.1f}")
    print(f"last-frame cell hash=0x{grid_hash(frames[-1]):08x}")
    print(f"dump sha256={hashlib.sha256(b''.join(raw)).hexdigest()}")
    if a.per_frame:
        for k, fr in enumerate(frames):
            print(f"frame {k} 0x{grid_hash(fr):08x}")


def cmd_hashes(a):
    head, frames = decode_sequence(open(a.file, "rb").read())
    print(head)
    for k, fr in enumerate(frames):
        print(f"frame {k} 0x{grid_hash(fr):08x}")


def cmd_survey(a):
    banner = open(a.banner, "rb").read()
    print("| effect | frames | repeat equal | dump sha256 (12) | non-ASCII glyphs | max changed cells | sequence bytes |")
    print("| --- | ---: | :---: | --- | ---: | ---: | ---: |")
    for effect in EFFECTS:
        try:
            raw1 = run_ttfx(a.ttfx, banner, effect, a.seed, a.cols, a.rows, a.fps, a.max_frames, [])
            raw2 = run_ttfx(a.ttfx, banner, effect, a.seed, a.cols, a.rows, a.fps, a.max_frames, [])
            frames = [parse_frame(f, a.cols, a.rows) for f in raw1]
        except (TfxError, subprocess.TimeoutExpired) as e:
            print(f"| {effect} | - | - | - | - | - | {e} |")
            continue
        glyphs = {c[0] for fr in frames for c in fr if c[0] > 0x7F}
        mx = max(sum(1 for i, c in enumerate(fr) if c != (frames[k - 1][i] if k else BLANK))
                 for k, fr in enumerate(frames))
        data = encode_sequence(frames, a.cols, a.rows, a.fps, a.seed, 0)
        eq = "yes" if raw1 == raw2 else "NO"
        sha = hashlib.sha256(b"".join(raw1)).hexdigest()[:12]
        print(f"| {effect} | {len(frames)} | {eq} | {sha} | {len(glyphs)} | {mx} | {len(data)} |")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--ttfx", required=True)
        p.add_argument("--banner", required=True)
        p.add_argument("--seed", type=int, default=1)
        p.add_argument("--cols", type=int, default=35)
        p.add_argument("--rows", type=int, default=38)
        p.add_argument("--fps", type=int, default=30)
        p.add_argument("--max-frames", type=int, default=None)

    s = sub.add_parser("sequence")
    common(s)
    s.add_argument("--effect", required=True)
    s.add_argument("--out")
    s.add_argument("--per-frame", action="store_true")
    s.add_argument("extra", nargs="*", help="effect arguments after --")
    s.set_defaults(fn=cmd_sequence)
    v = sub.add_parser("survey")
    common(v)
    v.set_defaults(fn=cmd_survey)
    h = sub.add_parser("hashes")
    h.add_argument("file")
    h.set_defaults(fn=cmd_hashes)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    try:
        main()
    except TfxError as e:
        print(f"textfx_frames: {e}", file=sys.stderr)
        sys.exit(1)
