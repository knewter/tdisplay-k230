# Keyboard-drag exclusive-zone gap: before/after

Headless QEMU, IPC-injected touch only. **Not** a board, panel, or
real-finger observation. This is `qemu-riscv64-static` running the real
`sway-unwrapped-riscv64-unknown-linux-gnu-1.12` card-shell compositor, the
real `wvkbd-mobintl` keyboard, and the synthetic
`card-composition-probe-client`, driven via `card_shell test-touch` IPC.

## The reported bug

Dragging the keyboard down (or up) resizes the ordinary-maximized app's
usable area every ~16ms animation tick
(`card_shell_keyboard_adjust_usable`/`ordinary_resize` in
`nix/card-shell/adapter.c`). A real client cannot redraw and commit a
matching buffer that fast on this CPU, so its old-sized buffer can still be
attached when the container box has already grown -- the margin between the
old buffer and the keyboard's new (lower) position had nothing painted in
it, exposing whatever sits behind the app.

## Reproduction and fix

`tools/qemu-keyboard-drag-gap-capture.py` starts the app while the keyboard
is already shown (so the client's committed geometry starts at the shrunk
756px height), then holds a one-finger grip-drag partway through hiding the
keyboard without releasing, and samples a pixel in the theoretical gap
region. The synthetic client's own animation loop redraws every frame
regardless of size, which never reproduces the bug on its own, so the
client was given a `--stall-resize-ms` test-only flag
(`nix/card-composition-probe-client/card-composition-probe-client.c`): for
a bounded window after any resize it keeps its old, wrong-sized buffer
attached instead of redrawing, modeling a slow real app.

The fix (`nix/card-shell/adapter.c`, `ordinary_backdrop_sync`) adds a single
card-coloured `wlr_scene_rect` in `output->layers.tiling`, directly behind
ordinary-maximized cards, resized to the output's current `usable_area` on
every `ordinary_sync_usable()` call. Repositioning a scene rect is a pure
compositor-side operation with no client round trip, so it never lags the
animated reservation the way the client's own buffer can.

| | Before fix | After fix |
| --- | --- | --- |
| Drag start (keyboard shown, app at its committed 756px height) | [before-fix-drag-start.png](before-fix-drag-start.png) | [after-fix-drag-start.png](after-fix-drag-start.png) |
| Mid-drag, client stalled 4s, sampled at (284, 891) | [before-fix-mid-drag-gap.png](before-fix-mid-drag-gap.png) | [after-fix-mid-drag-backdrop.png](after-fix-mid-drag-backdrop.png) |

At (284, 891) -- inside the exposed margin between the stalled app buffer
(756px) and the compositor's already-updated usable area (1026px) -- the
before-fix sample is `(0, 0, 0)` (nothing painted; the mid-drag screenshot
shows flat black behind the keyboard). The after-fix sample is
`(36, 73, 90)`, which is exactly `card_color = {.141, .286, .353, 1}`
(unthemed default) at 8-bit precision. Full numeric results:
[before-fix-result.json](before-fix-result.json),
[after-fix-result.json](after-fix-result.json).

This harness has no wallpaper renderer (no Rust launcher is running under
it), so "nothing painted" reads as black rather than the desktop wallpaper
photo the user described; the mechanism -- an unpainted margin between a
stale client buffer and the compositor's already-moved keyboard -- is the
same one, and the fix closes it regardless of what is stacked behind the
app on the real image.

## Regression check

`tests/test_keyboard_gestures_runtime.py` continues to pass unchanged
against the fixed build (its `held_height`/`grip_height` assertions rely on
the same continuous, per-frame `usable_area` tracking that the fix does not
touch -- only the backdrop's own presence is new). Exact command and store
paths used for this checkpoint:

```sh
nix build .#card-shell --max-jobs 1 --cores 4 --no-link --print-out-paths
# -> /nix/store/zk7g16sasa5vkqqfcd70n5kbnn9jzang-k230-card-shell
#    sway: /nix/store/wwsspnnab2q0gp47fcqb8qyh0l6w2mkd-sway-unwrapped-riscv64-unknown-linux-gnu-1.12
python3 tests/test_keyboard_gestures_runtime.py \
  --sway /nix/store/wwsspnnab2q0gp47fcqb8qyh0l6w2mkd-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --client /nix/store/bxiz9zkb33m4v97gkgzx91aswfm7cf9f-card-composition-probe-client-riscv64-unknown-linux-gnu-0.1/bin/card-composition-probe-client \
  --keyboard /nix/store/n7p6qfbyw30yany09x8kr95j2ar1fh7b-wvkbd-riscv64-unknown-linux-gnu-0.20/bin/wvkbd-mobintl \
  --output /tmp/k230-ux-2
# PASS native Sway/wvkbd chord, held/reversed pixels, grip and usable area; no physical proof
```

Gap capture commands (before build from a throwaway worktree pinned to the
pre-fix commit `a68014de`, plus the stall fixture cherry-picked on top; after
build from this change):

```sh
python3 tools/qemu-keyboard-drag-gap-capture.py \
  --sway <pre-fix sway-unwrapped>/bin/sway \
  --client <card-composition-probe-client with --stall-resize-ms> \
  --keyboard <wvkbd-mobintl> --output /tmp/k230-ux-gap-before
python3 tools/qemu-keyboard-drag-gap-capture.py \
  --sway <this change's sway-unwrapped>/bin/sway \
  --client <card-composition-probe-client with --stall-resize-ms> \
  --keyboard <wvkbd-mobintl> --output /tmp/k230-ux-gap-after
```

## Remaining gate

This is headless-QEMU injected-touch evidence with a synthetic client and no
wallpaper renderer. It does not establish panel touch reachability,
real-finger feel, or what the actual Rust launcher's wallpaper looks like
through the gap on real hardware/timing. See the top-level report for the
specific real-glass check this still needs.
