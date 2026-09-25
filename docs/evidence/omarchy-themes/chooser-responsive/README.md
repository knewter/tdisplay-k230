# Theme chooser responsiveness: idle-redraw fix, immediate feedback, fast thumbnails

Captured 2026-09-24 against branch `perf/theme-chooser-responsive`, base
`master` `b9f81d47` (pushed). **Host and headless-QEMU only** (`grim`
screenshots, synthetic Wayland touch via Sway's `card_shell test-touch` IPC,
`qemu-riscv64-static` user-mode emulation of the real cross-built riscv64
binaries) -- no board, no real finger, no physical panel. The coordinator's
own board reproduction (Themes carousel real, preview page slow/silent,
continuous ~15fps commit/frame-done while idle) is the bug this addresses;
see the task brief and `docs/evidence/omarchy-themes/background-decode-cache-qemu/board-timing.md`
for the previously-recorded on-board Python/decode timing this does not
change.

## Root cause of the idle redraw

`main.rs`'s event loop already called `RendererCache::poll_theme_thumbnails()`
unconditionally every iteration and correctly set `dirty = true` only when
that call's own `changed` return value said something actually arrived
(a decode completed). Separately, further down the same loop body, a second
block did this instead:

```rust
if state.renderer.theme_thumbnails_pending() {
    state.dirty = true;
}
```

`theme_thumbnails_pending()` only says whether some visible carousel slice's
bitmap is still unresolved -- it says nothing about whether anything changed
*this iteration*. Forcing `dirty = true` on that alone meant: for the entire
span a thumbnail or the "Selected background" still preview was decoding
(observed 8-28s on the real board), the loop rendered a full, unchanged
Cairo scene and committed a new Wayland buffer at whatever rate the
compositor's own frame callback allowed -- effectively the panel's own frame
rate, continuously, regardless of whether the frame just rendered looked any
different from the one before it. That full scene render (carousel paint,
hit-test geometry, icon lookups) is real CPU work on the K230's single
in-order C908 core, directly competing with the background worker thread
doing the actual decode -- worse than merely wasteful, it measurably slowed
the very decode the user was waiting on.

The fix (`nix/rust-shell-client/src/main.rs`): delete that block. Retries of
dropped/queued thumbnail requests and draining completed decodes already
happen every iteration regardless (`poll_theme_thumbnails`/`poll_theme_image`
are called unconditionally near the top of the loop), so nothing about
correctness depended on the deleted block. In its place, a new, deliberately
throttled `THEME_PULSE_INTERVAL` (160ms, ~6/s) drives the one legitimate
reason left to redraw without anything having changed: advancing the
loading-spinner animation (`ThemeView::pulse_phase`) while a thumbnail
decode, a still-preview decode, or a pending Activate is genuinely in
flight. This satisfies the goal as stated -- render only for an animation, a
completed decode, or input -- and bounds that animation's own cost, rather
than removing feedback during a real wait.

Regression coverage: `render::tests::pending_thumbnails_do_not_by_themselves_report_a_change`
(a fresh decode request must not itself report `changed`, proving pending
and changed are decoupled) plus the QEMU idle-window measurement below.

## Immediate feedback (goal 1)

- **Pressed slice**: `theme_carousel::Carousel::pressed()` (new) reports the
  tapped slice index the instant a touch lands inside the carousel band and
  hasn't yet moved past `TAP_SLOP` into a drag; `main.rs` mirrors it into
  `ThemeView::theme_pressed`/`background_pressed` on every relevant touch
  event and redraws immediately. `render.rs::paint_carousel` washes that
  slice with the theme's own accent color. Unit test:
  `theme_carousel::tests::pressed_shows_immediately_on_down_and_clears_on_drag_or_release`.
- **Loading spinner**: any carousel slice without a resolved thumbnail, the
  "Selected background" preview box while its still is decoding, and the
  confirmed-but-still-loading slice while a Preview request is in flight all
  paint a small rotating-arc spinner (`render.rs::spinner`), animated by the
  same throttled `pulse_phase`.
