# A no_std ttfx engine for U-Boot: feasibility and a working host-side port

Evidence class: **host build and test**, plus riscv64imac machine code run under
`qemu-riscv64-static` (user mode). Nothing here ran in U-Boot or on the board.
Collected 2026-10-30. The answer to "can ttfx execute in U-Boot" is **yes, bounded**:
the port is done on the host, the open items are board measurements and the U-Boot
link, both of which wait for the stage 1 install plan.

## What the port took

Upstream is `ttfx` 0.5.1 (commit `14ed274`, MIT), 45 085 lines. It holds two
engines: the original (`src/engine`, `src/effects`, `src/utils`: 4 953 + 14 556 +
3 881 lines) and the fast one (`src/fx`, 21 058 lines, threaded renderer, SIMD,
`std::arch`). The CLI's own parity suite checks the fast engine against the original
one, so the original engine is the reference and the one ported; `fx`, `cli.rs` and
`main.rs` stay `std`-only. The original engine's frame source is already
`Effect::next_frame(&mut EngineCtx) -> Option<String>`: a formatted ANSI frame per
call, which is the unit this change moves around.

The patch (`nix/ttfx-nostd/ttfx-nostd.patch`, against `14ed274`) is 73 files,
+2 271 / -1 464 lines by `git diff --numstat`:

| Area | Files | Lines | What |
| --- | ---: | ---: | --- |
| `src/effects/*.rs` | 39 | +1 605 / -1 087 | 37 effect configs: clap derives and `#[arg]` become `cfg_attr(feature = "cli", ...)`; a generated `impl Default` per config (310 fields in 27 shapes: the defaults were only in the clap attributes); `std::` paths to `core::`/`alloc::` |
| `src/engine/*.rs` | 13 | +212 / -161 | `terminal.rs` (Instant, io::Write printing, terminal size), `effect.rs` (run loops), `ctx.rs` (real clock), `error.rs`: gated behind `std` |
| `src/utils/*.rs` | 15 | +92 / -58 | `HashMap::new` to `default`, `OnceLock`, one `write!` to a Vec replaced, rng entropy and AVX-512 probe gated |
| new `sys.rs`, `fmath.rs`, `prelude.rs`; `lib.rs`, `Cargo.toml` | 6 | +362 / -158 | platform seams (below), features, registry by name |

Hand-written logic is about 600 lines; the rest is mechanical and was produced by
two scripts. Behaviour of the std CLI is unchanged: `cargo test --release` on the
patched tree passes (37 unit + 11 integration tests) and `--parity-dump` output is
byte-identical to the unpatched build for all 37 effects in both engines
(`TTFX_FX=1` and `0`, seed 3, 35x38 canvas): 74 of 74.

### What depended on std, and the replacement

| std use | Count in the ported tree | Replacement |
| --- | --- | --- |
| `HashMap` / `HashSet` (dozens of sites) | keys are small ints, hashed with ttfx's own deterministic `FxHasher` | `hashbrown` (no default hasher, no random seed) behind `sys::HashMap` |
| `thread_local!` | 4 sites (visual pool, format scratch, appearance memo, origin id) | `thread_local_compat!`: std's macro with `std`, a lazily initialised single-thread static without; `OnceLock` shim likewise |
| `Rc`, `RefCell`, `VecDeque`, `Vec`, `String`, `Box`, `format!` | everywhere | `alloc` |
| `std::time::Instant`, `SystemTime`, `thread::sleep`, `env`, `terminal_size`, `io::Write` | `Clock::Real`, framerate pacing, terminal sizing, the ANSI writers | gated behind `std`; the boot run uses `Clock::Virtual`, an explicit canvas and `ignore_terminal_dimensions` |
| signals, `mallopt`, threads, `std::arch` SIMD | `lib.rs` runtime, `fx` | stay in the `std` build only |
| clap | 339 `#[arg]` lines | `cfg_attr(feature = "cli")` |

The feature layout is `default = ["std", "cli", "all-effects"]`; `--no-default-features
--features nostd` is the engine on `core` + `alloc` + `hashbrown` + `libm`;
`effect-<name>` features choose which of the 37 effects `build_default(name)` offers,
so firmware images carry only the ones they play (size below). `ttfx::effects::build_default`
and `NAMES` are the no-CLI entry points.

## Floating point

66 files mention `f32`/`f64`; the calls are `powf` (61 uses, 39 in `easing.rs`, 8 in
`geometry.rs`, 4 in `spotlights`), `abs`, `sin`, `cos`, `sqrt`, `floor`, `ceil`,
`fract`, `hypot` and `round_ties_even`. So the effects **do** need floating point and,
in `no_std`, libm: `fmath.rs` maps them to the `libm` crate (a port of musl's math
library). `powf` is the parity risk: the std CLI calls the platform's libm (glibc), and
the Python original's results come from C `pow`. Measured: 0 differences in 37 effects
x 2 seeds x 2 texts on the host (`nostd-parity-full.txt`), and 0 in 37 effects for the
riscv64imac build under QEMU, but that is a finite sample, not a proof, so the design keeps
a cell-grid hash check at the continuation point (below) and a replay fallback.

