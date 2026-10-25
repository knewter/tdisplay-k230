## 1. Host

- [x] 1.1 Add the exact opaque/zero chunk shortcuts with the per-row bail-out to RVV `over_8888_0565` (`nix/patches/pixman-rvv-over-0565-exact-shortcuts.patch`), scoped to the compositor in `nix/card-shell.nix`. Proof: `nix build .#nixosConfigurations.k230-mainline-drm-shell-landscape-hdmi.config.system.build.toplevel` (`h4rqzlgr`), with sway's RUNPATH listing the patched Pixman first.

## 2. Board (hardware-only)

- [x] 2.1 Byte-exact check of stock RVV, patched RVV and scalar Pixman on 112 OVER a8r8g8b8 → r5g6b5 cases (`docs/evidence/interaction-jank/keyboard-blend/exact.c.txt`: identical sha256 `a39338ae…`).
- [x] 2.2 Run the drawer and keyboard measurement on the boot default (`pb5l6lmb`) and the candidate (`h4rqzlgr`, test-activated) on one boot, and pixel-compare their grim captures (`docs/evidence/interaction-jank/keyboard-blend/README.md`: show settle 38.3 → 19.2 ms interval median, render 16.0 → 10.0 ms; drawer repaint 10.19 → 10.22 ms; six captures identical).
- [ ] 2.3 Promote the build from master to the boot default, and verify an ordinary boot, the loaded Pixman and one drawer-and-keyboard run on it.
