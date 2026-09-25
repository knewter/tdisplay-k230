# "Why don't I ever see a background image": QEMU root-cause investigation

Filed against the user report that catppuccin-latte's selected background
("Color fade", `backgrounds/1-color-fade.webp`) never appears -- the card
overview and drawer show a flat, uniform fill in latte's own palette
`background` colour (`#eff1f5`) instead of the image, on the installed board
system built from `master` `b9d892c7`. This is a **host + headless-QEMU**
result: no board, glass, or real-finger observation. Run 2026-09-24, worktree
`fix/wallpaper-visible-swap-jank`, base `master` `b9f81d47`.

## What was checked and ruled out

Traced the full path from `tools/theme_activate.py`'s `prepare()` through
`nix/rust-shell-client/src/appearance.rs`'s snapshot loader,
`background_decode.rs`'s decode/cache, `main.rs`'s `draw_wallpaper()`, and
`nix/card-shell/appearance.c`/`adapter.c`'s deck-canvas transparency
(`appearance_canvas_refresh`). Every step was exercised directly, not just
read:

- `tools/theme_activate.py prepare(...)` against the real pinned
  `catppuccin-latte` source (`nix/omarchy-theme-tools/upstream` +
  `theme_sources.py`'s fetched builtins, `1-color-fade.webp`, VP8 lossy,
  1536x1024) produces `report.json` with
  `"selected_background": "backgrounds/1-color-fade.webp"` and
  `appearance.json` with `"background": "background"` -- the sentinel that
  both `nix/rust-shell-client/src/appearance.rs`'s parser and
  `nix/card-shell/appearance.c`'s `load()` require to set the wallpaper flag.