## The U-Boot build and the FPU

The pinned U-Boot proper is built `-march=rv64imac... -mabi=lp64`: `readelf -A` of the
built `u-boot` and `spl/u-boot-spl` reports
`rv64i2p1_m2p0_a2p1_c2p0_zicsr2p0_zifencei2p0_zmmul1p0_zaamo1p0_zalrsc1p0_zca1p0` and the ELF
flags say "soft-float ABI"; the store path is the `.#uboot-k230` output
(`readelf-A.txt` beside the binary). Upstream's `arch/riscv/Makefile` in the pinned tarball derives
`-march` from the configured extensions (no F/D), and `arch/riscv/cpu/start.S` does not touch
`mstatus.FS`, so the FPU is off and a hard-float object would trap on its first
instruction. The Rust target must therefore be `riscv64imac-unknown-none-elf`, not
`riscv64gc` (nixpkgs' `riscv64-embedded` cross target is `riscv64gc-unknown-none-elf`, hard-float,
and is unusable here). Doubles are then software: `compiler_builtins` supplies
`__adddf3`, `__muldf3` and friends, and IEEE basic operations are correctly rounded either way,
which is why the frames match. Enabling the FPU in stage 1 (setting `mstatus.FS`, saving FP
state around `bootm`) would be faster and is a firmware change this proposal does not take.
Speed on the C908 in soft float: the same object code, run as a Linux static executable on the board, costs 32 ms for all 138 frames of `wipe` and at worst 3.08 ms per frame (`beams`) over the 37 effects (`board-engine-bench.txt`; every effect's frames equal the std ttfx's). That is Linux with caches on; U-Boot's cache state is <!-- UNVERIFIED: not measured in U-Boot; if its data cache is off the figures could be an order of magnitude worse. -->.

## Size

`libk230_ttfx_boot.a` built `opt-level = "z"`, LTO, `panic = "abort"`, riscv64imac,
position-independent, linked with `--gc-sections` (transcript: `nostd-sizes.txt`; sizes are the linked `.text` + `.rodata`;
`.eh_frame` (17 to 50 KB, listed in `nostd-sizes.txt`) is unneeded with `panic = "abort"` and can be discarded at link time):

| Effects compiled in | .text | .rodata | total |
| --- | ---: | ---: | ---: |
| `wipe` only | 107 202 | 18 032 | 125 234 |
| 8-effect subset (`wipe middleout expand slide errorcorrect print decrypt scattered`) | 175 310 | 22 320 | 197 630 |
| all 37 | 479 094 | 40 952 | 520 046 |

The U-Boot-proper slot is 1 048 576 bytes and the DMA-request candidate used 385 932
(`docs/evidence/game-of-life/stage1-install-recovery-proposal.md` on the Life branch), so a
subset fits with room for Life, and all 37 effects leave about 140 KB. The slot is the binding
constraint, so firmware carries a subset.

## Memory

Peak heap per effect, measured with a counting allocator, over the K230 banner on a 35x38
canvas (`k230_ttfx_boot` example `mem`, host x86-64, so sizes of pointers match
riscv64). Everything is still live at the end of a run, because ttfx interns each distinct visual
in a pool that lives for the run:

