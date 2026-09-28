# Overlay squashes when wvkbd shows: before/after

Headless QEMU, real cross-built executables under `qemu-riscv64-static`,
IPC-injected touch (`card_shell test-touch`) plus a real
`zwp_virtual_keyboard_v1` connection to reach the Wi-Fi password field, and
the real, cross-built `wvkbd-mobintl` (not a synthetic stand-in) shown
through the same `k230-keyboard-gesture-signal` path production uses. A
private synthetic root broker inside a user namespace supplies only invented
`Example` network names. **Not** a board, panel, or real-finger observation.

## The reported bug

2026-09-28, real-glass capture `/tmp/coherent-settings.png`: the moment
`wvkbd` appeared on the Wi-Fi Settings page, the whole page squashed
vertically to about 0.66x its height -- "Wi-Fi", "Cancel" and "Connect" all
visibly squat, the header at y≈39 instead of ≈59, Cancel/Connect at y≈515
with a big empty gap above the keyboard (top at y≈775).

Root cause: the overlay/home/wallpaper layer surfaces (`Layer::Overlay`/
`Bottom`/`Background`, anchored to all four edges) requested
`set_exclusive_zone(0)`. Per wlr-layer-shell-unstable-v1's own doc for that
request, `0` means "the surface indicates that it would like to be moved to
avoid occluding surfaces with a positive exclusive zone" -- exactly what
`wvkbd`'s own real, positive exclusive zone triggered the instant it showed.
wlroots' `arrange_layers` acted on that by *shrinking* (not moving) these
fully-anchored surfaces, and `LayerShellHandler::configure`'s existing
`configure_size` accepted the smaller height like any legitimate resize.
Every page painted onto these surfaces scales its fixed 568x1232 design-unit
artwork to fill whatever it is given
(`cr.scale(width / 568.0, height / 1232.0)`) -- correct for a genuine output
resize, wrong here: shrinking only the height stretched every glyph and
button vertically.

## Reproduction and fix