- `k230-shell-rust --write-wallpaper-cache <source> <generation> 568 1232`
  (the hidden verb `tools/theme_activate.py`'s `build_wallpaper_cache` calls)
  decodes the real webp correctly on both the native x86_64 build and the
  riscv64 build under `qemu-riscv64-static` -- byte-identical cache files
  (`cmp` clean), sampled at 235 distinct colours across a coarse grid, not a
  flat fill.
- `AppearanceReceiver::bind_with_roots` against a real `prepare()`d
  generation resolves `background = Some(.../1-color-fade.webp)` and
  `fallback_still()`'s logic picks it correctly, both from the `active`
  symlink and from a live "commit" event's embedded generation/path pair.
- The full paired protocol, real compositor, real Rust shell, real
  `catppuccin-latte`, under headless QEMU
  (`tests/test_real_theme_paired_runtime.py`), against store paths built
  fresh from this worktree:
  - sway: `/nix/store/0rv28hkhciv5w5mvnxx47wp9l5ml2kqb-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`
    (from `nix-store -qR` of `.#card-shell`)
  - rust shell: `/nix/store/zbj1bad4kkiay9i6yi6w3kmcd0spr9f9-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust`
    (`.#handheld-shell-rust`)
  - client: `/nix/store/71rhd3yzyqi8qkyrbrcc988dsdfsg6cv-k230-card-composition-probe/bin/card-composition-probe-client`
    (`nix-store -qR` of `.#card-composition-probe`)
  - theme bundle: `/nix/store/sgivy8dgc1apdlcdsswz9sagzhpj3rzf-handheld-theme-default-28ceaae7`
    (`.#handheld-theme-default`)
  - icons: `/nix/store/in3nc21zx02xiz2rdp5bpq36719x3axd-handheld-theme-icons-25.10.3`
    (`.#handheld-theme-icons`)

  Result: **PASS**, both without and with `--wallpaper-cache-tool` (the new
  argument this change adds -- see below). The deck showed the real image at
  both sample points, matching a centered-crop of the source exactly:
  `latte_wallpaper_upper=(254,238,221)` at `(10,300)` and
  `latte_wallpaper_lower=(241,210,227)` at `(10,700)`, both equal to
  `expected_wallpaper()`'s independently-computed PIL crop/resize of the
  same source file. The drawer showed the authored Latte launcher brush
  (`latte_drawer=(238,240,245)`), not a flat fallback. Rollback after an
  injected second-commit failure restored the same pixels. `default-deck.png`,
  `latte-deck.png`, and `latte-drawer.png` in this directory are the actual
  compositor captures; `latte-deck-cache-hit.png` is the same deck capture
  from the cache-hit run (see below), pixel-identical to `latte-deck.png`.

**Conclusion: the current source tree does not reproduce the reported bug.**
Every stage of the pipeline -- theme preparation, the decode cache, both
appearance receivers' JSON parsing, the deck's canvas-transparency logic,
and the compositor's actual pixel output -- was independently exercised
against the real theme package and produced the correct image, not a flat
fill, with byte-exact pixel matches. `#eff1f5` (latte's flat `background`
palette colour, and the colour the user's grim capture matched) is exactly
what `nix/rust-shell-client/src/render.rs`'s `draw_wallpaper()` procedural
fallback paints when `wallpaper_path` is `None` -- i.e. this class of bug
requires the active generation's `appearance.json` to have `"background":
null` (or the receiver to fail to resolve the `active` pointer at all), a
state this investigation could not produce from any current, correctly
`prepare()`d generation.

## Closing a real coverage gap: the cache-hit path was previously untested end-to-end

`tests/test_real_theme_paired_runtime.py`'s `prepare()` calls never passed
`wallpaper_cache_tool`, so every previous run of this test (including the
historical `docs/evidence/coherent-shell/real-theme-paired-qemu/README.md`
proof this investigation started from) only exercised
`background_decode.rs`'s **full-decode** path, never the `background.cache`
**cache-hit** path that `handheld-theme-command.nix` always uses on the real
board (`wallpaperCacheFlag`, gated on `coherentShell`). This change adds
`--wallpaper-cache-tool` to the test, asserts each prepared generation
actually got a `background.cache` file, and reruns the whole paired
transaction through it. Result: pixel-identical to the full-decode run
(`latte-deck-cache-hit.png` vs `latte-deck.png`), confirming the cache
mechanism introduced by `aab56856` is not the source of the reported bug
either.

One run with `--wallpaper-cache-tool` hit a **pre-existing, documented,
load-dependent flake** at `app_after = wait(expanded_app, 5)` (the
post-`card_shell back` app-settle wait), identical in shape to the failure
`docs/evidence/omarchy-themes/background-decode-cache-qemu/README.md`
already recorded against both a modified and an unmodified `origin/master`
build under host load (`load average: 16.69, 18.02, 19.93` on this shared
dev host during this run, from concurrent unrelated agents). This is after
the point where every wallpaper/cache assertion this change added had
already passed (`latte-deck.png` was written); it is not a wallpaper
regression, and matches a failure mode this repository already attributes
to host CPU contention, not to this code path.

## Most likely explanation for the board observation

Given the mechanism is correct in the current source end-to-end, the
remaining plausible explanations are board-state, not code:

1. **A stale `~/.local/state/omarchy/current` generation.** Generations are
   "immutable, hash-identified, one-shot" (`background_decode.rs`'s own
   comment) and persist across NixOS generation switches (they are user
   state, not managed by the image) -- exactly the kind of state
   `AGENTS.md`/`openspec/config.yaml` warn is never restored to preserve
   bring-up settings. If the board's `active` pointer or a remembered
   generation predates a fix to the wallpaper token scheme, it would be
   silently reused (idempotent `prepare()`) instead of regenerated, since its
   `generation` hash only changes when `theme_activate.py`/`theme_tokens.py`
   themselves change.
2. **A stale or truncated `background.cache` written by a different Rust
   binary version than the one now installed.** `background.cache`'s
   validity check (`load_cached` in `background_decode.rs`) only compares
   width/height/mode, not a content or code version, so a cache file
   produced by an earlier `k230-shell-rust` remains a cache *hit* for a
   later one even if the earlier binary's encoding differed.

## Board command for the coordinator

Read-only diagnosis first (does not touch the running session):

```sh
./tools/console.py /dev/ttyACM0 --wait=3 \
  "cat ~/.local/state/omarchy/current/active/report.json | grep selected_background"
./tools/console.py /dev/ttyACM0 --wait=3 \
  "cat ~/.local/state/omarchy/current/active/appearance.json | grep -o '\"background\": [^,]*'"
./tools/console.py /dev/ttyACM0 --wait=3 \
  "ls -la ~/.local/state/omarchy/current/active/background.cache"
```

If `"background"` above is `null` while `selected_background` names a still
image, that generation predates or otherwise lost the wallpaper token and
should be discarded and regenerated (safe: generations are a disposable
cache, not durable state):

```sh
./tools/console.py /dev/ttyACM0 --wait=3 \
  "rm -rf ~/.local/state/omarchy/current/generations ~/.local/state/omarchy/current/active && \
   runuser -u shell -- k230-theme activate --json catppuccin-latte --expected-generation $(runuser -u shell -- k230-theme preview --json catppuccin-latte | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"generation\"])')"
```

Then re-check with `swaymsg card_shell enter` + `grim` per the original board
facts. If `"background"` is already `"background"` and the cache is present
and sized 2,799,121 bytes, the generation is not stale and the divergence
lies somewhere this investigation's QEMU fixture cannot reach (e.g. a
real-hardware-only rendering path); that would need a fresh board capture
with `RUST_LOG`/`SWAY_K230_CARD_SHELL` diagnostics to progress further, which
this task was directed not to run itself.

## Reproduce

```sh
nix build --no-link --print-out-paths --max-jobs 1 --cores 6 \
  .#handheld-shell-rust .#card-shell .#card-composition-probe \
  .#handheld-theme-default .#handheld-theme-icons

python3 tests/test_real_theme_paired_runtime.py \
  --sway "$(nix-store -qR $(nix build --no-link --print-out-paths .#card-shell) | grep sway-unwrapped-riscv64)/bin/sway" \
  --rust "$(nix build --no-link --print-out-paths .#handheld-shell-rust)/bin/k230-shell-rust" \
  --client "$(nix build --no-link --print-out-paths .#card-composition-probe)/bin/card-composition-probe-client" \
  --theme-bundle "$(nix build --no-link --print-out-paths .#handheld-theme-default)" \
  --icons "$(nix build --no-link --print-out-paths .#handheld-theme-icons)" \
  --wallpaper-cache-tool "$NATIVE_K230_SHELL_RUST/bin/k230-shell-rust" \
  --output /tmp/k230-wj-repro
```

`--wallpaper-cache-tool` must be a build-machine-native (e.g. x86_64) binary,
not the riscv64 one used for `--rust`: `tools/theme_activate.py`'s
`build_wallpaper_cache` runs it directly with `subprocess.run`, no `qemu`
wrapper, exactly like `nix/handheld-theme-default/default.nix`'s own
`wallpaperCacheTool = buildPackages.callPackage ../rust-shell-client { }`.
This run used `/nix/store/2fy35zmwcz1yxd8cnbhs84a8q1lfiq9b-k230-shell-rust-0.1.0/bin/k230-shell-rust`,
an x86_64 build already resident in this host's store from a prior
`handheld-theme-default` build; any equivalent native build of
`nix/rust-shell-client` works (`$NATIVE_K230_SHELL_RUST` above stands for
that path, which is not a stable output across hosts).
