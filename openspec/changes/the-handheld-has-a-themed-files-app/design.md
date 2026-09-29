## Context

The handheld cross-compiles everything from x86_64-linux to riscv64-linux
with no binary cache for the target (`openspec/specs/image/cross-build`).
Every GUI package already installed renders through GTK3 Cairo/Pixman or a
plain terminal, chosen specifically because this board has no Mesa/EGL/GL
driver at all (`nix/shell.nix`'s comment above `zathuraApp`). GTK4 is new to
this image: its default GSK renderer wants a GL (or, failing that, an
`ngl`/Vulkan) context, none of which this board can provide.

The existing theme pipeline (`tools/theme_activate.py` → generation
directory with `report.json`/`colors.toml`/`icons.theme` →
`tools/theme_transaction.py::activate_generation` → an acknowledged
`app-appearance/active` symlink built by `tools/app_appearance.py::sync`)
already has exactly one installed-app adapter: Foot (terminal/monitor
configs plus opt-in OSC for the caller's own PTY). Its `coverage.json`
already documents what is and is not covered per generation. That adapter
is the natural place to add a second one rather than inventing a parallel
mechanism.

## Goals / Non-Goals

Goals: get real cross-build and closure evidence for both candidate file
managers; make both launch from the drawer without attempting GL, and with
their icons actually resolving; give both the same dark/light + icon-theme
fidelity Omarchy itself gives Nautilus; ship both installed and visible by
default, per the operator's decision, with nnn's old unusable "Files" entry
removed outright rather than left as a fallback.

Non-goals: recoloring GTK/libadwaita's accent color from the resolved
palette (Omarchy doesn't do this either); wiring gvfs/tracker/localsearch
services; a native Files app; narrowing to a single GTK4 candidate (both
stay installed — the board-measured launch-time/RSS/scroll comparison in
`tasks.md` 5.3 is still open, but it no longer gates keeping both or
removing nnn, which the operator has already decided).

## Decisions

### 1. Two candidates, not one, shipped side by side, nnn removed outright

The course correction was explicit: try existing touch-aware file managers
before building anything new, and let the board decide between Omarchy's
own choice (Nautilus) and a phone-first alternative already packaged in
nixpkgs (Portfolio). Both get a drawer entry with a distinguishing name
("Files (Nautilus)" / "Files (Portfolio)").

Originally nnn's plain "Files" entry was left untouched as a known-working
fallback while the other two were evaluated, with any entry removal deferred
to a follow-up once the coordinator had real launch-time/RSS/scroll numbers
from the board. The operator has since made that call directly: keep both
GTK4 candidates installed and visible by default
(`k230.shell.filesAppNautilus` now defaults to `true`), and remove nnn's
entry outright rather than keep it as a fallback — it launched inside a
terminal and was unusable on a touch handheld, so it was never a real
long-term candidate. Removed with it: `pkgs.nnn` from `environment.systemPackages`, its
`nnn.desktop` override, its `handheld-desktop-entries.nix` wiring, and the
compositor's hardcoded `"nnn" -> "Files"` card-title fallback
(`nix/card-shell/adapter.c`). The board-measured
launch-time/RSS/scroll comparison between Nautilus and Portfolio (`tasks.md`
5.3) remains open and unaffected by this decision.

### 2. `GSK_RENDERER=cairo` in a launcher wrapper, not a patched package

GTK4 supports selecting its scene-graph renderer via the `GSK_RENDERER`
environment variable; `cairo` is the software fallback that never touches
GL/EGL. Setting it in a thin `writeShellScriptBin` wrapper (mirroring the
existing `k230-foot`/`themedFoot` pattern) is a one-line, narrowly-scoped
fix — no patch to nixpkgs' `gtk4` or either app's own package, and no
rebuild cost beyond the wrapper derivation itself.

### 3. GSettings keyfile backend, not dconf

This image runs no `dconf` service and no `xdg-desktop-portal`. The
in-process `keyfile` `GSettingsBackend` (`GSETTINGS_BACKEND=keyfile`,
built into GLib, no extra package) reads
`$XDG_CONFIG_HOME/glib-2.0/settings/keyfile` directly — no D-Bus session,
no daemon, no portal implementation to install or keep alive. A session
D-Bus bus does exist on this image (`/run/shell-bus/bus`, `nix/shell.nix`),
but wiring dconf onto it would be strictly more moving parts for the same
two keys (`color-scheme`, `icon-theme`) this change actually needs.

The schema definition itself (`org.gnome.desktop.interface`) still has to
be discoverable regardless of backend: `pkgs.gsettings-desktop-schemas` is
a `buildInput` of nixpkgs' `nautilus` package already, but **not** of
`portfolio-filemanager`, and libadwaita itself only depends on it at
build/check time (`pkgs/by-name/li/libadwaita/package.nix`:
`gsettings-desktop-schemas` appears only in the `checkPhase` environment,
not `propagatedBuildInputs`). Both launcher wrappers add it to
`XDG_DATA_DIRS`/`GSETTINGS_SCHEMA_DIR` explicitly rather than relying on
either app's own transitive closure.

A naive `${pkgs.gsettings-desktop-schemas}/share` on `XDG_DATA_DIRS` is not
enough, and this change's host-native evidence harness
(`docs/evidence/files-app/README.md`) caught it directly: nixpkgs' `glib`
setup-hook installs each package's compiled schema under
`<pkg>/share/gsettings-schemas/<name>/glib-2.0/schemas/`, not
`<pkg>/share/glib-2.0/schemas/`, specifically so unrelated packages'
schemas never collide. With the naive path, `gsettings get
org.gnome.desktop.interface color-scheme` returned `No schemas installed`
and both apps silently ignored the keyfile's `color-scheme` entirely
(rendering light regardless of the keyfile). `nix/shell.nix`'s
`filesAppSchemaDirs` uses nixpkgs' own `glib.getSchemaDataDirPath` passthru
helper instead of a hand-built path, which is what libadwaita's own
`checkPhase` uses for the identical purpose.

### 4. The appearance adapter lives beside Foot's, in `app_appearance.py`

`tools/app_appearance.py::prepare()` already turns an acknowledged theme
generation into a content-addressed, cached `app-appearance/generations/
<id>/` directory (`terminal-foot.ini`, `monitor-foot.ini`, `coverage.json`),
published at `app-appearance/active` only after the shell's own commit
acknowledgement — the same fail-closed, no-partial-publish contract this
change's GTK output needs. Adding `gtk-settings.keyfile` to that same
directory (read via a new `gtk_appearance()` helper that independently
re-reads `report.json` for `mode`/`icon_theme`, since `palette()` only
returns ANSI colors) reuses that contract instead of building a second,
parallel activation path. The per-app launcher wrapper links
`~/.config/glib-2.0/settings/keyfile` to
`app-appearance/active/gtk-settings.keyfile` immediately before every
launch — cheap, idempotent, and correct even for a process started outside
the normal drawer flow.

### 5. Live re-theme of an already-open window is marked UNVERIFIED, not claimed

`GKeyfileSettingsBackend` does watch its backing file for changes and can
in principle notify an already-running process. Nothing in this change's
host/QEMU evidence can exercise "a GTK4 app stays open across a real theme
switch on this board" — that is a hardware observation
(`.skills/k230-spec-change/SKILL.md`'s evidence-order rule: an observation
on the board outranks anything documentation says should happen). The spec
delta marks this scenario `<!-- UNVERIFIED -->` rather than asserting it. A
fresh launch after any theme change is unconditionally correct by
construction (the wrapper re-links the symlink every time), so the feature
degrades to "correct on next open" in the worst case, never to a stale or
wrong theme.

### 6. Default keyfile is a pinned static file, not generated at NixOS build time

Every other per-generation default (`terminal-foot.ini`, `monitor-foot.ini`,
`wvkbd.args`) in `nix/handheld-theme-default/` is a committed static file,
regenerated and diff-checked by a small `tools/generate_default_*.py
--check` script rather than computed inside the Nix derivation. The new
`gtk-settings.keyfile` follows the same pattern
(`tools/generate_default_gtk.py`) for the same reason: it keeps the
derivation free of a native-vs-cross Python invocation, and keeps the
committed value auditable in a diff instead of opaque inside a build log.

### 7. `GDK_BACKEND=wayland` and the Adwaita/hicolor icon fallback chain, in the same wrapper

Board testing (performed by the operator, not reproduced by this worktree)
found icons missing from both apps unless two more things were set
explicitly: `GDK_BACKEND=wayland` (rather than letting GDK auto-detect,
which is otherwise fine under Sway but was the difference observed on the
board) and `XDG_DATA_DIRS` including `adwaita-icon-theme`'s and
`hicolor-icon-theme`'s own `share` directories alongside the launched app's
own `share`. Both symbolic-icon lookups (GTK4/libadwaita's own chrome:
toolbar buttons, "list-add", etc.) and the bundled Yaru theme's own
inheritance chain (`Inherits=...hicolor`/`Adwaita`) resolve through this
fallback, and none of the handheld's existing packages had previously
needed `adwaita-icon-theme`/`hicolor-icon-theme` on `XDG_DATA_DIRS` at all.
Fixed directly in `mkFilesAppLauncher` (`nix/shell.nix`) rather than as
hand-made files under `/home/shell`, per the operator's explicit direction,
so a fresh home never depends on anything not reproduced by the Nix build.
This repository's own board re-check of this specific fix is still
outstanding (`tasks.md` 5.3); it is recorded here as the operator's report,
not as evidence this worktree gathered itself.

## Risks / Trade-offs

- **Closure weight.** GTK4/libadwaita's own dependency graph pulls in
  GStreamer (GTK4's built-in `GtkMediaFile` backend), which is why even the
  smaller candidate (Portfolio) has a large riscv64 build list — this is
  intrinsic to GTK4 on this nixpkgs pin, not something either app's choice
  changes. See `tasks.md` for the measured derivation counts and, once the
  full system build finishes, the closure-size delta.
- **No thumbnailer/search index.** Nautilus without `tracker`/`localsearch`
  running falls back to synchronous directory reads; large directories may
  be slower to populate than on a full GNOME desktop. Untested on this
  board; flagged for the coordinator's scroll/large-directory check.
- **Two full candidates inflate the shipped image.** Both remain installed
  by default now, per the operator's decision — this is deliberate, not a
  placeholder pending narrowing.

## Deferred

- Accent-color mapping from the resolved palette (GNOME 47+/libadwaita 1.6
  `accent-color`), once it is confirmed to have any observable effect
  without a portal.
- gvfs/tracker/localsearch service wiring, if board evidence shows it is
  actually needed for acceptable directory-listing latency.
- Narrowing to a single GTK4 candidate, if the still-open board comparison
  (`tasks.md` 5.3) surfaces a decisive reason to drop one. Not expected by
  default now that both are the operator's chosen shipped state.
- The native Rust/Cairo Files app explored before the course correction:
  parked, not started, nothing to unwind.
