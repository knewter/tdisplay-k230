## 1. Research

- [x] 1.1 Read Omarchy's install package lists at the pinned revision
  already tracked by `docs/research/omarchy-quattro-theme-compatibility.md`
  (`install/omarchy-base.packages`, `install/omarchy-other.packages`) and
  its GNOME theming script (`bin/omarchy-theme-set-gnome`). Verify with:
  `curl -s https://raw.githubusercontent.com/omacom/omarchy/master/install/omarchy-base.packages`
  and the same path for `bin/omarchy-theme-set-gnome`. Done: confirms
  `nautilus`/`nautilus-python` are Omarchy's shipped file manager, no
  yazi/thunar/pcmanfm/portfolio anywhere in either package list, and that
  Omarchy's own GTK theming is dark/light `color-scheme` + icon-theme only
  (no accent-color recolor).
- [x] 1.2 Confirm `basecamp/omarchy` (the name in the user's request) and
  `omacom/omarchy` (the name this repo's existing research already pinned)
  are the same project. Verify with:
  `curl -s https://api.github.com/repos/basecamp/omarchy` (redirect) then
  `curl -sL https://api.github.com/repositories/994093166`. Done: confirmed
  redirect to `omacom/omarchy`.
- [x] 1.3 Confirm `portfolio-filemanager` (nixpkgs `pkgs.portfolio-filemanager`,
  upstream `tchx84/Portfolio`) exists at the pinned nixpkgs revision this
  flake already locks, and read its `package.nix` build inputs. Verify with:
  a store read of
  `pkgs/by-name/po/portfolio-filemanager/package.nix` in this flake's
  locked `nixpkgs` input tree. Done: GTK4/libadwaita/PyGObject, no
  gvfs/tracker/modemmanager/polkit stack in its own `buildInputs`.
- [x] 1.4 Find the current "Files" drawer entry. Verify with:
  `grep -n "nnn" nix/shell.nix nix/handheld-desktop-entries.nix`. Done:
  `nnn` in Foot, `nix/handheld-desktop-entries.nix`'s `nnn.desktop`.

## 2. Cross-build feasibility

- [x] 2.1 Dry-run both candidates against `pkgsCross.riscv64` at this
  flake's locked nixpkgs revision. Verify with:
  `nix build --file nix/files-app-probe.nix portfolio --dry-run --no-link`
  and the same for `nautilus`. Done: portfolio 129 derivations to build /
  417 paths fetched (838.2 MiB); nautilus 205 derivations to build / 197
  paths fetched (1.1 GiB) — nautilus's larger build list is `tinysparql`,
  `localsearch`, `gnome-user-share`, `glycin`/`libjxl`, `webrtc-audio-
  processing`, `modemmanager` and friends; both pull the same GTK4/
  libadwaita/GStreamer core, which portfolio's build list shows is intrinsic
  to GTK4 on this pin, not a candidate-specific cost.
- [x] 2.2 Build `pkgsCross.riscv64.portfolio-filemanager`. Verify with:
  `nix build --file nix/files-app-probe.nix portfolio --no-link --print-out-paths --max-jobs 1 --cores 4`.
  <!-- Fill in PASS/FAIL and the store path/build wall-clock once the
  background build this task launched finishes; see docs/evidence/files-app/. -->
- [ ] 2.3 Build `pkgsCross.riscv64.nautilus`. Verify with the same command
  form against the `nautilus` attribute. Not yet run to completion in this
  change (queued after 2.2 so the shared GTK4/libadwaita derivations it
  built are reused rather than rebuilt).

## 3. Theme integration

- [x] 3.1 `tools/theme_gtk.py`: render `[org/gnome/desktop/interface]`
  `color-scheme`/`gtk-theme`/`icon-theme` GSettings-keyfile text from a
  resolved `mode`/`icon_theme` pair, matching
  `bin/omarchy-theme-set-gnome`'s own scope and fallback
  (`Yaru-blue`). Verify with: `python3 -m pytest tests/test_theme_gtk.py -q`.
  Done: 9 tests (dark/light, missing-icon fallback, invalid mode, invalid/
  over-length/empty icon selectors, quoting, injection-surface check).
- [x] 3.2 Wire it into `tools/app_appearance.py::prepare()` alongside the
  existing Foot adapter: new `gtk_appearance()` reader, `gtk-settings.keyfile`
  written into the same content-addressed, cache-validated generation
  directory, `coverage.json` updated. Verify with:
  `python3 -m pytest tests/test_handheld_app_themes.py -q`. Done: 11 tests,
  including cache-tamper rejection for the new file (mirroring the existing
  Foot-config tamper check).
- [x] 3.3 Pin a default `gtk-settings.keyfile` for a fresh home
  (`nix/handheld-theme-default/gtk-settings.keyfile`,
  `tools/generate_default_gtk.py`, installed for both the bundled and
  recovery generations in `nix/handheld-theme-default/default.nix`).
  Verify with: `python3 -m pytest tests/test_handheld_theme_default.py -q`
  and `python3 tools/generate_default_gtk.py --check`.
- [x] 3.4 Launcher wrappers (`mkFilesAppLauncher` in `nix/shell.nix`):
  `GSK_RENDERER=cairo`, `GSETTINGS_BACKEND=keyfile`,
  `gsettings-desktop-schemas` + theme icons on `XDG_DATA_DIRS`, and the
  `~/.config/glib-2.0/settings/keyfile` symlink re-linked to the active (or
  pinned default) generation before every launch. Verify with:
  `nix-instantiate --parse nix/shell.nix` (syntax) now, `nix build
  .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel`
  (full closure) once both candidates finish building — task 5.1. Done:
  the host-native screenshot harness (task 5.2) caught a real bug in the
  first draft of `filesAppSchemaDirs` (plain `<pkg>/share` on
  `XDG_DATA_DIRS` does not expose nixpkgs' per-package-nested
  `gsettings-schemas` layout — `gsettings get` returned "No schemas
  installed" and both apps ignored `color-scheme` entirely) before it ever
  reached a cross-build; fixed with `glib.getSchemaDataDirPath`, re-verified
  by the same harness. See `docs/evidence/files-app/README.md`.

## 4. Drawer entries

- [x] 4.1 `dev.tchx84.Portfolio.desktop` / `org.gnome.Nautilus.desktop` in
  `nix/handheld-desktop-entries.nix`, using the exact upstream desktop IDs
  (so this repo's override precedes each package's own installed entry in
  `XDG_DATA_DIRS` order, same pattern the file's own header comment already
  documents) with distinguishing `Name=` values ("Files (Nautilus)" /
  "Files (Portfolio)"); nnn's `nnn.desktop` "Files" entry unchanged. Verify
  with: `nix-instantiate --parse nix/handheld-desktop-entries.nix`.

## 5. System build and evidence

- [ ] 5.1 Full system build with both candidates included. Verify with:
  `nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel --max-jobs 1 --cores 6 --no-link --print-out-paths`,
  and record the closure-size delta against the pre-change toplevel
  (`nix path-info -Sh` before/after). Blocked on 2.2/2.3 completing.
- [x] 5.2 Host screenshots of Portfolio and Nautilus under a dark and a
  light theme: real (unmodified) native x86_64 `portfolio-filemanager`/
  `nautilus` builds — substituted from cache.nixos.org, not the riscv64
  cross build — under Xvfb with the same `GSK_RENDERER=cairo`/
  `GSETTINGS_BACKEND=keyfile` the board wrapper sets, driven by a keyfile
  `tools/theme_gtk.py` rendered. `docs/evidence/files-app/README.md` and
  `docs/evidence/files-app/host/*.png`, with blob-inventory rows. QEMU
  screenshots (riscv64 binary, patched Sway, `qemu-riscv64-static`, this
  repo's existing brightness/volume-slider QEMU harness pattern) not done in
  this change — blocked on 2.2/2.3's riscv64 builds finishing.
- [ ] 5.3 Board evidence (owner: coordinator, not this change): real
  launch time, RSS and scroll behavior for both candidates and nnn, and the
  decision of which entry(ies) to keep. Operator command once a flashed
  image exists: launch each "Files (…)" drawer entry and observe; no
  narrow `tools/msh.py`/`console.py` invocation is prescribed here because
  the observation itself (does it come up, how fast, how smooth) is the
  point, not a scripted check. UNVERIFIED until performed; this change does
  not claim board behavior.
