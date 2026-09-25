# webOS-fan card overview: headless-QEMU evidence

Evidence for `openspec/changes/the-shell-behaves-as-one-coherent-system` slice
A, revised to the user's chosen direction: a webOS-style card "fan" (2-3
small cards visible at once, tight spacing, real icon + app name above each
card) rather than a wider single-card carousel.

## Method

`tools/capture-webos-fan-switcher.py`, run against the real `nix build
.#card-shell` cross-built riscv64 Sway under `qemu-riscv64-static` user-mode
emulation (the same headless-QEMU + `card-appearance-socket` path
`tools/capture-bare-app-cards.py` and
`tests/test_card_shell_appearance_runtime.py` already use), at the real panel
size (568x1232). Three synthetic `card-composition-probe-client` windows are
mapped as `k230.card.one/two/three`, matched via `StartupWMClass` to
locally-written `.desktop` fixtures naming the real identities this repo's
own shell uses for its three built-in apps (`nix/handheld-desktop-entries.nix`:
Terminal/foot, Monitor/htop, Files/folder), with `XDG_DATA_DIRS` pointing at
those fixtures plus a real `foot`/`htop`/Yaru-icon-theme closure
(`nix/handheld-theme-icons`) so the icon resolution in
`nix/card-shell/icon.c` runs against real installed icon files, not a stub.
`K230_ICON_THEME=Yaru` is set explicitly for this capture (see icon.c's own
doc comment: live appearance-driven icon-theme switching is not wired yet;
the shell's own default is `K230_ICON_THEME`/`hicolor` unless a theme
supplies its own `icon_theme`, matching `render.rs`'s
`icon_theme_name_for`). Touch is injected through the real
`card_shell test-touch` IPC path (`SWAY_K230_CARD_TEST_INPUT=1`,
`nix/card-shell/test-input.c`), the same synthetic-touch fixture
`tests/test_card_shell_*_runtime.py` use, driving the real
`seatop_touch_down/motion/up` -> `card_shell_down/motion/up` ->
`cs_down/cs_motion/cs_up` path, not a policy-only unit-test shortcut.

This is headless-QEMU proof (real cross-built compositor code, real IPC,
real synthetic touch), not board/panel/real-finger touch proof. No board or
`/dev/ttyACM0` access was used.

## Sequence captured, per theme (dark = the bundled default Catppuccin-Mocha
generation; light = a synthesized Catppuccin-Latte-like palette through the
same real report.json/appearance.json path
`capture-bare-app-cards.py` already establishes as legitimate, since this
repo has no bundled light theme in-tree)

1. `01-overview` -- `card_shell enter` with the middle app (Monitor)
   focused: the fan shows the selected card at full size with a legible
   peek of its neighbour(s), each with a resolved icon (Yaru's monitor/
   folder glyphs, foot's own hicolor glyph -- not a letter badge) and its
   real `.desktop` `Name=` above the card, never the raw window title.
2. `02-scrolling` / `03-scrolled-settled` -- a fast ~8ms-cadence horizontal
   drag and release: the selection pages over, and `03` (captured after the
   momentum coast's fixed 240ms settle window) shows the newly-selected
   card resting exactly centered, not mid-animation.
3. `04-after-close` -- a flick-up throw on the selected card: it closes
   (`card-composition-probe-client` accepts the `xdg_toplevel` close by
   default), the deck's status reads "App closed", and the remaining two
   cards re-flow.
4. `05-opened` -- a plain tap on the remaining selected card: the deck
   chrome (title, footer cue) disappears, confirming the compositor left
   `CS_DECK`. The synthetic floating probe-client windows (each forced to a
   fixed 520x1040 floating geometry by this fixture's own `sway.conf`, not
   tiled/maximized like a real app) do not produce a clean single-app
   full-bleed frame the way a real window would; this is judged to be an
   artifact of the floating-window test fixture, not of the card-shell
   change, and is called out here rather than asserted away.

## What this does not show

- Real board/finger touch, optical legibility, or panel colour rendering
  (UNVERIFIED; no board access was used).
- The exact resolved neighbour-peek fraction "looking right" at arm's
  length -- a host/QEMU render is not an on-glass legibility check.
- Live appearance-driven icon-theme switching (icon.c reads
  `K230_ICON_THEME` once; the shell's live theme-swap protocol does not yet
  carry an icon theme to the C compositor -- see icon.c's own doc comment
  and `docs/design/shell-ux-critique.md` #1.2's note that this
  cross-boundary resolver architecture is still undesigned).

## Commands

```
nix build .#card-shell --max-jobs 1 --cores 6 --no-link --print-out-paths
SWAYBIN=$(nix-store -qR <that path> | grep -m1 sway-unwrapped-riscv64)/bin/sway
python3 tools/capture-webos-fan-switcher.py --sway "$SWAYBIN" \
  --client <host-arch nix/card-composition-probe-client build> \
  --icon-roots <symlinkJoin of pkgs.foot, pkgs.htop, nix/handheld-theme-icons> \
  --output /tmp/k230-fs-N
```
