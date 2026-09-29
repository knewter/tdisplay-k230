## ADDED Requirements

### Requirement: The shell fills a whole non-panel output instead of letterboxing it

*Grounding: `nix/rust-shell-client/src/main.rs`'s `is_whole_output` (reads
`OutputState`, matches a configure's `(width, height)` against a known
output's own `logical_size`) and `lib.rs`'s `configure_preserves_aspect`,
both read for this change. `feat/hdmi-pillarbox` (commit `4c2eb57c`,
2026-09-29) recorded a board log of a real whole-output configure this
logic must handle: `pillarbox 1080x1920 -> 885x1920`, HDMI-A-1, Home and
wallpaper drawn (that log is this requirement's evidence that the shell
does receive such a configure on real hardware; it predates this change's
own fix and describes the pillarboxed behavior being replaced). Whether the
*reflowed* (non-pillarboxed) fill has itself been observed on the physical
board or under QEMU is <!-- UNVERIFIED --> as of this change: the evidence
committed with it (`docs/evidence/shell-responsive/`) is host-rendered
through the production paint path with no Wayland connection, per that
directory's own `README.md`.*

When a Wayland layer-shell `configure` gives a surface exactly the size of
a currently known output (an HDMI monitor at its own resolution, at any
aspect ratio, landscape or rotated portrait), the shell SHALL accept that
size and paint its wallpaper, Home grid/dock, and Drawer/Shade/Settings/
Power panel chrome to fill it completely, with no letterboxed or
pillarboxed band of unpainted or differently-colored space. A configure
that is not the size of any known output (in particular, a single-axis
shrink such as an on-screen keyboard's exclusive zone) SHALL continue to be
rejected exactly as before this requirement existed, leaving the surface at
its last accepted geometry.

This requirement governs whether the *surface itself* is allowed to take
the output's full size and whether what already reflows (the wallpaper
fill, Home's row count, panel chrome) is allowed to do so. It does not by
itself require every on-screen element to relayout for the new size: the
Home grid's column count, and Settings' row content, are recorded as
UNVERIFIED-for-reflow and named explicitly as open follow-up work in
`openspec/changes/the-shell-adapts-to-output-resolution/design.md`, not
claimed here.

#### Scenario: An HDMI monitor is configured at its own landscape resolution

- **WHEN** the compositor sends a layer-shell `configure` whose size
  matches a connected HDMI output's own logical size (e.g. 1920x1080)
- **THEN** the shell accepts that size for the surface, and the wallpaper,
  Home, and any open Drawer/Shade/Settings/Power panel fill it edge to edge
  with no pillarboxed column

#### Scenario: An on-screen keyboard's exclusive zone shrinks one axis

- **WHEN** a `configure` reduces only the surface's height (or only its
  width), to a size that does not match any known output's own logical size
- **THEN** the shell rejects that configure and keeps the surface at its
  last accepted geometry, exactly as it did before this requirement

#### Scenario: The Drawer reflows its column count with a wider output

- **WHEN** the Drawer is open on a surface wider than the 568px design width
- **THEN** its app grid uses more columns, proportional to the extra width,
  instead of the same 4 columns stretched into wider, sparser tiles