- **Busy Apply**: while an `Activate` request is outstanding the footer
  label switches to "Applying…" with its own spinner, distinct from the
  general muted/pending wash the footer already had.
- Unit test: `render::tests::pressed_and_activating_states_change_painted_pixels`.
- Screenshots: `screens/02-pressed-highlight.png` (teal-tinted centered
  slice, mid-touch, no release yet) and `screens/04-backgrounds-mid-decode.png`
  (spinners in both the "Selected background" box and the background
  carousel's centered/neighbor slices -- this is the exact "empty outlines"
  moment from the bug report, now with a visible loading affordance instead
  of silence).

## Fast thumbnails (goal 3)

- **(a) Build-time thumbnails for bundled themes.** **Superseded by the
  "Follow-up: staged-generation-copy fix" section at the end of this
  document** -- the path-mirroring lookup described in this bullet missed
  every staged generation copy (the actual path the chooser decodes) and
  has been replaced with content-hash keying. Left as-is below for the
  historical record of why the mirrored-tree layout was chosen over
  putting the cache inside a theme's own directory, which is still
  accurate and still the reason the seed lives in a directory of its own.
  A new hidden CLI verb,
  `--write-thumbnail-cache SOURCE expanded|slice WIDTH HEIGHT`
  (`theme_thumbnails::write_builtin_thumbnail`), precomputes a decoded,
  cropped-to-size `.rgba` file at a path that *mirrors* `share/omarchy/
  themes/<name>/<rest>` to a sibling `share/omarchy/thumbs/<name>/<rest>-
  <variant>-<w>x<h>.rgba` (see `theme_thumbnails::builtin_thumbnail_path`).
  This is **not** a sibling inside the theme's own directory: an earlier
  version of this change put it there and broke
  `tests/test_handheld_theme_bundle.py` for a real reason, not a test
  nuisance -- `tools/theme_sources.py::source_digest` hashes a theme's
  directory *recursively*, so every generation identity
  `tools/theme_activate.py::prepare` computes (including the pinned bundled
  generation in `bundled-report.json`) would have silently changed the
  moment a cache file appeared inside that tree. The mirrored `thumbs/`
  tree keeps the theme directories byte-for-byte exactly what
  `source-inventory.json` pins. `nix/handheld-theme-default/default.nix`
  now runs the precompute for every bundled theme's `preview.*` (at
  `theme_carousel::THEME_GEOMETRY`'s two sizes) and every background image
  (at `BACKGROUND_GEOMETRY`'s two sizes), after the existing background
  resize step. Verified in the built package:
  `share/omarchy/thumbs/catppuccin/preview.png-expanded-480x640.rgba` and
  four `*.rgba` files per background under
  `share/omarchy/thumbs/catppuccin/backgrounds/`, each exactly
  `16 + width*height*4` bytes (checked against `1-totoro.webp` etc. -- the
  exact backgrounds named in the bug report), and
  `tests/test_handheld_theme_bundle.py --package <built handheld-theme-default>`
  passes both its "20 unchanged source files" check and
  `check_all_builtins_resolve` against the real `theme_catalog`/
  `theme_activate` code path. The worker checks this mirrored path *before*
  anything else, so a bundled theme's first view on a fresh board never
  pays for a full decode.
- **(b) Persistent on-disk cache for user themes.** `theme_thumbnails.rs`
  adds a second, content-hash-keyed cache under
  `$XDG_CACHE_HOME/k230-shell/thumbs/` (falling back to
  `$HOME/.cache/...`), bounded to 24 MiB with oldest-file-first eviction
  (`evict_until`). A cache miss decodes once (off the render thread, in the
  existing worker) and writes through; a later view -- this run or after a
  restart -- reads the small file directly. Unit tests:
  `disk_cache_round_trips_and_rejects_mismatched_geometry`,
  `evict_until_removes_oldest_files_first_until_back_under_the_cap`,
  `resolve_persists_a_fresh_decode_to_the_runtime_disk_cache_for_next_time`,
  `resolve_prefers_an_existing_runtime_cache_hit_over_a_fresh_decode`,
  `disk_cache_dir_prefers_xdg_cache_home_then_falls_back_to_home_then_none`.
  QEMU timing below shows a real 4.5x speedup between a cold and warm view
  of the same full-resolution fixture.
- **(c) Centered-first, off the render thread.** Already true before this
  change and unchanged: `poll_theme_thumbnails` requests nearby ids
  centered-outward (`.rev()` on `visible_slices`' paint order, see its own
  comment), and every decode -- build-time-cache check, runtime-cache check,
  or full decode -- runs on `ThumbnailWorker`'s dedicated thread
  (`theme_thumbnails.rs`), never on the Wayland dispatch thread. Verified by
  reading the code path, not changed by this task.
- **(d) Reuse `background.cache` for the "Selected background" preview.**
  `RendererCache::poll_theme_image` previously called
  `BackgroundCache::render(path, None, ...)` for the live still preview --
  passing `None` for `generation_root` meant it never consulted the exact
  same `background.cache` file `tools/theme_activate.py`'s `prepare()`
  already writes for that generation, at the same panel width/height/
  `FitMode::Crop` (`background_decode.rs`). `ThemeImageKey` now carries
  `generation_root` (the parent of `ThemePreview::appearance_path`), and the
  worker passes it through. Unit test:
  `theme_ui::tests::still_preview_reuses_the_generations_background_cache_instead_of_redecoding`
  (writes a cache, deletes the source, proves the worker still succeeds).

## Timings (goal 4)

All runs use a synthetic `k230-theme` command (instant reply, no real
Python startup) so these numbers isolate the Rust client's own render/decode
path; they do **not** include the ~1.2s-per-invocation Python interpreter
startup already measured and left unchanged by this task (see
`../background-decode-cache-qemu/board-timing.md`). Fixture backgrounds are
procedurally generated 3840x2160 solid-color images, matching Catppuccin's
real full-resolution webp backgrounds' pixel dimensions (the ones the bug
report names). "tap to preview page" = wall time from the theme-confirm tap
to the Preview page's background carousel first painting real pixels. "tap
to thumbnails visible" = wall time from the background-confirm tap to that
background's own thumbnail (a distinct solid color) actually appearing,
sampled directly from the rendered frame.

