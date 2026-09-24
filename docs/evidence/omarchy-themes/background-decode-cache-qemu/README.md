# Theme-switch wallpaper decode: prepared-generation cache

Addresses the follow-up named in `docs/evidence/omarchy-themes/commit-fix-board/README.md`:
"Each switch takes 4-5 s, mostly decoding full-size photo backgrounds on the
K230, which is a known follow-up." This is a host + headless-QEMU
measurement, never a board, glass, or real-finger result.

## Options evaluated

- **(a) chosen: cache a decoded, pre-cropped panel-sized image inside the
  prepared generation directory.** `tools/theme_activate.py`'s `prepare()`
  already stages every theme (built-in or user) into an immutable,
  hash-identified, one-shot directory before any commit. This change adds one
  file to that directory, `background.cache` (magic + width + height + mode
  header, then raw native-endian Cairo ARGB32 bytes at the exact panel
  geometry), written once via a hidden `k230-shell-rust --write-wallpaper-cache
  SOURCE GENERATION_ROOT WIDTH HEIGHT` verb that reuses the existing audited
  decode/bounds code (`nix/rust-shell-client/src/background_decode.rs`)
  unchanged. `BackgroundCache::render` now takes the generation root and
  prefers this file when it exists and matches the requested geometry/mode
  exactly; a missing, truncated, or mismatched cache is silently a full
  decode, byte-for-byte the pre-existing behavior. Applied for every prepared
  generation, so it covers built-ins (including catppuccin/catppuccin-latte)
  and user themes (`~/.config/omarchy/themes`) alike, and also for the one
  pinned pointerless-default generation via a native-arch (`buildPackages`)
  build of the same binary invoked at Nix build time
  (`nix/handheld-theme-default/default.nix`) -- see "Startup" below.

- **(b) rejected: codec-level reduced-resolution decode** (JPEG DCT scaling /
  WebP scaled decode) so a first-ever decode is cheaper too, not just
  repeats. Checked both pinned decoders actually in the dependency tree:
  `zune-jpeg 0.5.15` (`~/.cargo/registry/src/*/zune-jpeg-0.5.15/src/decoder.rs`)
  exposes no scale-factor option, and `image-webp 0.2.4`
  (`.../image-webp-0.2.4/src/decoder.rs`) only exposes `read_image`/`read_frame`
  at full resolution -- neither the `image = "=0.25.10"` crate nor its pinned
  backends can do a reduced-resolution decode without vendoring new C bindings
  (libjpeg-turbo/libwebp), which would need new build-from-source/blob
  accounting and cross-compilation surface disproportionate to the win once
  (a) is in place. Rejected for this change.

- **(c) rejected for this change: build-time bounded derivatives for
  catppuccin/catppuccin-latte too.** Real, but narrow once (a) exists: it
  would only shrink the one-time first decode of those two themes, at the
  cost of breaking `SOURCE.md`'s documented byte-identical/pinned-identity
  guarantee for catppuccin's backgrounds (`source-inventory.json`, framed
  tree digests, `bundled-report.json`/`default-report.json`, and
  `tests/test_handheld_theme_bundle.py`'s full-resolution assertions), which
  would all need correct regeneration. Left as a follow-up if a still-slow
  first activation of those two themes is later judged worth that blast
  radius.

- **(d) not implemented as originally scoped: move decode to a worker
  thread inside the Rust process.** Superseded by an emergent property of
  (a): the expensive part now runs once, in `tools/theme_activate.py`'s own
  short-lived subprocess (the hidden `--write-wallpaper-cache` verb), which
  is a *separate process* from the Rust shell's event loop -- not scheduled
  on it, using the K230's second core if the first is busy. The Rust
  receiver's own Prepare/Commit handling now only ever reads a small cache
  file (bounded, a few ms) for any generation whose `prepare()` already ran,
  so the event loop is not blocked by a multi-second decode in the common
  case. A true cold generation (never prepared, no pinned build-time cache)
  still decodes synchronously in the Rust event loop exactly as before;
  moving that specific remaining case to a worker thread is a candidate
  follow-up, not done here.

## Rust unit/integration evidence (host)

`cargo test --offline` in `nix/rust-shell-client`: 84 + 7 + 14 + 7 + 8 tests
pass, including two new cases in `tests/background_decode_module.rs`:
`wallpaper_cache_hit_bypasses_a_changed_source_and_a_mismatch_falls_back`
(a cache hit returns the bytes written at cache time even after the source
file changes on disk; a geometry mismatch or missing cache file falls back
to a correct fresh decode) and
`wallpaper_cache_write_rejects_a_video_or_unsupported_destination`.
`examples/verify_bundled_default.rs` now also passes `generation_root`, and
passed against the real built package (see below).

## Host micro-benchmark (x86_64 dev machine, not the K230)

