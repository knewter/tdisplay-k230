# Cross-building Ladybird for this board: not attempted past evaluation

Checked 2026-09-25 against the flake's pinned nixpkgs rev
`20b1ddd1aa5ace70c9468305030aa4f9ef79671b` (the same pin
`docs/research/omarchy-app-catalog.md`'s browser section used). This follows
up on that section's Chromium/NetSurf/surf survey with the specific browser
the task named: `ladybird` (nixpkgs `pkgs/by-name/la/ladybird/package.nix`,
version `0-unstable-2026-06-05`, upstream rev
`02b205361dd239e134f434e484b609d1fa5f1938`).

**No build was started.** Nix evaluation itself fails before a single
derivation would be realized, for two independent, compounding reasons. Given
this board's own prior measurement of what a real GL stack costs here
(`docs/display-environment-options.md`), this is architecture-level, not a
one-line packaging bug, so the task's stop condition ("a Qt6 cross
configuration that nixpkgs doesn't support") applies and no build time was
spent past evaluation.

## Machine check before touching anything

```
nproc            -> 32
free -h          -> 125Gi total, ~28Gi free, 87Gi "available" (page cache heavy)
uptime           -> load average 8.4, 14.2, 22.6 (other agents' worktrees active)
```
Per AGENTS.md's shared-machine concern, no build was run at more than the
task's suggested `--max-jobs 1 --cores 6`, and in the end no build ran at all
(see below), so the machine was not loaded by this task beyond a handful of
`nix-build --dry-run` evaluations and small `curl` fetches of nixpkgs source
files, each a few seconds.

## Command run and what it found

The flake does not expose `pkgsCross.riscv64.ladybird` as a named output (it
is not part of `nix/shell.nix`'s app set), so this was checked directly
against the pinned nixpkgs revision, cross to `riscv64-unknown-linux-gnu`,
matching how `flake.nix` builds `pkgsCross`:

```
$ nix-build --dry-run -A ladybird ladybird-cross.nix
```
with `ladybird-cross.nix`:
```nix
let
  nixpkgsSrc = builtins.fetchTarball {
    url = "https://github.com/NixOS/nixpkgs/archive/20b1ddd1aa5ace70c9468305030aa4f9ef79671b.tar.gz";
  };
  pkgs = import nixpkgsSrc {
    system = "x86_64-linux";
    crossSystem = { config = "riscv64-unknown-linux-gnu"; };
    config.allowUnsupportedSystem = true;
    config.permittedInsecurePackages = [ "ladybird-0-unstable-2026-06-05" ];
  };
in { ladybird = pkgs.ladybird; }
```

Three separate gates had to be cleared or hit, in order:

### 1. `meta.platforms` does not list riscv64-linux at all

```
error: Refusing to evaluate package 'ladybird-0-unstable-2026-06-05' in
.../pkgs/by-name/la/ladybird/package.nix:208 because it is not available on
the requested hostPlatform:
  hostPlatform.system = "riscv64-linux"
  package.meta.platforms = [ "x86_64-linux" "aarch64-linux" "aarch64-darwin" ]
```
`pkgs/by-name/la/ladybird/package.nix` line 216-220 states this explicitly:
nixpkgs has never claimed riscv64-linux support for Ladybird. Cleared with
`config.allowUnsupportedSystem = true` to see what breaks next, per the
task's instruction to check for real blockers rather than stop at the first
guard rail.

### 2. Marked insecure (unrelated to this board, cleared trivially)

```
error: ... because it is marked as insecure
Known issues:
 - CVE-2026-58592
```
Cleared with `config.permittedInsecurePackages`. Not a cross/porting issue,
noted only so the next error is the real one.

### 3. Skia's GN `target_cpu` table has no riscv64 entry — hard evaluation error

```
error: attribute 'riscv64' missing
at .../pkgs/by-name/sk/skia/package.nix:92:9:
    91|       cpu =
    92|         {
      |         ^
    93|           "x86_64" = "x64";
```
The full table in `pkgs/by-name/sk/skia/package.nix` (lines 90-97):
```nix
cpu =
  {
    "x86_64" = "x64";
    "i686" = "x86";
    "arm" = "arm";
    "aarch64" = "arm64";
    "loongarch64" = "loong64";
  }
  .${stdenv.hostPlatform.parsed.cpu.name};
```
There is no `"riscv64" = ...` entry, so `.${...}` throws at evaluation time —
this is not a build failure, it is Nix refusing to even construct the
derivation. Ladybird pulls this same `skia` (via `buildInputs`, with a small
`overrideAttrs` patch for a vcpkg SkPath compat fix) directly.

Google's Skia build is driven by GN, not CMake/Meson; adding riscv64 here
would need at minimum a GN `target_cpu` string, a matching GN toolchain
definition (`gn/BUILD.gn` toolchain stanza with the right tool invocations
for the target triple), and for Skia's own architecture-dispatched code
(`src/opts/SkOpts_*`) to have — or gain — a working generic/portable
codepath when no riscv64 SIMD backend exists. None of that is present in
this nixpkgs packaging today; it is a real upstream/nixpkgs porting
project, not a patch this change's scope covers.

### The GL problem, independent of #3

Even setting Skia's `target_cpu` gap aside, both `skia` and `ladybird`
hard-require linking against desktop OpenGL:

- `pkgs/by-name/sk/skia/package.nix` lists `libGL` directly in
  `buildInputs`, unconditionally (not gated behind any flag).
- `pkgs/by-name/la/ladybird/package.nix` sets
  `env.NIX_LDFLAGS = "-lGL -lfontconfig";` unconditionally, citing an
  upstream Ladybird issue (`OESVertexArrayObject.cpp.o: undefined reference
  to symbol 'glIsVertexArrayOES'`) as the reason.

This board's package set has no `libGL` for riscv64 by design:
`docs/display-environment-options.md` (`## 1. The GPU situation, stated
precisely`) already measured what it costs to add one. Mesa's own riscv64
support forces the LLVM-JIT `llvmpipe` path (`llvm_with_orcjit`, LLVM >= 15),
and that document records `nix build --dry-run` for
`pkgsCross.riscv64.mesa` reporting **4 derivations / 575.2 MiB to build**,
with the resulting closure cost put at **~2.4 GiB** (LLVM 21 plus Mesa) once
counted end to end — bigger than this image's entire current closure
(1.8 GiB per `docs/research/omarchy-app-catalog.md`'s closure table) just to
produce a `libGL.so` that nothing would ever call at runtime, since Sway
here draws only through Pixman/`wl_shm`. That document already recommended
against paying this cost for a compositor (Hyprland); paying it a second
time here, for a library neither Skia nor Ladybird would actually use for
GPU rendering (Skia's raster/CPU backend and Ladybird's Qt widget path don't
need a GPU context to run), would be strictly worse.

## Why this is a stop, not a patch

Per the task's own stop condition — a Qt6/graphics cross configuration
nixpkgs doesn't support, or a JIT/arch-specific-code gap with no riscv64
backend — both apply here and neither is narrow:

1. Skia's nixpkgs packaging has no riscv64 GN target at all (a porting
   project: GN toolchain files plus Skia's own arch-dispatched opts code,
   upstream-scale work, not confirmed to have a portable fallback in this
   Skia version).
2. Skia and Ladybird both hard-link against real `libGL`, which this board
   deliberately does not carry (previously measured at ~2.4 GiB to add, for
   a compositor that was rejected specifically because of that cost).

Neither of these is the kind of pkg-config/bare-`cc` cross bug the sibling
branch (`_2048-in-terminal`, `sgt-puzzles`) patched narrowly. No build was
started; there is no log to attach beyond the two `nix-build --dry-run`
evaluation errors quoted above, and no closure size to report.

For completeness: Qt6 itself is not the blocker. A prior probe in this repo
(`docs/evidence/qtquick/minimal-probe-prebuild.md`) got Qt Quick's cross
derivation graph to evaluate and dry-run cleanly against this same nixpkgs
pin (40 target derivations, Qt 6.11.2, QML JIT predicted off on riscv64 by
`configure.cmake`'s own i386/x86_64/ARM/ARM64 gate) before being interrupted
for priority reasons, not failure. Ladybird's `qtbase`/`qtmultimedia`/
`qtwayland` dependencies are plausibly buildable on their own; Skia and the
GL link are what stop the whole graph from evaluating at all.

## Honest capacity estimate (labelled: this is an estimate — nothing here ran)

Since nothing built, none of the following is measured; it is inferred from
Ladybird's known process architecture and this board's numbers, and should be
weighted accordingly.

- **RAM.** Ladybird runs as several cooperating processes even for one tab:
  the Qt chrome/UI process, `WebContent` (parser, DOM, layout, JS engine),
  `RequestServer` (networking), and `ImageDecoder`. Each is a separate Linux
  process with its own ICU data mapping, Qt6/Skia code pages, and heap. Even
  before any page content, that process-per-concern design has historically
  cost on the order of 100-200+ MiB resident just to bring the four
  processes up on desktop-class systems; a single moderately complex modern
  page (its DOM/style tree, JS heap, decoded images, Skia raster surfaces)
  easily adds more on top. Against this board's ~675 MiB free at idle,
  **a single non-trivial page load is a plausible OOM risk**, not a
  comfortable fit — this is the same conclusion the existing catalog doc
  already reached for Chromium, at a smaller multiple.
- **CPU.** 568x1232 is a small raster surface (~700K px), so Skia's CPU-only
  (raster) backend doing the final composite is not by itself unreasonable
  on a 1.6 GHz in-order core — the same reasoning the catalog doc used for
  Sway's own Pixman compositing. The bottleneck is more likely upstream of
  raster: Ladybird's `LibJS`/`LibWeb` (HTML/CSS parsing, layout, and a
  bytecode-interpreted JS engine with no riscv64 JIT — none of Ladybird's
  architectures have a production JIT as of this source pin, so this is not
  a riscv64-specific penalty, but a single in-order core still pays the full
  interpreted cost) on any real-world site with meaningful script. Expect
  page loads and interaction on a typical modern page to be considerably
  slower than on the x86_64/aarch64 systems Ladybird is actually developed
  and tested against — plausibly many seconds to tens of seconds for a
  script-heavy page, by analogy with the existing WebKitGTK/`surf` entry's
  conclusion that this class of engine is architecturally mismatched with a
  single in-order low-clock core, independent of whether it can be built at
  all.

## What remains

Nothing to hand to the coordinator for board time: no package was added to
`nix/shell.nix`, no image was rebuilt, and no store path exists to deploy or
verify. This is a source/evaluation-only finding. If nixpkgs later gains a
riscv64 Skia GN target and this board later carries a `libGL` (accepting the
~2.4 GiB Mesa/LLVM cost this repo has already priced and rejected once),
re-checking this would be worthwhile; neither condition holds today.
