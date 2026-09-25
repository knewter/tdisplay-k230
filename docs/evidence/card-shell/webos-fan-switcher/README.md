# webOS-fan card overview: headless-QEMU evidence

Evidence for `openspec/changes/the-shell-behaves-as-one-coherent-system` slice
A, revised to the user's chosen direction: a webOS-style card "fan" (2-3
cards visible at once, real icon + app name above each card) rather than a
wider single-card carousel, then a sizing/polish pass driven directly by
board feedback (installed `w51crww9`) and a real-glass scroll-physics report.

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
Terminal/foot, Monitor/htop, Files/folder). `XDG_DATA_DIRS` points at those
fixtures plus a real `foot`/`htop`/Yaru-icon-theme closure
(`nix/handheld-theme-icons`), so `nix/card-shell/icon.c` resolves against
real installed icon files -- both PNG and SVG (via librsvg) -- not a stub;
this is the same fix that closed the board-reported gap ("Monitor" showed a
letter badge, not a real icon, under the real installed theme). Each window
is marked `card_shell ordinary`, `floating enable`, `resize set 100 ppt 100
ppt`, `move position 0 0` -- the same recipe the real shell uses for an
ordinary app window -- rather than a small fixed floating size; an earlier
capture generation used a smaller, inconsistent fixture size and showed an
odd-looking overlapping card and a broken composite "opened" frame, both
artifacts of that fixture, not of card-shell, and both are gone with this
recipe. `K230_ICON_THEME=Yaru` is set explicitly for this capture; the
active theme's own `icon_theme` (report.json, followed automatically via
`appearance_apply`) is not exercised by this fixture, which uses the bundled
default/synthesized-light report/appearance pair directly, neither of which
sets that field. Touch is injected through the real `card_shell test-touch`
IPC path (`SWAY_K230_CARD_TEST_INPUT=1`, `nix/card-shell/test-input.c`), the
same synthetic-touch fixture `tests/test_card_shell_*_runtime.py` use,
driving the real `seatop_touch_down/motion/up` -> `card_shell_down/motion/up`
-> `cs_down/cs_motion/cs_up` path, not a policy-only unit-test shortcut.

This is headless-QEMU proof (real cross-built compositor code, real IPC,
real synthetic touch), not board/panel/real-finger touch proof. No board or
`/dev/ttyACM0` access was used.

## Sequence captured, per theme (dark = the bundled default Catppuccin-Mocha
generation; light = a synthesized Catppuccin-Latte-like palette through the
same real report.json/appearance.json path
`capture-bare-app-cards.py` already establishes as legitimate, since this
repo has no bundled light theme in-tree)

1. `01-overview` -- `card_shell enter` with the middle app (Monitor)
   focused: the fan shows the selected card at roughly half the panel's
   width and 60% of its height, vertically centered between the title and
   the "Swipe up for apps" hint, with a legible peek of its neighbour(s).
   Each card carries a resolved icon (Yaru's Monitor/Files glyphs, foot's
   own hicolor glyph for Terminal -- confirmed real icons, not a letter
   badge, including an icon reached only through SVG) at 36px, and its real
   `.desktop` `Name=` at 20px above the card, never the raw window title.
2. `02-scrolling` / `03-scrolled-settled` -- a fast ~8ms-cadence horizontal
   drag and release: the fling's projected velocity carries the selection
   past the adjacent card (a multi-card jump, not a one-card snap), and `03`
   (captured after the momentum coast's own -- now fling-distance-scaled,
   up to ~760ms -- settle window) shows the newly-selected card resting
   exactly centered, not mid-animation.
3. `04-after-close` -- a flick-up throw on the selected card: it closes
   (`card-composition-probe-client` accepts the `xdg_toplevel` close by
   default), the deck's status reads "App closed", and the remaining two
   cards re-flow with no overlap artifact.
4. `05-opened` -- a plain tap on the remaining selected card: a clean,
   full-bleed single-app frame (the "ordinary maximized" fixture fixes the
   earlier composite/overlap artifact from a smaller, inconsistent floating
   window size), confirming the compositor left `CS_DECK`.

## What this does not show

- Real board/finger touch, optical legibility, or panel colour rendering
  (UNVERIFIED; no board access was used).
- The exact card size/text/icon "looking right" at arm's length -- a
  host/QEMU render is not an on-glass legibility check.
- Live appearance-driven icon-theme switching in practice: `appearance_apply`
  now calls `card_icon_set_theme` whenever a loaded report names an
  `icon_theme`, but this fixture's own report/appearance pair does not set
  that field, so only the `K230_ICON_THEME` env/hicolor default path is
  exercised here, not the report-driven one.
- The exact left/right neighbour a given app lands as: `p->cards[]`'s
  insertion order follows this fixture's own window-mapping order, which is
  not deterministically tied to `--app-id` launch order; the dark and light
  captures show different neighbour arrangements for this reason, and
  neither is a claim about production ordering.

## Commands

```
nix build .#card-shell --max-jobs 1 --cores 6 --no-link --print-out-paths
SWAYBIN=$(nix-store -qR <that path> | grep -m1 sway-unwrapped-riscv64)/bin/sway
python3 tools/capture-webos-fan-switcher.py --sway "$SWAYBIN" \
  --client <host-arch nix/card-composition-probe-client build> \
  --icon-roots <symlinkJoin of pkgs.foot, pkgs.htop, nix/handheld-theme-icons> \
  --output /tmp/k230-fs-N
```
