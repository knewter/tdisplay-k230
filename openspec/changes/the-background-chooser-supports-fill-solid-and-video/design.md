## Context

`background_decode.rs` already has a `FitMode` enum with `Crop`, `Fit` and
`Center` variants and a working `place()` function for each, built while
implementing bundled-theme background support. It was never wired to a
user-facing choice: `theme_thumbnails.rs`, `main.rs` and `theme_ui.rs` each
call `render`/`render_uncached` with `FitMode::Crop` hardcoded. Video
backgrounds were scoped in the original `the-shell-loads-omarchy-themes`
proposal (task 4.3) but never started — the module's own doc comment
states plainly that it does not decode video.

## Goals / Non-Goals

- Goal: a person can choose, per background, how it is placed (`Crop`,
  `Fit`, `Center`, and two new modes: `Fill`, `Solid`), and that choice
  persists the same way the background choice itself already does.
- Goal: a person can add their own background image, bounded and staged
  the same way a theme's own assets already are.
- Goal: bounded, muted, reduced-motion-aware video backgrounds, gated on
  passing the existing card CPU/frame budgets before being enabled by
  default.
- Non-goal: a crop/pan UI. Fit modes are a fixed, named enum.
- Non-goal: audio. Backgrounds are muted video only, matching "wallpaper,"
  not "media player."
- Non-goal: changing the chooser's own tap-to-apply interaction model.

## Decisions

- `Fill` stretches the source to exactly cover the canvas without
  preserving aspect ratio (distinct from `Crop`'s aspect-preserving cover
  and `Fit`'s aspect-preserving letterbox). `Solid` ignores the source
  entirely and paints a single resolved color (from the active theme's own
  palette, or an explicit choice) — useful for a person who wants a
  background role satisfied with no image at all, and as the documented
  fallback if a chosen image or video becomes unavailable.
- Fit-mode and overlay choices persist through `theme_preferences.py`'s
  existing bounded, hash-keyed, per-source store (`MAX_CHOICES = 256`) —
  this proposal only widens what one entry can record, not the storage
  model.
- Video decode is a new, separate, always-optional code path in
  `background_decode.rs`, built as its own isolated flake output
  (`handheld-wallpaper`) precisely so its cost (decoder linkage, memory,
  CPU) can be measured and gated independently of the rest of the theme
  package, per this project's own "Performance remains a physical gate"
  convention (`the-shell-loads-omarchy-themes` task 4.3's own wording).
  Decode failures (recognized suffix, undecodable content; corrupt
  container; codec this project does not carry) are named diagnostics in
  the compatibility report, not crashes, and fall back to a still frame or
  `Crop` of the theme's own paired still, per the parent task's own
  "still fallback" requirement.
- Visibility pause and reduced-motion both key off signals this codebase
  already threads through the render loop (`reduced_motion_enabled` in
  `main.rs`; existing surface-visibility bookkeeping for the wallpaper
  layer) rather than inventing new ones.
- Video stays disabled by default until the reserved-board workload
  (already partially scaffolded: `docs/evidence/omarchy-themes/background-workload-host.md`
  and `tools/handheld-theme-trial.py --workload backgrounds`'s existing
  video arm, which today reports "the installed Rust wallpaper client...
  still rejects video") passes the same card CPU/frame budgets the rest of
  this project holds itself to.

## Risks / Trade-offs

- Video decode on a single in-order K230 core competing with the compositor
  is the same class of cost this project has repeatedly found expensive
  for far cheaper operations (see the sibling change's task groups 7-10 on
  optimistic-apply latency). This is why video ships gated off by default
  behind its own measured workload, not assumed safe because the decode
  path compiles.
- Widening what a "background choice" can be (image, overlay, fit mode,
  video) touches the same generation-identity hashing
  (`tools/theme_sources.py`) that task 1.4 of the parent change already hit
  a real bug in once (a build-time sibling file inside a theme's own
  directory silently changing every generation identity). Any new staged
  path added here must live outside a theme's own content-hashed tree, the
  same lesson that bug already taught.

## Migration Plan

None — additive. Existing generations with no recorded fit-mode choice
default to today's behavior (`Crop`), so nothing already committed changes
appearance.

## Resolved Questions

- **Does "Solid" need its own color picker?** No (decided 2026-10-16, task
  1.3). `Solid` always paints the active generation's resolved `background`
  palette role -- the same role `RendererCache::draw_wallpaper` already uses
  as a theme's base colour -- so a dark theme gets its dark base and a light
  theme its light base with nothing for a person to configure, it needs no
  new persisted value (the generation's `report.json` already carries the
  palette), and it works for a theme that ships no background asset at all.
  `background_decode::FitMode::Solid` takes a resolved RGBA colour; the shell
  resolves it in `appearance::generation_wallpaper_fit`. Rejected: an
  explicit per-person colour (a picker plus a new stored, validated colour
  for a case the palette already answers; it can be added later as another
  `FitMode` argument without changing the stored fit name) and the `accent`
  role (reads as a highlight, not a backdrop; poor contrast under icons).

## Implementation notes (host work, 2026-10-16)

- **`Fill` is a stretch, not a cover-crop.** The proposal and this document
  define `Fill` as aspect-distorting and `Crop` as the aspect-preserving
  cover; the spec delta's first draft described `fill` as cover-and-crop,
  which is `crop`. The delta now says what `Fill` does here (stretch, no
  crop, no letterbox).
- **The fit mode is remembered per theme source**, beside the remembered
  background, in `background-selections.json` as an optional `fits` table
  keyed the same way (`crop`, the default, is never stored; version stays 1
  and files written before this change read as `crop`). It is not keyed per
  individual background image: the existing store has one entry per source
  and the chooser applies one placement to the active background.
- **The mode is part of the generation identity** (a generation stages the
  decode inputs and its `report.json`), added to the identity hash only when
  it is not `crop`, so every existing generation keeps its identity. The
  wallpaper `background.cache` is the `Crop` decode, so it is only built for
  `crop`; another mode is a cache miss and a full decode. The shell reads
  `fit_mode` from the generation's `report.json` (absent means `crop`).
- **Chooser control:** tapping the "Backgrounds" heading cycles the active
  background's fit (crop, fit, center, fill, solid) and the heading names the
  current mode. It sends `ThemeRequest::Fit`, a preview-then-activate pair
  like a background change, through the existing helper protocol
  (`--fit`/`"fit"`).
- **User overlays** (task 2.1) live in a flat directory outside every theme
  (`~/.config/omarchy/backgrounds`, `--overlays` to override), are staged
  into the generation as `backgrounds/user-<name>` so the existing selection,
  preference and Rust loader paths accept them unchanged, and are bounded:
  regular files only (no symlinks), `STILLS | VIDEOS` suffixes, a safe file
  name, each at most `MAX_ASSET`, at most 32 files and `MAX_TOTAL / 2` bytes
  together. A bad overlay is a line in the report's `unknown` list, never a
  failed activation; a name that collides with a theme's own asset loses to
  the theme. They stay out of the theme's content-hashed tree; the staged set
  enters the generation identity as a stat-only fingerprint (name, size,
  mtime), added only when overlays exist.
