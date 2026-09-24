# Icon resolution checkpoint for the existing launcher

This is host/source evidence for part of task 1.4 of
`the-handheld-presents-a-coherent-shell`, based on `a7c7a2af`. It changes the
installed development Apps surface's rows; it does not claim that the proposed
bar-free drawer, live-card headers, or notification center are installed.
Task 1.4 remains unchecked because the latter two consumers do not exist in
this path yet. No board, Nix cross-build, image integration, or real-finger
verification was run for the initial checkpoint. A subsequent narrow
cross-build is recorded below; physical verification remains open.

The launcher now reads each installed desktop entry's `GAppInfo`/`GIcon`,
including absolute `GFileIcon` paths and themed names. The resolver searches
`K230_ICON_THEME` when set, follows `index.theme` inheritance to a bounded
depth, then tries `hicolor` and XDG pixmaps. Its fixed sizes are 48 px for
drawer rows, 32 px for eligible cards, and 24 px for trusted notifications.
The existing app name stays text beside a same-sized neutral fallback. The
current built-in Terminal/New terminal and Monitor rows request the installed
Foot and htop themed icons. The image's Video desktop entry now declares
`Icon=mpv`; Editor declares `Icon=accessories-text-editor` and falls back when
that theme glyph is not installed. `nix/shell.nix` puts the actual Foot, htop,
and Video-player package `share` trees on the launcher's `XDG_DATA_DIRS` path
before profile paths, so their Nix store icons can be resolved by name.
The theme name is configurable; this does not assume that a proposed theme
clone has been installed or selected.

PNG decoding uses Cairo, and SVG decoding uses **librsvg** rather than a
homemade SVG parser or an implicit gdk-pixbuf loader cache. The launcher
derivation declares and links librsvg. Files over 512 KiB, unreadable files,
unknown icon types, and unsafe themed path components take the named fallback.
The single-threaded cache holds at most 12 fixed-size Cairo image surfaces
(at most about 108 KiB of decoded pixel data at 48×48, plus small metadata),
with LRU eviction. A changed file stamp or changed XDG/theme environment
replaces cached entries; `k230_icon_cache_invalidate()` is available for a
future app-catalog/theme refresh. A newly created file for a previously
missing name needs that explicit invalidation in the same process. Decoding
is lazy; first appearance cost on a new page is not yet measured on the board.

`K230_ICON_PRIVATE_CARD` and `K230_ICON_PRIVATE_NOTIFICATION` return a neutral
glyph **before** inspecting the supplied `GIcon`. Host tests verify no
identity-bearing cache entry or decode is created. This is an API contract for
future card/notification clients, not a claim that their production privacy
state has been wired to it. The private card's title must separately be
redacted by the owning compositor scene before display.

## Host verification

Run from the repository root:

```sh
python3 tests/test_shell_icons.py --case theme --case missing \
  --case cache-bound --case notification-icon --case private-no-identity
python3 tests/test_shell_icons.py --case absolute --case svg
python3 tests/test_desktop_catalog.py
python3 tests/test_launcher_navigation.py
nix-instantiate --parse nix/shell.nix >/dev/null
nix-instantiate --parse nix/touch-launcher/default.nix >/dev/null
```

All seven icon fixtures passed on the host. The theme case exercised custom
theme inheritance and, where present, the actual Foot, htop and mpv SVGs from
the image's Nix packages. The absolute-path and SVG cases passed. The cache
case verified reuse, the 12-entry ceiling, eviction and explicit invalidation.
The private case compared rendered pixels with and without an identifying
icon and observed zero decodes/cache entries. The isolated 64×64 rendered
theme, SVG, fallback and private samples were visually inspected; they show
distinct artwork, a legible generic person glyph and a neutral lock glyph.
The three desktop-catalog tests and three launcher-navigation tests pass.
The production launcher compiled against host-generated Wayland protocol
bindings and its `--layout` command returned normally. Nix parsing passed;
that is syntax only, not a cross-build.

## Narrow cross-build after integration

On 2026-09-23, from integrated source `fd8fcf326f3b7c42d5e07715999426695cad5a24`:

```sh
nix build .#touch-launcher --max-jobs 1 --cores 4 --no-link --print-out-paths
```

PASS: `/nix/store/xarb3m3r8drh69wz91il23l1xh6n9y0k-k230-touch-launcher`.
The wrapper references target binary package
`/nix/store/bir1a5d1fyx58z3isjg1pk0069p8w28h-k230-touch-launcher-riscv64-unknown-linux-gnu-0.1`
and the explicit Foot/htop/mpv icon roots. Only the two launcher derivations
needed building. The root coordinator reran seven icon and three launcher
navigation host tests successfully; CI now installs `librsvg2-dev` and runs
the icon suite. No launcher deployment, full-image build, or board action was
performed for this result.

Remaining gate: inspect installed rows and cache cost on the physical
568×1232 screen. The final task 1.4 gate additionally needs actual live-card
and trusted-notification consumers, private title redaction, and its named
five-case test command to pass against those consumers. No checkbox was
changed for this partial implementation.