Using the actual pinned `catppuccin` background,
`themes/catppuccin/backgrounds/2-waves.webp` (3840x2160, lossless WebP,
639,444 bytes, from the pinned `omacom/omarchy@28ceaae7` source), decoding to
the panel's exact 568x1232 crop:

| Path | Time | Notes |
| --- | ---: | --- |
| Cold decode (`BackgroundCache::render`, no cache) | 189 ms | release build, x86_64, not representative of the K230's absolute time |
| Cache hit (`background.cache` present) | 2.4 ms | 79.7x faster on this host; K230 ratio will differ but the mechanism (skip decode+resize entirely) is geometry-independent |

This is a relative-speedup sanity check only; it is not a K230 timing.

## Headless QEMU + `cpulimit` throttle (real IPC path, real store paths)

Ran the actual runtime path -- `tools/theme_catalog.py preview` then
`activate`, over the real Unix-socket two-phase protocol
(`tools/theme_transaction.py`), against a real `sway-unwrapped` compositor
and a real `k230-shell-rust`, both under `qemu-riscv64-static`, with the Rust
process throttled to 20% CPU via `cpulimit` -- the same harness shape as
`tests/test_theme_commit_under_occlusion_runtime.py`, extended with wall-clock
timing around each `preview`+`activate` pair (script not committed; the
exact invocation to reproduce is below). This is a QEMU+throttle result, not
a board result, but it is the real transaction path end to end, not a
decode-only microbenchmark.

Store paths (this worktree, `perf/theme-background-decode`):
- sway: `/nix/store/0rv28hkhciv5w5mvnxx47wp9l5ml2kqb-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`
  (from `nix-store -qR` of `.#card-shell`)
- rust shell: `/nix/store/xv0f43wmqrvh05rdbcjnkkg8r284dcky-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust`
  (`.#handheld-shell-rust`)
- theme bundle: `/nix/store/rf4b00manjj2rhvcgfa2rdzwmlx3hdpv-handheld-theme-default-28ceaae7`
  (`.#handheld-theme-default`; contains `background.cache` for the pinned
  bundled generation, see "Startup" below)
- icons: `/nix/store/in3nc21zx02xiz2rdp5bpq36719x3axd-handheld-theme-icons-25.10.3`
  (`.#handheld-theme-icons`)
- client: `/nix/store/qpjim9wgpwcwjnyvg6zn0qgyf5v9g746-card-composition-probe-client-riscv64-unknown-linux-gnu-0.1/bin/card-composition-probe-client`
  (`nix-store -qR` of `.#card-composition-probe`)

