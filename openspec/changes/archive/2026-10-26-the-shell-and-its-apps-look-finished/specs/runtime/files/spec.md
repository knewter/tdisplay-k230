## REMOVED Requirements

### Requirement: Two off-the-shelf touch-capable file managers are the handheld's only "Files" entries, installed by default

**Reason**: The operator decided on 2026-10-26 that the drawer lists one "Files" entry.

**Migration**: Replaced by "Nautilus is the handheld's one Files entry; Portfolio stays installed", which keeps both packages and the nnn removal.

## ADDED Requirements

### Requirement: Nautilus is the handheld's one Files entry; Portfolio stays installed

*Grounding: `docs/research/omarchy-quattro-theme-compatibility.md`'s pinned
Omarchy revision and this change's `install/omarchy-base.packages` read
confirm Nautilus is Omarchy's own shipped file manager. Portfolio
(`portfolio-filemanager`) is read directly from this flake's locked
nixpkgs `package.nix`. Cross-build feasibility is grounded in
`nix build --file nix/files-app-probe.nix ... --dry-run` output recorded
under `docs/evidence/files-app/`, not assumed. The decision to keep both by
default and remove nnn's old entry outright is an operator decision
recorded in this change's `design.md`/`tasks.md`, not a board measurement.
Showing only Nautilus in the drawer is the operator's 2026-10-26 decision
(`the-shell-and-its-apps-look-finished`).*

<!-- Grounding: the board drawer capture docs/evidence/shell-design-review/build-9kam3kq9/r2-drawer.png shows one "Files" entry; the operator accepted the build on glass on 2026-10-26 (docs/evidence/shell-design-review/operator-report.md). -->
The system SHALL install Nautilus and Portfolio, each cross-built for the
board's riscv64 target (`k230.shell.filesAppNautilus` defaults to `true`).
The drawer SHALL list Nautilus as the one "Files" entry; Portfolio SHALL
stay installed and launchable but SHALL NOT be listed. The system SHALL NOT
ship nnn's previous terminal "Files" entry, its package, or any launcher/
card-title wiring for it.

#### Scenario: One Files entry, nnn's old entry absent

- **WHEN** the installed-application drawer is opened on a default
  `coherentShell` build
- **THEN** exactly one "Files" entry is present, backed by Nautilus, and no
  "Files" entry backed by nnn or Portfolio is present
