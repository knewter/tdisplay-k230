# Themed shell installed preview

Source `aab74fb78dd7ed47a521146827696ea51a0ac6e7` built and was installed on
2026-09-24. `installed.json` records the exact system, previous preview, closure
delta and service observations. These are real board console and native PNG
captures, not camera/finger-motion evidence.

```sh
nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel --max-jobs 1 --cores 4 --no-link --print-out-paths
```

PASS system `/nix/store/25x0q5b2jxg4pgv53085xvszipsfzv5a-nixos-system-nixos-26.11.20260919.20b1ddd`.
Standalone Rust package `d7kq722kpixppyyy222siww0xlib0gzx` built separately;
the system's exact Rust package is `l8i7g4y9c18gm8l10m7a61cjbpgxvby4`, using its
NixOS Cairo/Pango/librsvg dependencies. Exact-image paired QEMU evidence is in
`../real-theme-paired-qemu/README.md`.

The operator held `/tmp/k230-board.lock` and the serial port. A 34-path,
146,163,312-byte delta imported with exit 0. A five-minute systemd fallback
to the previous preview was armed before `switch-to-configuration test`.
The activation returned 0, `/run/current-system` matched the target, and all
five listed services were active. Only then was the fallback timer stopped.
The original boot profile remains unchanged for reboot recovery.

The native captures use `swaymsg card_shell enter`, then the installed Rust
client's `--surface drawer`, and `grim` as the shell user with its existing
Wayland socket. Raw serial/transport logs remain private. Both PNGs were
visually reviewed before publication: they contain the packaged waves
wallpaper, actual installed app icons, and public terminal prompt content.

- [Live app deck](deck.png)
- [Installed app drawer](drawer.png)

This is visibly themed but not design acceptance. The user reported an awkward
shrink/expand during horizontal switching, mechanical release settling on
upward entry, and wallpaper exposed along the right edge. Board geometry
identified Foot's cell-rounded 564×1224 client on the 568×1232 output; a
separate pixel-size correction is in progress. The deck still has oversized
diagnostic titles and square letterboxed cards; the drawer remains a row list
with redundant helper entries and text showing through its authored alpha.
The visual audit and motion correction preserve these as open work.

Actual dark/light switching, fresh/reboot persistence, complete theme role
coverage, camera video and measured interaction budgets remain separate gates.
Do not infer those from these screenshots or the successful system activation.