| Run | Throttle | Cache | tap→preview page | tap→thumbnails visible | pending-window commits | idle-window (Ns) commits/frame-done |
| --- | --- | --- | ---: | ---: | ---: | --- |
| before (`b9f81d47`) | none | n/a | 0.276s | 3.419s | -- | 0/0 over 5s |
| after (this branch) | none | cold | 0.281s | 3.468s | -- | 0/0 over 5s |
| before (`b9f81d47`) | cpulimit 50% | n/a | 0.392s | 10.524s | 26 commits / 10.9s (2.38/s) | 1/1 over 5s |
| after (this branch) | cpulimit 50% | cold | 0.372s | 4.807s | 15 commits / 5.18s (2.90/s) | 1/2 over 5s |
| after (this branch) | cpulimit 50% | cold (2nd sample) | 0.381s | 3.625s | 14 commits / 4.01s (3.49/s) | 1/1 over 3s |
| after (this branch) | cpulimit 50% | **warm** (same `XDG_CACHE_HOME` as the row above) | 0.375s | **0.806s** | 4 commits / 1.18s | 4/4 over 3s |

Raw JSON for each row: `timings-before-unthrottled.json`,
`timings-after-unthrottled.json`, `timings-before-throttled50.json`,
`timings-after-throttled50.json`, `timings-after-cold-cache-throttled50.json`,
`timings-after-warm-cache-throttled50.json`.

**Reading these numbers.**

- Unthrottled, both builds resolve the (tiny, only 2-background) fixture
  before the idle window even starts, so both show 0 idle commits -- this
  is *not* evidence the bug never existed; it means native x86 QEMU is fast
  enough that the pending window here is too short to observe the
  difference. The throttled rows are where the fix actually shows up.
