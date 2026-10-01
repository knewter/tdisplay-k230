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
  **PASS**: `/nix/store/q0zq2kivvqilcz12wswvwrwp9caa6a8j-portfolio-1.0.3-riscv64-unknown-linux-gnu`,
  closure 1.2 GiB (`nix path-info -Sh`). All 129 derivations built from
  source, no patches needed. On this shared, heavily contended build host
  (`uptime` showed load average ~46-52 against 32 cores throughout), wall
  clock was several hours; gtk4/libadwaita/GStreamer's own dependency graph
  (not portfolio-specific) is the bulk of it.
- [x] 2.3 Build `pkgsCross.riscv64.nautilus`. Verify with the same command
  form against the `nautilus` attribute. Launched after 2.2 reached its own
  gtk4/libadwaita derivations, so those were shared/reused rather than
  rebuilt (confirmed: no `building 'gtk4-riscv64...` or
  `'libadwaita-riscv64...` line reappears in nautilus-build.log). **PASS**:
  `/nix/store/2mrz6i0r38z0pjxxn451vc68sqr8lv7m-nautilus-riscv64-unknown-linux-gnu-50.2.2`,
  closure 1015.3 MiB (`nix path-info -Sh`) -- smaller than Portfolio's own
  1.2 GiB standalone number despite Nautilus's larger dependency *list*
  (tracker/localsearch/gnome-user-share/modemmanager), because Portfolio's
  own closure count already carries the full gtk4-pulled GStreamer/media
  stack that both share; Nautilus's marginal cost on top of that shared
  base is smaller than it looks from derivation counts alone.

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
  "Files (Portfolio)"); nnn's `nnn.desktop` "Files" entry unchanged at the
  time. Verify with: `nix-instantiate --parse nix/handheld-desktop-entries.nix`.
  **Superseded by task 6.1**: nnn's entry is since removed outright, not
  left unchanged.

## 5. System build and evidence

- [x] 5.1 Full system build, Portfolio only (`filesAppNautilus` defaults
  off; per coordinator direction, do not wait on Nautilus's own build for a
  testable system). Verify with:
  `nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel --max-jobs 1 --cores 6 --no-link --print-out-paths`.
  **PASS**: `/nix/store/jv44pdh4al448zfl7h33l87pl3n4wmbq-nixos-system-nixos-26.11.20260919.20b1ddd`.
  Closure delta against `origin/master` (292ee81624fd, `builtins.getFlake
  "git+file://<repo>?rev=..."`, same `k230-coherent-shell` configuration,
  no source changes otherwise), measured as an independent per-path
  `nix-store -q --size` sum over `nix-store -q --requisites` (not `nix
  path-info -rS`, per coordinator's request that these be cross-checked
  separately):
  | | requisite paths | summed size |
  | --- | ---: | ---: |
  | master baseline | 1041 | 3.196 GiB |
  | Portfolio-only system | 1114 | 3.576 GiB |
  | **delta** | **+73 net** (97 new, 24 superseded same-named rebuilds) | **+389.0 MiB (+0.380 GiB)** |
  The 24 superseded paths (`dbus-1`, `etc`, `foot`, this repo's own
  `k230-*`/`unit-*.service`/`system-path`/`system-units` derivations) are
  the same conceptual thing rebuilt with a new hash because the closure
  around them changed, not new weight. The 73 genuinely new packages are
  overwhelmingly GTK4's own default GStreamer media backend closure
  (libdvdnav/libdvdread/libdvdcss, libdc1394+libraw1394 FireWire camera,
  gupnp/gupnp-igd UPnP, webrtc-audio-processing, openh264, tinysparql,
  chromaprint, …) plus gtk4-riscv64, libadwaita-riscv64 and
  portfolio-1.0.3-riscv64 themselves -- confirming `design.md`'s "closure
  weight is intrinsic to GTK4 on this nixpkgs pin" note with an exact,
  itemized list rather than an estimate. See
  `docs/evidence/files-app/closure-delta.md`.
