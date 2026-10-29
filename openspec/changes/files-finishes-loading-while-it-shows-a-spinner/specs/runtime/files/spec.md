## ADDED Requirements

### Requirement: Files finishes loading a folder while it is on screen

*Grounding (2026-10-29): on build `2867v7pm…`, Files showed "Loading…" for more than 300 s on a four-entry home folder while visible, and finished once hidden (`docs/evidence/files-app/slow-load/README.md`).*

<!-- UNVERIFIED: the patched build has not run on the board yet (files-finishes-loading-while-it-shows-a-spinner tasks 2.x). -->

When Files opens a local folder of a few entries on the panel, it SHALL show
the folder's contents while its window stays visible, without the person
hiding or switching away from the window. Once the folder has loaded, its
main thread SHALL go idle.

#### Scenario: Opening the home folder from the drawer

- **WHEN** a person opens Files from the drawer and it shows the home folder
- **THEN** the folder's entries appear while the window stays on screen, and
  the "Loading…" bar goes away

#### Scenario: Files at rest

- **WHEN** a folder has finished loading and nothing on screen is animating
- **THEN** Files uses no measurable CPU

### Requirement: An animating GTK4 window repaints only what changed

*Grounding (2026-10-29): `WAYLAND_DEBUG` showed every frame of a lone `AdwSpinner` window damaging the whole 1282×618 buffer while sway alternated two buffers. The cause was read in GTK 4.22.4 `gdk/wayland/gdkcairocontext-wayland.c` (`docs/evidence/files-app/slow-load/README.md`).*

<!-- UNVERIFIED: the patched build has not run on the board yet (files-finishes-loading-while-it-shows-a-spinner tasks 2.x). -->

A GTK4 app on the board, drawing with the software renderer, SHALL report
damage to the compositor only for the parts of its window that changed in
that frame, also when the compositor keeps its previous buffer until the
next commit.

#### Scenario: A spinner turns in an otherwise still window

- **WHEN** a GTK4 window shows only a turning spinner
- **THEN** after its first frames, each frame's damage covers the spinner's
  area rather than the whole window
