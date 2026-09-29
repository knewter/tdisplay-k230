## Why

The installed-application drawer's "Files" entry launches `nnn` inside a
Foot terminal (`nix/handheld-desktop-entries.nix`'s `nnn.desktop`). The user's
verbatim assessment: "the 'files' app is fuckin awful we need a great files
app" — with two more requirements in their own words: "it has to honor
themes" and "see what omarchyists use" (i.e. what Omarchy itself ships or
would recommend, not an invented alternative).

Reading Omarchy's own install package lists
(`install/omarchy-base.packages` at the pinned revision this repo already
tracks in `docs/research/omarchy-quattro-theme-compatibility.md`) shows
Omarchy ships `nautilus` and `nautilus-python`, plus `gvfs-mtp/nfs/smb`,
`sushi` (Nautilus's Quick Look), `gnome-disk-utility` and `udiskie`. There is
no `yazi`, `thunar`, `pcmanfm`, or `portfolio` package anywhere in either of
Omarchy's package lists. Omarchy's own theming for it
(`bin/omarchy-theme-set-gnome`, read at the same pin) is narrow: it only
flips `org.gnome.desktop.interface` `color-scheme` between
`prefer-dark`/`prefer-light` and switches `icon-theme` to the resolved
theme's Yaru variant (or a hardcoded `Yaru-blue` fallback) — it does **not**
recolor GTK/libadwaita with the resolved accent palette. Matching that scope
is feature parity with the reference implementation, not a shortfall.

A course correction during this change's own research reset its direction:
rather than building a new native Rust/Cairo Files app, first give existing,
maintained, touch-aware Linux file managers a genuine try on this hardware,
since at least one (Nautilus) is the literal thing "omarchyists" run.
[Portfolio](https://github.com/tchx84/Portfolio) — nixpkgs
`portfolio-filemanager` — is a second candidate: GTK4/libadwaita,
purpose-built for Linux phones (Librem 5, PinePhone), much smaller than
Nautilus (no tracker/localsearch/gvfs/modemmanager stack). Both are
evaluated here on their real cross-build cost and closure weight; the board
decides the rest, per `AGENTS.md`'s evidence-class rule ("a host build, QEMU
run, injected event, camera recording, and real glass interaction are
distinct evidence classes").

## What Changes

- Cross-build `pkgs.nautilus` (Omarchy's own choice) and
  `pkgs.portfolio-filemanager` (a phone-first alternative already in
  nixpkgs) for riscv64 and add both to the handheld's package set, each
  reachable from the drawer as a distinct "Files (Nautilus)" / "Files
  (Portfolio)" entry.
- **Operator decision (this pass):** keep both candidates installed and
  visible by default (`k230.shell.filesAppNautilus` now defaults to `true`,
  no longer gated), and remove nnn's old terminal "Files" entry outright —
  its package (`pkgs.nnn`), desktop entry (former `nnn.desktop`), launcher
  wiring, and the compositor's `"nnn" -> "Files"` card-title fallback are all
  deleted, not just superseded. This was previously deferred to the
  coordinator (see the superseded non-goal below); board launch-time/RSS/
  scroll comparison is unaffected and remains a separate, still-open
  hardware task (`tasks.md` 5.3).
- Launch both through a thin wrapper that sets `GSK_RENDERER=cairo` (so GTK4
  never attempts the GL scene renderer this Mesa-less board cannot provide),
  `GDK_BACKEND=wayland`, and an `XDG_DATA_DIRS` that includes the launched
  app's own `share`, `adwaita-icon-theme` and `hicolor-icon-theme` — matching
  operator-reported board behavior that icons were missing without the
  latter two, and keeping the fix in the Nix wrapper rather than hand-made
  files under `/home/shell`.
- **New:** a GTK/libadwaita appearance adapter
  (`tools/theme_gtk.py`, wired into the existing `tools/app_appearance.py`
  "app appearance" generation alongside its Foot adapter) that renders a
  GSettings keyfile-backend snippet — `color-scheme` and `icon-theme` under
  `org.gnome.desktop.interface` — from the same resolved theme generation
  Foot already reads, matching Omarchy's own `omarchy-theme-set-gnome`
  scope exactly (dark/light + icon variant, no accent-color recolor). Both
  apps' launcher wrapper links `~/.config/glib-2.0/settings/keyfile` to the
  active generation's rendered file before every launch, so a freshly
  launched instance always reflects the currently active theme; there is no
  `xdg-desktop-portal` on this image; the keyfile is read directly. Whether
  an *already-open* window picks up a later theme change live (the keyfile
  GSettings backend does watch its file) is explicitly marked
  `UNVERIFIED` below pending a board check.
- A pinned default GTK settings keyfile
  (`nix/handheld-theme-default/gtk-settings.keyfile`, generator/checker
  `tools/generate_default_gtk.py`, following the existing
  `generate_default_foot.py`/`generate_default_keyboard.py` pattern) so a
  fresh home has correct GTK appearance before any theme is ever explicitly
  activated.
- Unit tests for the new appearance adapter's rendering and validation
  (`tests/test_theme_gtk.py`) and its wiring into `app_appearance.py`
  (`tests/test_handheld_app_themes.py`).
- Evidence: cross-build logs/derivation counts, closure-size deltas for
  each candidate (and both together) against the current
  `k230-coherent-shell` toplevel, and host/QEMU screenshots of both apps
  under a dark and a light theme, recorded under
  `docs/evidence/files-app/`.

## Non-goals for this pass

- ~~**No board decision.** This change makes both candidates buildable,
  themed and drawer-launchable; it does not remove nnn's entry or declare a
  winner.~~ **Superseded:** the operator has since decided to keep both
  candidates by default and remove nnn's entry outright (see "What Changes"
  above); real launch-time/RSS/scroll numbers from the board remain a
  separate, still-open hardware task (`tasks.md` 5.3) and are not required
  to justify this removal.
- **No native Rust/Cairo Files app.** The course correction paused that
  work before any code was written for it; nothing here depends on it, and
  nothing needs undoing if it is never picked up.
- **No accent-color recolor.** Matching Omarchy's own dark/light + icon
  scope for now; a resolved-accent-color mapping (GNOME 47+
  `accent-color`) is a follow-up, not scoped here.
- **No thumbnailer/search-index service tuning.** Nautilus's `tinysparql`/
  `localsearch` runtime dependents are not started by this change (no
  systemd user service wiring); Nautilus falls back to plain directory
  reads without them. Documented as a known limitation, not solved here.