`tests/rust_overlay_keyboard_resize_qemu.py` reaches the same WPA2 password
Entry page the bug was reported on (reusing `tests/
rust_wifi_settings_qemu.py`'s Broker/theme/SETTINGS fixtures), then shows the
real `wvkbd-mobintl` through a copy of `nix/shell.nix`'s own
`k230-keyboard-gesture-signal` (`pkill -USR2 -u "$(id -u)" -f wvkbd-mobintl`
-- `-f`, not production's `-x`: under `qemu-riscv64-static` the process the
kernel sees is the *emulator*, `comm` is `qemu-riscv64-st`, not
`wvkbd-mobintl`, confirmed with `/proc/<pid>/comm`; this is a test-harness-
only concession to running wvkbd under emulation at all, not a change to the
production script). It asserts every `configure <W>x<H>` the Rust log
records for the overlay says exactly `568x1232`, and that the header/
password-field region (0,0)-(568,410) -- which the page's own keyboard-aware
reflow never touches, only Cancel/Connect move -- is pixel-identical before
`wvkbd` shows and after.

The fix (`nix/rust-shell-client/src/main.rs`, `ensure_layer`/`ensure_home`/
`ensure_wallpaper`): all three request `set_exclusive_zone(-1)` instead of
`0` ("would not like to be moved \[or resized\]... extend it all the way to
the edges it is anchored to"), so the compositor never proposes a smaller
size for them regardless of what `wvkbd` or any other layer surface
requests. `configure_preserves_aspect` (`nix/rust-shell-client/src/lib.rs`)
adds an independent, defense-in-depth second guard in all three `configure`
branches: a configured size whose aspect ratio drifts more than 10% from
568:1232 is rejected outright.

| | Before fix | After fix |
| --- | --- | --- |
| WPA2 Entry page, keyboard not yet shown | [before-fix-keyboard-hidden.png](before-fix-keyboard-hidden.png) | [after-fix-keyboard-hidden.png](after-fix-keyboard-hidden.png) |
| Same page, real `wvkbd` shown (`-H 400`) | [before-fix-keyboard-shown.png](before-fix-keyboard-shown.png) | [after-fix-keyboard-shown.png](after-fix-keyboard-shown.png) |

The "keyboard not yet shown" pair is byte-identical (both builds render the
same page the same way before `wvkbd` ever shows -- expected, since the fix
only changes what happens *once wvkbd requests its exclusive zone*). The
"keyboard shown" pair is where the bug and fix diverge: the before-fix
capture shows the reported squash -- confirmed in its own Rust log with
`rust-shell 3364ms configure 568x832` (1232 - 400, wvkbd's exclusive zone
eating exactly its own height); the after-fix capture shows no such line at
all (`"new_configures_after_keyboard_shown": 0` in the script's own JSON
result) and is pixel-identical to its own "hidden" capture in the
header/password-field region, matching the script's real assertions, not
just this README's visual description.

## Commands and store paths

Before-fix build, from a throwaway worktree pinned to the pre-fix commit
`cf12c5e8` (the reported bug's exact revision -- everything on `master` up
to and including the Wi-Fi system-keyboard fix, before this change):

```sh
git worktree add /tmp/before-fix cf12c5e8
cd /tmp/before-fix && nix build .#handheld-shell-rust --max-jobs 1 --cores 6 --no-link --print-out-paths
# -> /nix/store/a84l9x3v4ggl6xh6s22zlfzy9nfkqa49-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0
```

After-fix build, from this change's commit `53926919`:

```sh
nix build .#handheld-shell-rust --max-jobs 1 --cores 6 --no-link --print-out-paths
# -> /nix/store/30w4z8lxq7skia8fzyvm9dgn5f2jp7z1-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0
```

Both runs share the same (unaffected by this change) card-shell-patched Sway
and real wvkbd:

```sh
nix build .#card-shell --max-jobs 1 --cores 6 --no-link --print-out-paths
# sway: /nix/store/0a2f857nc1rz65gnjdfn46h32zsyxm18-sway-unwrapped-riscv64-unknown-linux-gnu-1.12
# wvkbd (already part of the system closure's own requisites):
# /nix/store/f78wgpdcniq2v2yn274dd0yi29gh9sc6-wvkbd-riscv64-unknown-linux-gnu-0.20
```

```sh
unshare -Ur python3 tests/rust_overlay_keyboard_resize_qemu.py \
  --sway /nix/store/0a2f857nc1rz65gnjdfn46h32zsyxm18-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --rust <before or after k230-shell-rust store path>/bin/k230-shell-rust \
  --wvkbd /nix/store/f78wgpdcniq2v2yn274dd0yi29gh9sc6-wvkbd-riscv64-unknown-linux-gnu-0.20/bin/wvkbd-mobintl \
  --theme-source nix/handheld-theme-default \
  --output <private-output>
```

Against the after-fix build this exits zero and reports
`headless-qemu-real-wvkbd-overlay-resize`. Against the before-fix build it
raises `AssertionError` on the committed script's own assertions (the
`capture_words` OCR check on the squashed page's re-flowed text fails first,
before the pixel/log assertions are even reached) -- both captures above
were still saved to disk by the time it did, since `grim` writes each
screenshot as it is taken. On this shared build machine's current load
(dozens of concurrent agents' `nix build`s), the unrelated, pre-existing
`--surface` helper (`nix/rust-shell-client/src/main.rs`'s `request()`, a
separate short-lived process with its own fixed 500ms socket deadline,
untouched by this change) was intermittently slower than that deadline;
capturing both runs used the same uncommitted retry wrapper technique
already recorded in `../wifi-settings/keyboard-focus-qemu/README.md` for the
identical, unrelated flakiness.

Host proof:

```sh
cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml --quiet
# lib 301 passed/1 ignored (pre-existing, unrelated), bin 22, and four
# integration test modules (14/8/11/5) all passed, 0 failed -- includes
# lib.rs's new configure_preserves_aspect_accepts_uniform_resize_only
cargo clippy --offline --manifest-path nix/rust-shell-client/Cargo.toml --lib --bins
# no new warnings
```

## Remaining gate

This is headless-QEMU evidence with an invented Wi-Fi fixture and no
physical panel. Real-glass confirmation that the Wi-Fi page (and any other
page) stays full-size with `wvkbd` shown on the actual board remains
**UNVERIFIED** and needs the board reservation, which this change did not
touch.
