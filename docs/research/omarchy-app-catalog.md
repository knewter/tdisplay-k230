# More drawer apps, checked against Omarchy's catalogue

Checked 2026-09-25 against
[`omacom/omarchy`](https://github.com/omacom/omarchy) at the pinned
`quattro`-branch ref `28ceaae70ebac3a0edcc21f2faa77a90dc6d404c` already vendored
under [`nix/omarchy-theme-tools`](../../nix/omarchy-theme-tools/SOURCE.md), plus
the current `quattro` HEAD package lists:
[`install/omarchy-base.packages`](https://github.com/omacom/omarchy/blob/quattro/install/omarchy-base.packages)
and
[`install/omarchy-other.packages`](https://github.com/omacom/omarchy/blob/quattro/install/omarchy-other.packages).
This does not import Omarchy's Hyprland/Quickshell session, package manager,
or app-discovery code; see
[`docs/research/omarchy-nixos-comparison.md`](omarchy-nixos-comparison.md) for
why. It only asks, category by category, which *leaf application* Omarchy
ships and whether that same program is sane on this board.

The drawer has no allowlist to edit. `nix/rust-shell-client/src/catalog.rs`
(coherent shell) and `nix/touch-launcher/catalog.c` (bar shell) both call
`GAppInfo`/`GDesktopAppInfo` discovery directly over `XDG_DATA_DIRS`; any
package that lands in `environment.systemPackages` with a `.desktop` file (own
or one added here with `pkgs.makeDesktopItem`) shows up automatically, sorted
by name. Icons resolve the same way, through
`nix/rust-shell-client/src/icon.rs`'s freedesktop icon-theme lookup
(`librsvg` for scalable SVGs, a raster decode for PNGs), against
`nix/handheld-theme-icons`'s bundled Yaru/hicolor tree plus each package's own
`share/icons`. No new launcher or icon-mapping code was needed for any app
below.

## The one constraint that decided the most

This board has **no GPU and no software GL fallback** — no Mesa, no LLVM
(`docs/display-environment-options.md`). Sway itself renders everything with
Pixman. Any candidate that touches `libGL`/EGL at runtime is out regardless of
how it builds, because there is no driver, real or software, to satisfy it.
Checking each candidate's `buildInputs` against nixpkgs (pinned rev
`20b1ddd1aa5ace70c9468305030aa4f9ef79671b`) surfaced one direct hit:

- **imv** (Omarchy's `install/omarchy-base.packages`, image viewer) links
  `libGL` unconditionally in
  [`pkgs/by-name/im/imv/package.nix`](https://github.com/NixOS/nixpkgs/blob/20b1ddd1aa5ace70c9468305030aa4f9ef79671b/pkgs/by-name/im/imv/package.nix) —
  imv's Wayland backend genuinely draws through EGL, not `wl_shm`. It also
  fails to cross-build here independent of that: its `libnsgif`/`libnsbmp`
  backends pull NetSurf's `libnsbmp`, whose upstream `Makefile.tools` invokes
  bare `cc` to guess the build platform, which does not exist in this
  cross environment (`cc: command not found`,
  `nix log /nix/store/dpp9lz1gin8vv3qm9jc17cbsgjgq8w28-libnsbmp-riscv64-unknown-linux-gnu-0.1.7.drv`,
  host build evidence from this change). **Substitute: `viewnior`**
  (`viewnior-gtk3` in nixpkgs), a plain GTK3/`gdk-pixbuf`/`exiv2`/`lcms`
  viewer with no GL anywhere in its dependency graph.
- **mupdf**'s GUI (what Omarchy would show if it used mupdf as a viewer) is
  built `enableGL = true` by default: a GLUT (`freeglut`+`libGLU`) *and* X11
  window, needing both a real GL context and Xwayland (disabled in this image
  to keep the GTK3/CUPS/Avahi tail out entirely when unused — see
  `nix/shell.nix`'s `swayBase` comment). Turning `enableGL`/`enableX11` off
  leaves only the `mutool` CLI, not a touch-usable viewer. **Not carried
  over as an app**; mupdf's *library* is still used, see below.
- The **NetSurf** browser (`netsurf-browser`) hits the exact same
  `libnsbmp`/`libnsutils`/`libhubbub`/`libcss`/`libdom` build failure as
  imv's backends — this is a real gap in nixpkgs' cross support for the
  whole NetSurf library family, not something specific to a viewer or a
  browser. **Dropped for that reason**, independent of it otherwise being
  the best-fit engine for a browser here (own small C engine, GTK frontend,
  no WebKit, no GL).

Everything kept below renders through GTK3 (Cairo → `wl_shm`, the same path
Sway already uses) or a terminal (`foot`, already in the image). None of it
needs `libGL`, EGL, or Xwayland.

## Games

Omarchy ships no lightweight game at all in `omarchy-base.packages`; its only
game-shaped tooling is `bin/omarchy-games-retro-*`, which installs RetroArch
libretro cores (dry-run: `nix build --dry-run .#nixosConfigurations.k230.pkgs.brogue-ce`
alone reported 613 paths / 1.7 GiB download / 3.3 GiB unpacked for one
roguelike with an SDL2/GL dependency chain) — an emulation stack aimed at a
GPU-backed desktop, not a 1.6 GHz in-order core with no GPU. That is the
"dumb here" case the task asked to watch for, so this category has no direct
Omarchy pick to keep; the substitutes are independently-chosen, genuinely
light native games:

| App | Package | Why |
| --- | --- | --- |
| Simon Tatham's Puzzles (4 curated) | `sgt-puzzles` | GTK3, Cairo drawing; no GL. |
| NetHack | `nethack` | Classic curses roguelike; tiny, terminal-only, builds clean. |
| 2048 | `_2048-in-terminal` | Trivial ncurses game; effectively free closure cost, once patched (below). |

`sgt-puzzles` needed two changes, both a real host build surfaced rather
than something guessed from source reading. Upstream's `postInstall`
installs one binary/icon/`.desktop` per puzzle (~40 of them) in a single
loop, but the per-puzzle icon PNGs are not shipped pre-rendered: the source
tarball ships only `icons/*.sav` fixtures plus `icon.pl`/`cicon.pl`/`crop.sh`,
meaning the icons are meant to be screenshotted from the just-built game
binaries at build time -- impossible when cross-compiling, since the
riscv64 binaries cannot run on the x86_64 builder. `install -Dm644
icons/$i-96d24.png ...` fails for every puzzle checked (`net`, then
`bridges`), aborting the whole derivation
(`nix log` on the `sgt-puzzles-riscv64-*.drv` from this change). That is a
nixpkgs cross-compilation gap in the package's own build, not something to
patch inside this change's scope. A ~40-entry dump into a small touch
drawer was also more than this launcher needs even if the icons had built,
so `nix/shell.nix` overrides `postInstall` to install only four
touch-friendly picks that need a single tap and no secondary-button/
right-click semantics -- rotate (Net), remove same-colour groups (Same
Game), shift a row/column (Sixteen), slide a tile (Fifteen) -- each using
the shared bundled `applications-games` icon instead of a per-puzzle
screenshot.

`_2048-in-terminal`'s Makefile invokes bare `pkg-config` instead of
`$PKG_CONFIG`: the cross environment does not put an unprefixed
`pkg-config` on `PATH` (only the target-prefixed binary), so the build
fails with undefined `ncurses` symbols at the link step until
`nix/shell.nix` patches the Makefile with `substituteInPlace ...
--replace-fail 'pkg-config' "$PKG_CONFIG"`. `tty-clock` (considered for
the clock/timer utility, not a game) hits the identical bug
(`pkg-config: command not found` then undefined `ncurses` symbols, `nix-store
-l` on
`/nix/store/0624znjs9ay92s398nzm10nc16bbm4q8-tty-clock-riscv64-unknown-linux-gnu-2.3-unstable-2021-04-07.drv`)
but was dropped instead of patched: a `date`-in-a-loop shell script
replaces it for free (see Utilities), and one Makefile fix was enough
scope for this change.

## Viewers

| Category | Omarchy | Ours | Why |
| --- | --- | --- | --- |
| Image | `imv` | `viewnior` | imv needs `libGL` and fails to cross-build here (above); viewnior is plain GTK3/Cairo. |
| PDF/ebook | `evince` | `zathura` | `evince` is GNOME/GTK4-ish and pulls the full `yelp`/help-docs tail for a feature this drawer will never use (in-app help browser). `zathura` (`girara`+`gtk3`) is the same job with a much smaller, already-common Linux minimal-desktop pick. Its default plugin set links mupdf's *own* GL-enabled GUI binary into the same closure just to reach mupdf's parser (`useMupdf = true` pulls `freeglut`/`libGLU` in as dead weight -- it is never launched, `zathura` only calls `libmupdf`). A real build was attempted to drop that: `zathuraPkgs.override { useMupdf = false; }` selects the poppler backend instead, but its `zathura_pdf_poppler` plugin fails to cross-build in this pinned nixpkgs on its own -- meson cannot resolve `zathura` via pkg-config for the cross target (`Run-time dependency zathura found: NO (tried pkgconfig)`, `nix log` on `/nix/store/aarbyyh4bd8ximj3j1pmx9311y8i8xma-zathura-pdf-poppler-riscv64-unknown-linux-gnu-2026.05.10.drv` from this change). That is a nixpkgs cross-meson gap in the plugin's own build, unrelated to this board's hardware and out of this change's scope to fix. The default `zathura` (mupdf-backed) is kept instead: it is already a valid, present store path at this pin, so the unused GL-linked `mupdf-gl` binary rides along as closure weight rather than blocking the viewer. Neither backend reads EPUB; there is no small, non-GL, actively-packaged EPUB reader in nixpkgs at the moment, so "ebook" here means PDF/PS/DjVu/CBZ, not EPUB. |

## Utilities

| Category | Omarchy | Ours | Why |
| --- | --- | --- | --- |
| Calculator | *(none — only its own `omacalc` CLI helper, not packaged upstream as a normal calculator)* | `galculator` | Omarchy has no GUI calculator to match. `qalculate-gtk` was also checked (also GL-free, GTK3) but pulls `libqalculate` (GMP/MPFR/libxml2/ICU/curl for currency rates) for unit-conversion features this drawer does not need; `galculator` is a plain GTK3 four-function/scientific calculator with a much smaller dependency graph. |
| System monitor | `btop` | `btop` **and** the existing `htop` (Monitor) | Straight keep: `btop` is in `omarchy-base.packages`, is a small self-contained C++ binary (no GL, no GPU-monitoring backend enabled here), and ships its own desktop entry. Kept alongside the existing Monitor/htop entry rather than replacing it — the two answer different questions and neither costs much once the other is present. |
| Weather | *(none in the package list)* | `curl wttr.in` in a foot card | Matches the task's suggested shape exactly: `curl` is the only package this pulls in (self-contained in the script's own `PATH`, not a general-purpose addition to `systemPackages`), and a `foot` card fetches a compact one-line report with a clear "no network" message if it can't reach the network. |
| Clock / timer | *(swaybar-style bar clock only, not a standalone app in Omarchy either)* | `date`-loop and countdown scripts in `foot` cards | `tty-clock` (the obvious upstream pick) fails to cross-build here (see Games); a `date '+...' ` loop and a `date +%s`-based countdown loop need no new package and no GL. |

## Browser

Omarchy's browser story is entirely Chromium-family: `omarchy-base.packages`
installs `chromium`, and `bin/omarchy-install-browser` offers Chromium-based
alternatives (Brave, Vivaldi, etc.) plus `bin/omarchy-webapp-*` wrapping sites
as Chromium app-mode windows. **Chromium itself is explicitly not viable
here**: it is a multi-process, JIT- and GPU-compositing-oriented browser built
around Skia/ANGLE GPU paths, with a cross-build measured in many hours even
before considering that this board has no GPU driver for it to composite
with, and a resident-memory footprint that alone can exceed this board's 1 GiB
before a single tab loads. It was not attempted.

Two non-Chromium alternatives were evaluated in place of it, both suggested
by the task:

- **NetSurf** (own small HTML/CSS engine, GTK frontend, explicitly designed
  to run without a GPU) is architecturally the best fit for this hardware,
  but its `libnsbmp`/`libnsutils`/`libhubbub`/`libcss`/`libdom`/`libsvgtiny`
  libraries all fail to cross-build in the pinned nixpkgs for the reason
  above (NetSurf's own buildsystem calls bare `cc`). This is a nixpkgs
  packaging gap in the whole NetSurf family, not something to patch inside
  this change's scope. **Not included.**
- **surf** (suckless, WebKitGTK) got a real build attempt:
  `nix build .#nixosConfigurations.k230.pkgs.surf`, host build, this change.
  WebKitGTK can be told to composite without a GL context
  (`WEBKIT_DISABLE_COMPOSITING_MODE=1`) at runtime, but its own build pulls a
  GStreamer/media stack of comparable size to WebKitGTK itself (`libsoup`,
  `imlib2`, `opencore-amr`, `libid3tag`, `wildmidi`, `enchant`, `nuspell`,
  `taglib`, `libnice`, dozens more), and the pinned nixpkgs still needs to
  cross-build essentially all of it from source. After roughly 40 minutes of
  continuous building (no failures, no cache hits -- every dependency was a
  fresh cross-compile) it was still deep in that dependency graph, nowhere
  near WebKitGTK itself, and was stopped there rather than left running
  unbounded. Whether it is worth shipping is a build-time and closure-size
  question, not an architectural one, but this change does not answer it:
  **surf is not included**, and because the build never finished there is
  nothing to isolate onto its own droppable commit either.

`luakit` was ruled out without a build attempt: `nix build --dry-run` reports
its nixpkgs expression asserts `allowUnsupportedSystem` for `riscv64-linux`
(LuaJIT has no working RISC-V64 JIT backend), so it cannot be built for this
target at all. `vimb` is the same WebKitGTK dependency chain as `surf`; there
is no reason to build both.

## Closure size

`nix path-info -S` on `.#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel`,
before and after this change (host build, both fully realized):

| | Store path | Closure size |
| --- | --- | --- |
| Before | `/nix/store/yb815pr058186vb5nh65slp5ky9bj9gf-...` | 1,567,328,816 bytes (≈1,494.7 MiB) |
| After | `/nix/store/2k9ri1j5fma84236mdvjp832r2yi6imv-...` | 1,894,179,232 bytes (≈1,806.4 MiB) |
| **Delta** | | **326,850,416 bytes (≈311.8 MiB)** |

**This is over the ~150 MiB guideline in this task**, so it is flagged
explicitly rather than rounded down. It was worse first: an initial build
measured a 745.5 MiB delta, more than half of which (388 MiB) turned out to
be a single accidental closure leak, not real weight. `nix-store -q
--referrers` on the riscv64 `gcc` derivation named `nethack`'s own game
binary and its lock-recovery helper as referrers. Nix's default fixup phase
only strips ELF binaries under `bin/sbin/lib*/libexec`; nethack installs
both under `games/lib/nethackdir/`, which that list misses, so they kept
their unstripped `.comment`/debug sections naming the full compiler
closure. `nix/shell.nix`'s `nethackFixed` applies `remove-references-to`
(the identical fix nixpkgs' own `btop` package already applies to itself
for the same class of leak) to strip it, which is what brought the delta
down from 745.5 MiB to the 311.8 MiB above -- a real, reproducible measurement
error caught by actually diffing closures rather than reading source, not a
rounding difference.

The remaining 311.8 MiB is real weight, by size (`nix path-info -s` on the
paths new to the closure; see the commit for the full list):

| Size | Path | Why it's here |
| --- | --- | --- |
| 53.6 MiB | `mupdf` | zathura's default backend links mupdf's library; its GL-enabled `mupdf-gl` GUI binary rides along unused in the same output (see Viewers). |
| 50.6 + 6.4 MiB | `ghostscript-with-X` (+ fonts) | zathura's bundled PostScript plugin. |
| 43.4 MiB | `gtk+3` | The one-time toolkit tax this image had never paid before (`nix/shell.nix`'s `swayBase` comment: Xwayland was disabled specifically to avoid "GTK 3/CUPS/Avahi" until something needed it). Every GTK3 app added here (`sgt-puzzles`, `viewnior`, `galculator`, `zathura`/`girara`) shares this one payment. |
| 35.0 MiB | a second `glibc` build | Not yet root-caused; some new dependency triggers a distinct glibc variant from the one already in the baseline closure. Flagged here rather than silently absorbed. |
| 23.7 MiB | `iso-codes` | GTK3/locale data, part of the same one-time tax. |
| 18.8 MiB | `nethack` (fixed) | The game itself, after the leak above was removed. |
| 16.6 MiB | `sgt-puzzles` (curated) | Four puzzle binaries plus their help pages. |
| 9.4 + 4.9 MiB | `cups` (+ lib) | GTK3's print-dialog dependency, part of the same one-time tax; nothing in this image enables printing. |
| ~12 MiB | `x265`, `libaom`, `libvmaf`, `libyuv`, `libheif` | viewnior's optional AVIF/HEIF image codec support (`gdk-pixbuf` loaders). |
| 6.5 MiB | `gsettings-desktop-schemas` | GTK3 tax. |
| 4.6 MiB | `exiv2` | viewnior's image-metadata reader. |
| 2.4 MiB | `at-spi2-core` | GTK3 accessibility tax. |

In short: about 100 MiB of this is the GTK3/CUPS/Avahi-adjacent toolkit tax
this image had structurally avoided until now (paid once, shared by four
apps), about 60 MiB is zathura's PostScript/mupdf plugin weight (including
one genuinely unused GL-linked binary), and the rest is the games/viewer
binaries and their own small codec libraries. None of it is GPU/EGL-related;
see the constraint section above.

## Not attempted, or attempted only as a dry run

- `brogue-ce`: 1.7 GiB download / 3.3 GiB unpacked per the dry-run above, for
  one roguelike. Far outside this task's "narrow" build budget for a
  substitute nobody asked to keep.
- `qalculate-gtk`: a real build was started (GL-free, GTK3 like
  `galculator`) and it pulls `texlive-bin`/`gnuplot` transitively through
  `libqalculate`'s optional plotting/currency features — confirms it is the
  heavier of the two calculators regardless of whether that build finishes;
  `galculator` was chosen instead and does not carry that tail.
- `epiphany`: only `nix build --dry-run` (no build attempted). It is
  WebKitGTK-based like `surf`/`vimb`, plus the GNOME shell integration
  (`libadwaita`, `gnome-desktop`, etc.) on top, so it is strictly heavier than
  `surf` for the same engine risk; not a genuinely separate candidate.