- [x] 5.1b Full system build, both candidates
  (`k230-coherent-shell-both-files-apps`, `filesAppNautilus = true`).
  Verify with the same command against that configuration. **PASS**:
  `/nix/store/b2f6yqk428w599jcc7w6rcjawld85bp6-nixos-system-nixos-26.11.20260919.20b1ddd`.
  Same per-path `nix-store -q --size` sum method:
  | | requisite paths | summed size |
  | --- | ---: | ---: |
  | master baseline | 1041 | 3.196 GiB |
  | Portfolio-only | 1114 | 3.576 GiB |
  | Both apps | 1154 | 3.704 GiB |
  | **Nautilus's own marginal delta** (both vs. Portfolio-only) | **+40 net** (54 new, 14 superseded) | **+130.4 MiB (+0.127 GiB)** |
  | **both apps vs. master** | **+113 net** | **+519.4 MiB (+0.507 GiB)** |
  Nautilus's marginal *byte* cost is much smaller than its own 1015.3 MiB
  standalone closure, because gtk4/libadwaita/GStreamer's bulk is already
  shared with Portfolio; what Nautilus adds on top is real, itemized
  dependency-surface growth rather than size: iOS/USB device sync
  (`libimobiledevice`+`libusbmuxd`+`libplist`+`libtatsu`), network
  directory sharing (`gnome-user-share`+`apache-httpd`+`mod_dnssd`),
  `localsearch`+`tinysparql` full-text indexing, `polkit`, LDAP
  (`openldap`+`cyrus-sasl`), PDF (`poppler-glib`/`poppler-data`,
  `libgxps`), image metadata (`gexiv2`/`exempi`), `libnotify`,
  `libcloudproviders`, `libosinfo`+`osinfo-db`, `gnome-autoar`,
  `gnome-desktop`, `nautilus-riscv64-unknown-linux-gnu-50.2.2` and
  `k230-nautilus` (this change's launcher) themselves. See
  `docs/evidence/files-app/closure-delta-both-apps.md`.
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
- [x] 5.3 Board evidence: both installed candidates launched and were exercised
  on the physical panel. Operator confirmed icons and scrolling work in both.
  Exact installed desktop-wrapper launches measured Portfolio 5.916 s / 74,388
  KiB RSS and Nautilus 3.461 s / 64,536 KiB RSS; both actual processes passed
  Wayland, cairo and application/adwaita/hicolor share environment checks.
  Original native captures plus the optical panel photograph, public console
  record, script, identities and measurement limits are committed in
  `docs/evidence/files-app/board-2026-09-30/README.md`. Repeatable board command
  is recorded there. These are warm-cache surface-map measurements, not
  first-frame latency or quantified scrolling FPS. Keep both by the existing
  operator decision; no further candidate selection remains.

## 6. Default both candidates, remove nnn's entry outright

- [x] 6.1 Operator decision recorded: keep both Portfolio and Nautilus
  installed and visible in the app drawer by default
  (`k230.shell.filesAppNautilus` default flipped from `false` to `true` in
  `nix/shell.nix`; `k230-coherent-shell-both-files-apps` in `flake.nix` is
  now identical to `k230-coherent-shell`, kept only so anything naming it by
  attribute still resolves), and remove nnn's old terminal "Files" entry
  outright rather than leave it as a fallback. Verify with:
  `grep -rn nnn nix/shell.nix nix/handheld-desktop-entries.nix` finding only
  historical/explanatory comments, no live wiring.
- [x] 6.2 Remove nnn's package/binary and desktop-entry wiring: `pkgs.nnn`
  dropped from `environment.systemPackages` and from
  `handheld-desktop-entries.nix`'s inputs, the `nnn.desktop` override
  deleted from `handheld-desktop-entries.nix`, and the compositor's
  hardcoded `"nnn" -> "Files"` card-title fallback removed from
  `nix/card-shell/adapter.c`. Add `GDK_BACKEND=wayland` and
  `adwaita-icon-theme`/`hicolor-icon-theme`/the app's own `share` to
  `mkFilesAppLauncher`'s `XDG_DATA_DIRS` in `nix/shell.nix` (operator-
  reported board fix for missing icons), in the Nix wrapper rather than
  hand-made files under `/home/shell`. Verify with:
  `nix-instantiate --parse nix/shell.nix nix/handheld-desktop-entries.nix
  flake.nix` and `nix flake check --no-build`.
- [x] 6.3 Update tests/specs that referenced nnn as the shipped "Files" app:
  `tests/test_card_shell_deck_title.py` (drop the `"nnn" -> "Files"` card
  title case), `tests/handheld_desktop_entries_probe.c` (drop `nnn.desktop`
  from the probed IDs), `tools/app_appearance.py` and
  `tests/test_handheld_app_themes.py` (drop `"nnn"` from the `"inherited"`
  theme-coverage list). Verify with:
  `python3 -m pytest tests/test_handheld_app_themes.py tests/test_theme_gtk.py tests/test_handheld_theme_default.py -q`
  and `gcc -Wall -Wextra -Werror tests/handheld_desktop_entries_probe.c -o /tmp/probe $(pkg-config --cflags --libs gio-unix-2.0)`.
  `tests/test_card_shell_deck_title.py` itself fails to compile on this
  host's GCC independent of this change (`desktop_identity_icon`: unused-
  function under `-Werror`, reproduced identically on the pre-edit
  commit) — not fixed here, out of this change's scope.
- [x] 6.4 Full system build proving the new default evaluates and builds.
  Verify with:
  `nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel --max-jobs 1 --cores 6 --no-link --print-out-paths`.
  **PASS**: `/nix/store/6m8avy8didrmf6c0znlhqw40l82dq5sz-nixos-system-nixos-26.11.20260919.20b1ddd`.
  Only 31 derivations needed building (the wrapper/desktop-entry/adapter.c
  and their dependents); the riscv64 `portfolio-filemanager`/`nautilus`
  packages themselves were unaffected by this task group's changes and did
  not need rebuilding. This is a host evaluation/build proof only, not
  board evidence — see 5.3.
- [x] 6.5 `openspec validate --all --strict` exits 0 after this task
  group's proposal/spec edits (owner: this change, checked directly, not
  through a pipe to `tail`). **PASS**: `Totals: 60 passed, 0 failed (60 items)`,
  exit code 0.