| effect | frames | peak heap KiB | live at end KiB | host ms |
| --- | ---: | ---: | ---: | ---: |
| beams | 321 | 8549 | 8549 | 38 |
| binarypath | 842 | 11953 | 11953 | 30 |
| blackhole | 894 | 2545 | 2545 | 17 |
| bouncyballs | 417 | 1788 | 1788 | 8 |
| bubbles | 521 | 2355 | 2355 | 6 |
| burn | 324 | 9315 | 9315 | 15 |
| colorshift | 528 | 2703 | 2703 | 15 |
| crumble | 430 | 2553 | 2553 | 17 |
| decrypt | 753 | 3260 | 3260 | 14 |
| errorcorrect | 274 | 1280 | 1280 | 3 |
| expand | 50 | 1489 | 1489 | 3 |
| fireworks | 1211 | 2521 | 2521 | 15 |
| highlight | 129 | 1098 | 1098 | 2 |
| laseretch | 494 | 12155 | 12155 | 20 |
| matrix | 1452 | 1388 | 1388 | 25 |
| middleout | 94 | 1566 | 1566 | 2 |
| orbittingvolley | 1387 | 1687 | 1687 | 4 |
| overflow | 57 | 1493 | 1492 | 3 |
| pour | 256 | 1666 | 1666 | 13 |
| print | 308 | 1844 | 1844 | 3 |
| rain | 235 | 1607 | 1607 | 5 |
| randomsequence | 241 | 1101 | 1101 | 2 |
| rings | 1398 | 13236 | 13236 | 85 |
| scattered | 120 | 1589 | 1589 | 4 |
| slice | 176 | 1000 | 1000 | 4 |
| slide | 110 | 1521 | 1521 | 3 |
| smoke | 180 | 6269 | 6269 | 24 |
| spotlights | 601 | 1535 | 1535 | 34 |
| spray | 337 | 1815 | 1815 | 7 |
| swarm | 3655 | 3112 | 3112 | 36 |
| sweep | 220 | 3816 | 3816 | 30 |
| synthgrid | 629 | 6243 | 6243 | 28 |
| thunderstorm | 623 | 3590 | 3590 | 22 |
| unstable | 250 | 2072 | 2071 | 8 |
| vhstape | 687 | 2561 | 2561 | 29 |
| waves | 512 | 4043 | 4043 | 23 |
| wipe | 138 | 1188 | 1188 | 4 |

Most effects peak at 1 to 4 MiB; `beams` (8.5), `burn` (9.3), `binarypath` (12), `laseretch`
(12) and `rings` (13) are the large ones. U-Boot proper's pool is `CONFIG_SYS_MALLOC_LEN`, which
the pinned `common/Kconfig` defaults to `0x400000` (4 MiB) and which the K230 defconfig does not
override (`CONFIG_SYS_MALLOC_F_LEN=0x40000` is the early pre-relocation pool). So the Rust side
must not use U-Boot's malloc as is. The library takes an **arena** from the host
(`ttfx_fw_init`) with its own first-fit allocator, and the integration chooses either to raise
`CONFIG_SYS_MALLOC_LEN` (to 32 MiB, say) and take the arena from it, or to point it at a fixed
free DRAM range during stage 1. Which addresses are free is checked with the Life change's
memory-map tool; I have not done that here.

## How a Rust staticlib links into U-Boot in Nix

`nix/ttfx-boot` is a crate with a C ABI (`ttfx_boot.h`: `ttfx_fw_init`, `ttfx_fw_new`,
`ttfx_fw_next`, `ttfx_fw_free`, and a host-provided `ttfx_fw_panic`). Built with
`cargo rustc --lib --crate-type staticlib --target riscv64imac-unknown-none-elf`,
`-C relocation-model=pic` (U-Boot is a PIE and relocates itself), `panic = "abort"`. Linking
`--gc-sections` with only a stub for `ttfx_fw_panic` resolved every symbol: no libc is needed,
`memcpy`/`memset` come from `compiler_builtins`. Nixpkgs' rustc has no std for that target, so
`nix/ttfx-boot/default.nix` adds the official `rust-std` tarball for the same rustc version
(hash published beside it on static.rust-lang.org) to a sysroot, applies the ttfx patch with
`applyPatches`, and vendors the three registry crates (`hashbrown`, `libm`, `unicode-width`) from a
committed `Cargo.lock`. U-Boot would then add the `.a` to `PLATFORM_LIBS` and a C glue file
calling the ABI, on the model of the Life change's `k230_boot_life.c`; that is a stage 1 edit and
waits for the operator. The Nix derivation's build is queued behind the shared build lock
and is recorded in the task list, not claimed here.

## Parity

`tests/test_ttfx_nostd.py` (output: `nostd-parity-full.txt`):

- The `no_std` engine as a host program (libm + hashbrown) against `ttfx --parity-dump` for all
  37 effects x seeds 3 and 11 x two texts (the K230 banner and `TDISPLAY / K230`), canvas 35x38:
  148 of 148 byte-identical streams.
- The freestanding riscv64imac staticlib, linked with `nix/ttfx-boot/bench/bench.c` into a static
  soft-float executable, run under `qemu-riscv64-static`, FNV-1a of every frame byte against the std
  output: 37 of 37 (seed 3, K230 banner).

## Limits

- QEMU user mode proves the machine code computes the same frames. It says nothing about
  speed, caches, U-Boot's relocation, or the arena. `bench.c` is a Linux-hosted static executable
  of the same objects: running it on the board gave the C908 timings above (task 2.8); the cost inside U-Boot is task 4.3.
- The upstream patch has not been offered upstream; it is written to be (std CLI unchanged,
  its test suite passes, features default to the old behaviour).
- ttfx's `thread_local!` visual pool leaks by design (`&'static` visuals); a boot run is finite and the arena
  is dropped when stage 1 ends.
