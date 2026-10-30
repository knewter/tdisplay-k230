# ttfx research for the-boot-plays-terminal-text-effects

Evidence class: **host** (read-only source reading and host runs). Nothing here
is a board or boot observation. Collected 2026-10-30.

## The program

- Upstream: `github.com/omacom-io/ttfx`, tag `v0.5.1`, commit `14ed274`
  (the revision `nix/ttfx.nix` pins). A Rust port of TerminalTextEffects.
- Licence: MIT. `LICENSE` names 37signals / omacom-io and ChrisBuilds
  (TerminalTextEffects); the copy at `nix/ttfx/LICENSE` is byte-identical to the
  tag's (`cmp`), and `nix/ttfx.nix` installs it with `NOTICE` under
  `share/doc/ttfx`.
- Layout: one crate, library plus binary. `src/engine` (original engine),
  `src/fx` (the fast engine the binary prefers), `src/effects` (37 effects),
  `src/utils`, `src/cli.rs`, `src/main.rs`. About 16 000 lines in
  `src/engine`, `src/fx` and `src/utils`. No `build.rs`.
- Dependencies (`Cargo.toml`): `clap` 4 (derive), `clap_complete`,
  `terminal_size`, `unicode-width`. `Cargo.lock` has 30 packages; the lock at
  `nix/ttfx/Cargo.lock` is identical to the tag's. `src/lib.rs` calls `signal`,
  `raise` and glibc `mallopt` through hand-written `extern "C"`.
- Library as a frame source: `ttfx::fx::Engine` can be driven frame by frame
  (`src/fx/run.rs` `dump_effect`), but the interactive run loop owns a
  `Terminal` and writes ANSI to stdout; there is no cell-and-colour callback.
- Deterministic frame mode: `--seed N --parity-dump [--max-frames M]` (hidden
  flags; `--virtual-clock` is implied) writes `<byte length>\n<frame>\n` per
  frame and `frames=N` on stderr. A frame is UTF-8, rows joined by `\n`, each
  coloured cell `ESC[38;2;r;g;bm<char>ESC[0m`, blanks as spaces.
- Target build: already exists. `.#ttfx` (`flake.nix`, `nix/ttfx.nix`) builds the
  riscv64 binary the exhibition uses (3.3 MB, ELF RISC-V, dynamically linked).

## Method

`ttfx` was built on the host from a checkout of `14ed274` with
`cargo build --release` (cargo 1.91.0-nightly, x86-64). Over the committed
banner `nix/exhibition/K230.txt` (6 rows by 33 columns) each of the 37
effects ran twice with `tools/textfx_frames.py survey` on the real panel grid
(35 columns by 38 rows: 568x1232 pixels at 16x32-pixel cells), seed 3, effect
defaults, `--frame-rate 30`, `--anchor-canvas c --anchor-text c`:

```
python3 -I tools/textfx_frames.py survey --ttfx <ttfx> --banner nix/exhibition/K230.txt --seed 3
```

Columns: frames the effect produced; whether two runs gave identical bytes;
SHA-256 of the whole dump (first 12 hex); distinct code points above U+007F;
the largest number of cells changed between consecutive frames; bytes of the
uncompressed TFXS delta sequence (format in the tool's docstring).

Every frame of every effect parsed with only SGR `0` and `38;2;r;g;b`, no
background colour, no double-width characters and no code point outside the
BMP; the parser raises on anything else.

| effect | frames | repeat equal | dump sha256 (12) | non-ASCII glyphs | max changed cells | sequence bytes |
| --- | ---: | :---: | --- | ---: | ---: | ---: |
| beams | 321 | yes | 39ab25024c97 | 13 | 194 | 213173 |
| binarypath | 842 | yes | 888daef41548 | 7 | 131 | 478374 |
| blackhole | 894 | yes | cac0d8cc4528 | 15 | 168 | 109585 |
| bouncyballs | 417 | yes | 811c65246a23 | 7 | 91 | 95926 |
| bubbles | 521 | yes | e0a3b40e7be7 | 7 | 100 | 97695 |
| burn | 324 | yes | 7776f92c229c | 12 | 178 | 84330 |
| colorshift | 528 | yes | dd4b222f0e57 | 7 | 178 | 324936 |
| crumble | 430 | yes | dcd4f2987c72 | 7 | 229 | 141256 |
| decrypt | 753 | yes | a5c8100a4f59 | 429 | 178 | 130989 |
| errorcorrect | 274 | yes | f0aace8921d1 | 15 | 178 | 19410 |
| expand | 50 | yes | 4c7d7d1192f5 | 7 | 40 | 6033 |
| fireworks | 1211 | yes | fd588cc7c4b6 | 7 | 47 | 122609 |
| highlight | 129 | yes | 5e7222e3f2ba | 7 | 178 | 7878 |
| laseretch | 494 | yes | 3c9ab942aaf2 | 7 | 87 | 121301 |
| matrix | 1452 | yes | 50fbe0aa51ef | 42 | 66 | 154066 |
| middleout | 94 | yes | a7607398704f | 7 | 151 | 12960 |
| orbittingvolley | 1387 | yes | e0dea31dd204 | 7 | 16 | 107953 |
| overflow | 57 | yes | 6a698134e518 | 7 | 630 | 61095 |
| pour | 256 | yes | f5184118f5e8 | 7 | 69 | 55641 |
| print | 308 | yes | 1f6b3899aeaa | 10 | 220 | 39967 |
| rain | 235 | yes | 7258f60f958b | 7 | 86 | 53877 |
| randomsequence | 241 | yes | afb0f9f2484c | 7 | 8 | 10482 |
| rings | 1398 | yes | 87c17d59f71c | 7 | 213 | 490910 |
| scattered | 120 | yes | a801278400c6 | 7 | 182 | 44113 |
| slice | 176 | yes | cbdd5de42fc1 | 7 | 260 | 36875 |
| slide | 110 | yes | c70bb491494d | 7 | 79 | 20244 |
| smoke | 180 | yes | 211677f4404d | 10 | 180 | 40159 |
| spotlights | 601 | yes | 34ad6e2c3139 | 7 | 178 | 81937 |
| spray | 337 | yes | 46cdce082894 | 7 | 28 | 23225 |
| swarm | 3655 | yes | 5dca0ad103b1 | 7 | 32 | 234345 |
| sweep | 220 | yes | aa02d7e1d4aa | 10 | 228 | 93306 |
| synthgrid | 629 | yes | 9ab98af1aa8a | 12 | 60 | 145476 |
| thunderstorm | 623 | yes | c428b3cd7c50 | 7 | 222 | 105284 |
| unstable | 250 | yes | d0620a1e7860 | 7 | 275 | 128338 |
| vhstape | 687 | yes | ff5e4167b916 | 7 | 178 | 310869 |
| waves | 512 | yes | 6f765beccd0f | 14 | 142 | 227744 |
| wipe | 138 | yes | 0cac956c2d5a | 7 | 60 | 16506 |

## Limits

- This is a host x86-64 build. Task 1.2 compares the packaged riscv64 binary's
  dump hashes with these on the board; until it is ticked, equality across
  architectures is not claimed.
- Frame counts are for these arguments (effect defaults). Effect options
  change frame counts and glyph sets and would change the digest in the
  sequence header.
- `--parity-dump` is a hidden flag. The pinned revision and the golden hashes in
  `tests/test_textfx_frames.py` are what protect the format.
