## Context

Layer: userspace, the Rust shell client (`nix/rust-shell-client`). The drawer's
`DrawerSearch` (`service_ui.rs`) holds the query; `filter_app_indices` returns
catalog indices, and `launch_drawer_app(display_index)` maps a display position
back to one (`main.rs`). The base-keys change makes LILYGO focus the search with
the on-screen keyboard down and makes Enter launch display position 0.

*Grounding: `service_ui.rs` `filter_app_indices` and `DrawerSearch::key_action`
read at cff47b1e; `catalog::scan_apps` caps the catalog at 128 entries;
`app_actions.rs` reads actions with `gio::DesktopAppInfo::list_actions`. The
Settings routes (`PanelIntent::OpenWifi`, `OpenCellular`, `OpenLocation`,
`OpenDateTime`, `OpenAbout`, `ToggleDoNotDisturb`, `ThemeIntent::OpenVision`)
were read in `service_ui.rs` and `main.rs`. No board observation of searching
Settings exists.*

## Decisions

- **One result type, one list.** `SearchResult { kind, label, detail, target }`
  with `target` one of `App(catalog_index)`, `Action(catalog_index, action_id)`
  or `Settings(SettingsDest)`. Painting, hit-testing and Enter all read the same
  vector, so the outlined first row is Enter's target by construction. The
  vector is recomputed per keystroke; the expensive part, painting, is at most
  a handful of rows and cheaper than the 39 ms grid scroll.
- **A list, not the grid, once a query exists.** The review's capture of the
  keyboard-up drawer shows about 1.5 grid rows left of 568 px
  (`panel-landscape/board/installed-keyboard-injected.png`), and mixed kinds do
  not fit an icon grid. The empty query keeps the grid and its cache untouched,
  so the idle drawer costs what it does today.
- **Settings is a static table.** Each entry has a label, a few keywords
  ("wifi", "wi-fi", "wireless"; "time", "clock", "date"; "brightness", "screen",
  "dim"; "dnd", "quiet", "silent"; "version", "build", "about") and a
  destination. Rows gated on hardware (Cellular, Location, Key backlight) are
  included only when the same condition the Settings screen uses is true, so a
  result never leads to a missing row.
- **Navigation only.** A Settings result opens Settings, scrolled so the row is
  in view for the inline controls, or the page for page destinations. It does
  not toggle Do Not Disturb or move a slider. Enter must not change state the
  person has not looked at.
- **The drawer hands off to Settings.** Settings and the drawer are separate
  routes today; the drawer closes and the existing settings entry (the one the
  shade uses) is invoked with a destination. UNVERIFIED how much of "open a
  given page" the existing surface request supports; task 2.2 may need a small
  destination argument on that request.
- **App actions from the scan.** Action names are copied into `AppEntry` when
  `scan_apps` already parses the desktop file, so a keystroke never opens a
  file. Activating one reuses `AppAction::Desktop(id)` from `app_actions.rs`.
- **Ranking.** Score 0 prefix of the label, 1 prefix of a later word, 2
  substring, 3 keyword prefix; lower first, then kind, then catalog order. It is
  a sort of at most about 150 elements.
- **Privacy by construction.** The sources are the catalog, the static table
  and action names. The notification broker, window tree and filesystem are not
  read, so no row can leak their contents. The query stays in `DrawerSearch`
  and is not logged.
- **Single CPU.** No thread, timer or cache is added. Everything runs on the
  existing dispatch path as the filter does now.
- **Conflicts.** The base-keys change modifies "Shell navigation works from the
  base's keys"; this change leaves that requirement alone and modifies only
  "The app drawer filters its grid by a live search query", so the two archive
  in either order.

## Rejected

- *A frecency boost and stored history.* A new on-disk file that a fresh home
  must not rely on (`openspec/config.yaml`), for a catalog small enough to
  scan by eye.
- *Searching running windows.* Titles can be private, and the overview exists.
- *Toggle results ("Do Not Disturb: on").* Enter on an accidental first match
  would change state; navigation is reversible.
- *A files index from `$HOME`.* It needs a scanner or inotify on one CPU and
  would put file names in a result list.
- *Grid plus a Settings strip underneath.* Two containers make "first match"
  ambiguous when the first app and first Settings hit tie.

## Risks

- Keywords are guessed. Mitigation: they are a table with tests, easy to extend.
- Row count past the viewport relies on the drawer scroll. UNVERIFIED on glass
  with the on-screen keyboard raised.

## Open questions

1. Should app actions ship at all? Few desktop entries on this image declare
   any (UNVERIFIED which; the design review asked for them). If none do, task
   1.3 shrinks to an empty source.
2. Which answer-type results come next: a calculator, "timer 5" or "run in
   terminal"? Each is its own proposal.