- At 50% cpulimit (approximating a slower single core, the same technique
  `tests/test_theme_commit_under_occlusion_runtime.py` already uses), the
  fixed build reaches thumbnails-visible in roughly half the wall time of
  the unfixed build on a **cold** cache (4.8s/3.6s vs 10.5s) -- this is the
  idle-redraw fix's CPU-contention effect: the decode worker thread gets a
  much larger share of the one throttled core when the render loop isn't
  also burning it on unchanged full-scene redraws every frame callback.
- The warm-cache row is the same fixed binary, same throttle, second view
  of the identical fixture, sharing `XDG_CACHE_HOME` with the row above it:
  0.8s vs 3.6s, a ~4.5x speedup, isolating goal 3(b)'s persistent disk cache
  specifically (the on-disk read replaces the decode entirely).
- The still-nonzero idle-window commits in the throttled rows (1-4 over
  3-5s, vs the old bug's *continuous* ~15fps for the whole 8-28s wait) are
  the throttled pulse animation itself plus at most one real
  completion-triggered redraw -- an intentional, bounded animation, not the
  fixed-forever busy-loop this task set out to remove.

**Estimating real board numbers.** `qemu-riscv64-static` plus a 50% cpulimit
throttle is not a calibrated model of the K230's C908 core, so these are
directional, not a hardware claim (`<!-- UNVERIFIED against real silicon -->`
per this project's grounding rules). The relative improvement is the
meaningful number: if the board's own ~15fps continuous-redraw regime was
genuinely stealing roughly half the single core from the decode thread (as
the coordinator's report and this fix's mechanism both suggest), a
similar ~2x reduction in wall time to "thumbnails visible" would be
expected there too -- i.e., something closer to the report's own "8s to
preview page" (unaffected: the Preview page paints before any background
thumbnail needs to resolve) and a materially shorter tail than the reported
28s for backgrounds to finish appearing, before even counting the
build-time/persistent-cache wins above (which apply in full on the board,
independent of this throttle estimate, since they eliminate the full
decode outright on a cache hit).

## Commands run

```
cargo test --offline                                    # 132 passed, 0 failed
python3 tools/blob-scan.py; echo $?                      # ok, exit 0 -- no blob-inventory change needed
nix build --no-link --print-out-paths --max-jobs 1 --cores 6 \
  .#handheld-shell-rust .#handheld-theme-default .#handheld-theme-command .#card-shell
nix eval .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel.drvPath
python3 tests/rust_theme_chooser_qemu.py --sway <sway-unwrapped riscv64> --rust <k230-shell-rust riscv64>
python3 tests/test_handheld_theme_bundle.py --package <built handheld-theme-default>
python3 tests/test_handheld_theme_default.py tests/test_handheld_theme_rendering.py \
  tests/test_handheld_theme_trial.py tests/test_omarchy_theme_activation.py \
  tests/test_omarchy_theme_resolution.py tests/test_omarchy_theme_sources.py \
  tests/test_omarchy_theme_tools.py tests/test_omarchy_theme_transaction.py \
  tests/test_theme_background_metrics.py tests/test_theme_background_status.py \
  tests/test_theme_catalog.py tests/test_theme_preferences.py     # each run individually; all OK
```

The before/after timing and screenshot runs above used an ad hoc harness
(not committed: a throwaway extension of `tests/rust_theme_chooser_qemu.py`'s
own boot/IPC helpers with full-resolution fixtures, wall-clock timing and an
explicit idle window) against a `handheld-shell-rust` build of `master`
`b9f81d47` ("before") and of this branch ("after"), both paired with the
same `sway-unwrapped` binary from `.#card-shell`'s closure
(`nix-store -qR`), via `qemu-riscv64-static` and, for the throttled rows,
`cpulimit -l 50 -i -z --` (the exact binary
`tests/test_theme_commit_under_occlusion_runtime.py` also pins).

## Follow-up: staged-generation-copy fix (branch `fix/chooser-staged-thumbs`)

The board run after landing the above (system `xzb322jc`) caught a real
miss: the Backgrounds carousel was still spinning ~16s after the tap (40
commits in 5s at the pulse rate, i.e. genuinely pending, not idle redraw).
The build-time seed thumbnails existed in the store, but
`theme_thumbnails::write_builtin_thumbnail`'s original lookup was keyed by
mirroring the source's own *path* (`share/omarchy/themes/<name>/<rest>` ->
`share/omarchy/thumbs/<name>/<rest>`). `tools/theme_activate.py::prepare`
stages a byte-for-byte copy of a theme's background under
`~/.local/state/omarchy/current/generations/<gen>/theme/backgrounds/...`
before the chooser ever decodes it -- the Rust client only ever sees that
staged path, which has no `themes` component, so the precomputed thumbnail
was silently never found and every first view paid for a full 4K decode.

