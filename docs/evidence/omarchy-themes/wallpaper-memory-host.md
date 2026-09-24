# Per-theme wallpaper memory: host checkpoint

Observed 2026-09-23 from the `c92160d8` integration base. The optional
`background-selections.json` lives under the user's theme state directory,
outside every unchanged source checkout. Its keys hash canonical source paths;
its values are source-relative `backgrounds/NAME` entries rather than stale
generation store paths. The file is bounded to 64 KiB/256 choices, written
atomically with mode 0600, and rejects foreign symlinks and malformed data.

Omitting a background in either `omarchy-theme-set` or the JSON chooser reads
the remembered asset if it remains staged. An explicit asset wins, including
the theme's default image. If the remembered asset was removed in a source
update, preparation reports `remembered background removed; using theme
default`; this does not rewrite the preference during preview. The next
acknowledged activation records the fallback.

The preference guard and final write run under the same existing activation
flock as the `current/active` pointer swap. A shell commit ACK precedes the
memory write; a failed ACK preserves both prior pointer and preference. A
failed post-ACK preference write attempts restoration of the pointer, prior
preference bytes, and shell generation. A stale implicit preview whose source
preference changed while it waited for the lock is rejected for re-preview.
There is no claim that the physical panel presented or remembered an image.

```text
python3 tests/test_theme_preferences.py          PASS 9 host tests
python3 tests/test_theme_catalog.py              PASS 9 host tests
python3 tests/test_omarchy_theme_activation.py   PASS 9 host tests
python3 tests/test_omarchy_theme_transaction.py  PASS 13 host tests
openspec validate the-shell-loads-omarchy-themes --strict  PASS
```

Fixtures cover switch-away/back and a fresh process read, source update,
deleted asset fallback, preview/cancel, failed shell ACK, injected preference
write failure after replacement, cached-generation diagnostics, conflicting
concurrent activations, the
compatible command path, and an alien symlink. No Nix package build, reboot,
touch chooser, decode/cache/overlay/fit mode, or real-glass proof was run for
this checkpoint. OpenSpec task 4.1 and the physical tasks remain open.

The coordinator subsequently built the narrow command package from the landed
`99ac8e48` integration revision: `nix build .#handheld-theme-command --no-link`
PASS, output `/nix/store/xjncl4sgb4yb7asabpk41l051wncpi5b-handheld-theme-command-0.1`.
This proves the package evaluates and cross-builds; it does not prove a theme
switch, client repaint, wallpaper presentation, or persistence on the board.
