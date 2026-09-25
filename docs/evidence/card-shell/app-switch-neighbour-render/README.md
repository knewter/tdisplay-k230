# Cropped app-switch neighbour and held-frame flicker: root cause and fix

User report, from real glass on the K230 (568x1232): swiping between two
ordinary maximized apps (`k230-monitor` and `k230-terminal`) showed the
incoming neighbour at roughly 70% of the panel height, with wallpaper visible
above and below it and its content cut off, and holding the drag still
"flickers and looks bad".

## Root cause

`nix/card-shell/adapter.c`'s `sync_card()` already gives the incoming
neighbour the outgoing app's own full-panel frame during a direct app-switch
drag (`cs_entry_visual_rect`'s `common_full_frame` case, gated on both cards
being `card_shell_ordinary_maximized`), so the neighbour's mirrored content is
correctly sized and positioned full-screen, sliding in alongside the outgoing
app. But `card_clip_box()` -- the rect every card's live mirror is clipped to
before painting -- special-cased **only** `shell.policy.entry_id` (the
outgoing app) for the full-output clip box:

```c
static struct wlr_box card_clip_box(struct card *c) {
    if ((shell.policy.mode == CS_ENTERING && c->id == shell.policy.entry_id) ||
        (shell.policy.mode == CS_EXPANDING && c->id == shell.policy.expand_id))
        return (struct wlr_box){shell.output->lx, shell.output->ly,
            shell.policy.config.width, shell.policy.config.height};
    return clip_box();
}
```

Every other card -- including the neighbour, even while it is being rendered
at that same shared full-panel frame -- fell through to `clip_box()`, the
small card-*deck* viewport (`cfg.height - top_reserved - bottom_reserved -
title_height - footer_height`, well short of the full panel). The neighbour's
live mirror was therefore never disabled or mis-scaled -- it was full-size
and correctly positioned -- but its paint was cropped to that shorter rect,
so the compositor's own deck backdrop (wallpaper) showed through above and
below it, and the app's own content above/below the crop line was simply
never drawn.

Fix (`nix/card-shell/adapter.c`): a new `struct card.full_clip` flag is set
in `sync_card()` from the exact same `common_full_frame` condition already
computed there, and `card_clip_box()` now grants the full-output clip box to
any card carrying that flag, not only `entry_id`. The wider clip is always a
superset of `clip_box()`, so once a card has actually shrunk into the deck
grid (`entry_progress` near 1) the change is a no-op.

The reported "flicker while holding" is the same defect: the crop boundary
sits in the middle of the panel, and any operator-driven touch stream that
oscillates by even a pixel between the neighbour's own colour and the
backdrop right at that boundary reads as flicker. Removing the crop removes
the boundary. Under noise-free QEMU-injected input the boundary itself
never moved even pre-fix (see "held" measurement below) -- consistent with
that flicker requiring real touch-report jitter, a hardware behaviour this
harness cannot inject -- but it is the same code path and the same fix.

## Measurement

Two synthetic `card_shell ordinary` clients (`k230.card.one` blue,
`k230.card.two` purple, `nix/card-composition-probe-client`), matching the
coordinator's board reproduction: down at (420,1226), stepped to (280,1226)
at constant y, held.

Column scan at the neighbour's own x (content/backdrop classified against
`backdrop = {.067,.094,.153}` from `nix/card-shell/adapter.c`, tolerance 12
per channel):

| Build | Column runs (content=True / backdrop=False) |
| --- | --- |
| before (`/nix/store/1va4angandva4xbm5i0v7367p0nd9jry-k230-card-shell`) | `(False,0,127) (True,128,1175) (False,1176,1231)` |
| after (`/nix/store/s8r1x1wfhk7ch3z40w7ialcrb7w4br9r-k230-card-shell`) | `(True,0,1231)` |

Before: 1048/1232 = 85% of the column is content, the rest wallpaper --
matches the reported cut-off neighbour. After: the full column is content,
no wallpaper rows.

Two captures 1.6s apart while genuinely held (no further injected input):
the content/backdrop boundary is bit-for-bit identical before and after
(`0` classification flips out of 699,776 sampled pixels in both builds,
confirmed with a raw pixel diff too -- see `tests/
test_card_shell_switch_neighbour_runtime.py`); raw pixel differences between
the two held captures (28% of pixels before, 9% after) come entirely from the
synthetic clients' own continuous animation, not from shell state.

## Files

- `before-cropped-neighbour.png` / `after-full-neighbour.png`: single frame,
  mid-drag, showing the crop and the fix.
- `before-held-1.png` / `before-held-2.png`, `after-held-1.png` /
  `after-held-2.png`: the two held captures (~1.6s apart) used for the
  frame-stability measurement above, pre- and post-fix.

## Commands

```sh
git stash                         # clean pre-fix tree
nix build .#card-shell --max-jobs 1 --cores 6 --no-link --print-out-paths
# /nix/store/1va4angandva4xbm5i0v7367p0nd9jry-k230-card-shell
git stash pop                     # fix/app-switch-neighbour-render
nix build .#card-shell --max-jobs 1 --cores 6 --no-link --print-out-paths
# /nix/store/s8r1x1wfhk7ch3z40w7ialcrb7w4br9r-k230-card-shell

python3 -m pytest tests/test_card_shell_switch_neighbour_runtime.py -v
# CARD_SHELL_SWAY / CARD_SHELL_CLIENT pinned to each store path above
```

Headless-QEMU-injected-input evidence only (per `.skills/k230-spec-change/
SKILL.md`'s proof table): this proves the compositor's own composited scene,
not real touch-report jitter, real-glass legibility, or finger reachability.
Those remain **UNVERIFIED** and require the physical board.