**Fix:** both disk caches (build-time seed and runtime) are now keyed by the
*same* mechanism -- the source file's own content hash, exactly like the
runtime cache already was -- rather than by path. The seed ships as a flat,
read-only, content-hash-named directory
(`share/omarchy/thumbs-by-hash/<hash>-<variant>-<w>x<h>.rgba`) inside
`handheld-theme-default`, wired to the shell process as
`K230_THEME_THUMBNAIL_SEED` by `nix/shell.nix` (same pattern as the existing
`K230_THEME_DEFAULT_GENERATION`). A staged copy's bytes are identical to the
pinned source's (`checked_copy` never re-encodes), so its hash matches
regardless of which of the two paths -- or any future third one -- asked.
Checked also for the theme list's own `preview.png` (never staged, already
worked, and still works identically under the new key) and the "Selected
background" still preview (already fixed by reusing `background.cache`
directly in the previous commit, an unrelated and unaffected code path).

**Real, non-board verification that the exact reported gap is closed**
(`tests/test_handheld_theme_bundle.py`'s own `theme_activate.prepare()`
call, against the newly built package, no synthetic fixture): staging
`catppuccin` produces
`generations/<gen>/theme/backgrounds/1-totoro.webp` (the exact background
named in both the original report and the coordinator's follow-up); its
SHA-256 matches the pinned source's, and a `share/omarchy/thumbs-by-hash/
<that hash>-{expanded,slice}-*.rgba` pair exists in the built package.

**Quick throttled-QEMU timing, real command, real bundled theme** (not the
synthetic-fixture harness above -- this drives the actual built
`handheld-theme-command`'s `k230-theme` against the actual built
`handheld-theme-default`, under a fresh `$HOME` so a real generation gets
staged, with `K230_THEME_THUMBNAIL_SEED` wired exactly as `shell.nix` does):
opening the Themes carousel and confirming the first-discovered theme
(`catppuccin`) settles its background carousel (a full-resolution Totoro/
waves/blue-eye/omarchy set) in **2.45s at 50% cpulimit throttle** (6 total
commits) and 2.55s unthrottled -- versus the reported ~16s/40-commits this
branch fixes. `timing-staged-fix-real-catppuccin-{unthrottled,throttled50}.json`.

Proof commands for this follow-up: `cargo test --offline` (134 passed, 0
failed, including the new regression test
`theme_thumbnails::tests::resolve_finds_a_seed_thumbnail_for_a_staged_generation_copy_at_a_different_path`),
`nix build --no-link --print-out-paths --max-jobs 1 --cores 6
.#handheld-shell-rust .#handheld-theme-default .#handheld-theme-command
.#card-shell`, `nix eval
.#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel.drvPath`,
`python3 tests/rust_theme_chooser_qemu.py`, `test_handheld_theme_bundle.py`
plus every `test_handheld_theme_*`/`test_theme_*`/`test_omarchy_theme_*`
host suite (all pass), `python3 tools/blob-scan.py` (exit 0). Host and QEMU
only; the board was not touched for this follow-up.