Sequence: activate catppuccin-latte (never prepared before, cold), activate
catppuccin (never prepared in this run's fresh state root, cold), then
repeat both twice more.

Baseline (Python `prepare()` never given `--wallpaper-cache-tool`; the Rust
receiver still checks for a cache file, finds none, and falls back to a full
decode -- this is exactly today's unpatched behavior):

| Switch | Wall time |
| --- | ---: |
| catppuccin-latte (cold) | 3509 ms |
| catppuccin (cold) | 7337 ms |
| catppuccin-latte (repeat) | 1830 ms |
| catppuccin (repeat) | **failed**: `"fanout prepare failed; both receivers restored"` after the Rust log showed acks stretching past the transaction's 8 s exchange budget (`rust-shell 24914ms wallpaper-commit`, from a 0ms-based log) |

Patched (`--wallpaper-cache-tool` given, exercising this change):

| Switch | Wall time |
| --- | ---: |
| catppuccin-latte (cold; cache built during this call) | 892 ms |
| catppuccin (cold; cache built during this call) | 1517 ms |
| catppuccin-latte (repeat; cache hit both sides) | 355 ms |
| catppuccin (repeat; cache hit both sides) | 362 ms |
| catppuccin-latte (repeat again) | 358 ms |

Even the "cold" patched numbers are faster than baseline's cold numbers,
because the decode that produces the cache runs in `theme_catalog.py`'s own
subprocess, which `cpulimit` never throttles (only the long-lived `rust
--serve` process is throttled) -- consistent with the "(d) superseded"
argument above. The baseline's fourth switch failing outright, after
progressively longer waits, reproduces the shape of the historical
`"commit failed and fanout rollback was not acknowledged"` board bug under
sustained throttled load; the patched run shows no such degradation across
five consecutive switches.

Reproduce (paths above; `--use-cache-tool` toggles the two tables):

```sh
python3 tests/test_theme_commit_under_occlusion_runtime.py \
  --sway /nix/store/.../bin/sway --rust /nix/store/.../bin/k230-shell-rust \
  --client /nix/store/.../bin/card-composition-probe-client \
  --theme-bundle /nix/store/...-handheld-theme-default-28ceaae7 \
  --icons /nix/store/...-handheld-theme-icons-25.10.3 \
  --tools nix/omarchy-theme-tools/upstream --output /tmp/k230-bd-1
```
proves the two-phase protocol itself still tolerates occlusion+throttle with
this change. On this dev host, the unmodified, committed test at its default
`--throttle 20` timed out during Scenario B's very first `prepare` exchange
against both this change's build (`generation_b` there is prepared without
`--wallpaper-cache-tool`, so it takes the identical, unmodified decode path)
**and** against an unmodified `origin/master` build
(`k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0` built from
`git+file://…?ref=master#handheld-shell-rust`/`#handheld-theme-default`) --
master's rollback exchange itself then also timed out
(`"fanout prepare failed and rollback was not acknowledged"`), a strictly
worse outcome than this change's build, whose rollback still completed
(`"...both receivers restored"`). This confirms the timeout is this host's
QEMU-plus-`cpulimit` decode throughput at `-l 20` against catppuccin's real,
uncached, full-resolution background -- a pre-existing environment
sensitivity of that exact default, not a regression -- and both builds pass
Scenario A and B cleanly at `--throttle 60`. The wall-clock table above used
a local, uncommitted variant of that same harness that additionally times
`preview`+`activate` and adds `--wallpaper-cache-tool`; the coordinator can
reconstruct it from `tools/theme_catalog.py`'s new `--wallpaper-cache-tool`
flag plus `time.monotonic()` around the existing
`theme_cli("activate", ...)` calls in that file.

`tests/test_real_theme_paired_runtime.py --check-restart` was also run
against both this change's build and the same unmodified `origin/master`
build; both fail identically at the same point
(`app_after = wait(expanded_app, 5)` timing out waiting for the card's
expanded-app pixel to settle), confirming that failure is this host's
pre-existing animation/compositor-settling timing sensitivity under QEMU,
unrelated to wallpaper decode or this change.

## Startup (pinned pointerless-default generation)

The Rust shell's very first paint, before any theme is ever explicitly
activated, reads `K230_THEME_DEFAULT_GENERATION` directly
(`appearance.rs`'s `selected_snapshot(...).or(default_snapshot)`), never
through `prepare()`. `nix/handheld-theme-default/default.nix` now builds a
native (`buildPackages`) copy of `k230-shell-rust` and runs
`--write-wallpaper-cache` on the pinned bundled generation's
`backgrounds/2-waves.webp` at build time, so this exact path -- the one the
startup log's `wallpaper-commit` line at ~3000 ms refers to -- gets the same
cache-hit fast path with no runtime change required:

```sh
nix build --no-link --print-out-paths --max-jobs 1 --cores 6 .#handheld-theme-default
# -> /nix/store/rf4b00manjj2rhvcgfa2rdzwmlx3hdpv-handheld-theme-default-28ceaae7
ls /nix/store/rf4b00manjj2rhvcgfa2rdzwmlx3hdpv-handheld-theme-default-28ceaae7/generations/0d16475245f13b3d7d3f036f/
# background.cache (2,799,121 bytes = 17-byte header + 568*1232*4) is present
cargo run --offline --release --example verify_bundled_default -- \
  /nix/store/rf4b00manjj2rhvcgfa2rdzwmlx3hdpv-handheld-theme-default-28ceaae7
# PASS: generation 0d16475245f13b3d7d3f036f, 4 source backgrounds, 568x1232 decoded wallpaper; recovery 20f2d477bb758593d831e427
```

## Memory

The cache does not raise peak RSS: a cache hit reads exactly the same
2,799,104-byte (568x1232x4) buffer the decoder would otherwise have produced,
skipping the intermediate full-size decode buffer and resize scratch
entirely (a cache miss is byte-for-byte the pre-existing code path, so no
regression there either). One `background.cache` file lives per prepared
generation on disk (bounded to the panel's fixed 2.8 MB), not per running
process.

## Board timing check the coordinator should run

None of the above is a board result. The narrow on-board check, reusing the
exact procedure and columns from `docs/evidence/omarchy-themes/commit-fix-board/README.md`:

```sh
# after installing a system built from this change (or a later master that
# includes it), on the board, as the shell user:
/nix/store/<...>-handheld-theme-command-.../bin/k230-theme activate --json <theme-id>
/nix/store/<...>-handheld-theme-command-.../bin/k230-theme activate --json --expected-generation <g> <theme-id>
journalctl -u shell-ui | grep -c appearance-.*-rejected   # expect 0, as before
```
Expected result if this change holds on hardware: the *first* activation of
a theme not yet prepared on that board is roughly unchanged (still one real
decode, now paid in `k230-theme`'s own process rather than inside
`shell-ui`); every later activation of an already-prepared theme -- which is
the common case the 4-5 s number in `commit-fix-board/README.md` was
measured against -- drops from several seconds to close to the small,
decode-independent floor this evidence's QEMU run shows (a few hundred
milliseconds of process/IPC overhead). `journalctl -u shell-ui` should show
no new rejection categories; `wallpaper-commit` timestamps in its startup
log should be much closer together than the ~3000 ms baseline.
