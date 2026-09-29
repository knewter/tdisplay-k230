# Files app candidates: host-native theming screenshots

## Evidence class

**Host-native, not board, not QEMU, not the riscv64 cross build.** This
captures the real x86_64-linux `pkgs.portfolio-filemanager` and
`pkgs.nautilus` packages (substituted unmodified from cache.nixos.org — no
patch, no override) running under Xvfb, with the exact runtime flags the
board's launcher wrapper (`nix/shell.nix`'s `mkFilesAppLauncher`) sets:
`GSK_RENDERER=cairo` and `GSETTINGS_BACKEND=keyfile` pointed at a keyfile
rendered by `tools/theme_gtk.py`. It proves the GSettings appearance
mechanism itself works against a real GTK4/libadwaita runtime. It does not
prove riscv64 cross-build correctness, Pixman/`cairo` renderer visual output
on this board's actual wlroots compositor, or anything about launch time,
memory, or touch behavior — those remain board tasks (`tasks.md` 5.3).

## Harness

```
xvfb-run -a -s "-screen 0 568x1000x24" dbus-run-session -- <app> <sample-dir>
```

with `HOME`/`XDG_CONFIG_HOME` pointed at a scratch directory containing
`.config/glib-2.0/settings/keyfile` (the file `tools/theme_gtk.py` renders),
`XDG_DATA_DIRS` covering `gsettings-desktop-schemas` and `yaru-theme`, then
`imagemagick`'s `import -window root` after an 8s settle. `dbus-run-session`
is only for this host harness's convenience (Nautilus's Tracker/GVfs calls
resolve faster with a session bus present); the board's own launcher does
not add one — see the "found and fixed" note below for why that is fine.

Sample directory: `Documents/`, `Pictures/` (empty dirs) plus `notes.txt`,
`photo.png`, `report.pdf` (empty files) — enough to exercise folder vs. file
icon rendering, not real content.

## What this run found and fixed

The first attempt used `${pkgs.gsettings-desktop-schemas}/share` on
`XDG_DATA_DIRS`. Both apps rendered identically regardless of the keyfile's
`color-scheme` (byte-identical `portfolio-dark.png`/`portfolio-light.png`
outputs), and `gsettings get org.gnome.desktop.interface color-scheme`
under the same environment returned `No schemas installed`. nixpkgs does
not install a package's compiled GSettings schema at `<pkg>/share/`; its
`glib` setup-hook installs each package's own `gschemas.compiled` under
`<pkg>/share/gsettings-schemas/<name>/glib-2.0/schemas/` specifically to
avoid cross-package collisions, and expects consumers to add
`<pkg>/share/gsettings-schemas/<name>` (not `<pkg>/share`) to
`XDG_DATA_DIRS`. Fixed by using nixpkgs' own passthru helper,
`glib.getSchemaDataDirPath`, in `nix/shell.nix`'s `filesAppSchemaDirs`
rather than a hand-built path. Re-running with the fix: `gsettings get`
correctly read back `'prefer-dark'`/`'Yaru-purple'`/`'Adwaita-dark'`, and
the four screenshots below are visibly distinct dark/light renders. This is
exactly the kind of bug host evidence is supposed to catch before a board
flash — see `portfolio-dark.png`/`portfolio-light.png` below for the
before/after (these four files are the *fixed* run; the broken run's
byte-identical pair was not committed).

## Screenshots

| File | Theme | App |
| --- | --- | --- |
| `host/portfolio-dark.png` | dark (`Yaru-purple`) | Portfolio |
| `host/portfolio-light.png` | light (`Yaru-olive`) | Portfolio |
| `host/nautilus-dark.png` | dark (`Yaru-purple`) | Nautilus |
| `host/nautilus-light.png` | light (`Yaru-olive`) | Nautilus |

Both apps: window chrome (headerbar, back/forward, search) renders and
reflows correctly at the board's 568px panel width. Dark/light switches the
whole surface (headerbar, list background, text color) in both apps. Mime
icons for the plain files (`notes.txt`, `photo.png`, `report.pdf`) show as
broken/generic icons in Portfolio — `shared-mime-info`'s icon-name database
was not on `XDG_DATA_DIRS` in this harness, a host-harness gap (not wired
into the board's launcher wrapper either yet) tracked as a follow-up, not a
theme-fidelity defect: the folder icons and the overall Yaru variant select
correctly.

## Not covered here

- riscv64 cross-build output (`docs/evidence/files-app/` has no cross-build
  screenshot yet; see `tasks.md` 2.2/2.3 for build status).
- The board's actual Pixman/`cairo`-renderer visual output, launch time, or
  RSS — coordinator task, `tasks.md` 5.3.
- Whether an already-open window picks up a later theme change live (see
  `design.md` decision 5; this harness only ever starts a fresh process per
  screenshot).
- `shared-mime-info` wiring for correct per-file-type icons.
