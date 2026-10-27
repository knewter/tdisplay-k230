## Why

A person who types in the drawer can only find an app by its name. Someone who
wants the Wi-Fi page, the About page or Do Not Disturb has to remember that
those live behind the shade's "Settings >" row, pull the shade down and scroll
Settings. webOS's Just Type and Firefox OS's Rocketbar answered the same typing
with apps, settings and actions (gap 2 of
`docs/design/shell-ux-review-webos-firefoxos-2026-10.md`). With the base's keys
(`the-base-keys-launch-apps-and-drive-the-overview`) a person can already press
LILYGO, type and press Enter without touching the glass; today that only ever
reaches an app.

## What Changes

- Typing in the drawer search shows a short ranked results list instead of the
  filtered icon grid. An empty query still shows the full grid, unchanged.
- Three kinds of result, all from data the shell already holds or can name at
  build time:
  - **Apps**: the existing catalog, matched on name as now.
  - **Settings**: a fixed table of the destinations that exist today: Wi-Fi,
    Cellular and Location (only when the modem is present), Date & time,
    About, Themes, Vision, Do Not Disturb, Brightness, Volume, Keyboard,
    Reduce motion and Key backlight (only when the base has it). Choosing one
    opens Settings on that page, or Settings itself for the inline controls.
    It never flips a switch or sets a value.
  - **App actions**: the desktop-entry actions (`Actions=` / `[Desktop
    Action ...]`) that the app menu already lists, shown as "Action -
    App" and read once from the catalog scan.
- Ranking is prefix, then word start, then substring, case-insensitive; ties
  keep the order Apps, App actions, Settings, then catalog order. No
  frecency, no stored history.
- The first result carries the same outline the base-keys change gave the first
  app, and Enter launches or opens exactly that row, so the target is always
  the one drawn first.
- Every row is at least 99 px tall. Rows beyond the viewport scroll with the
  drawer's existing scroll.
- No result carries notification text, a window title, a file name, an SSID or
  a person's data, and the typed query is never written to the shell log.

## Non-goals

- No calculator, timer or weather answer, no "run in terminal", no web search
  and no file-name index. Each needs a new source or service; they are named
  follow-ups (design.md, open question 2) and not built here.
- No background indexer, cache on disk or new daemon. The single online CPU
  does one linear pass over at most about 150 short strings per keystroke.
- No type-to-search from Home or Overview (gap 2's first item). The drawer, as
  entered by touch or LILYGO, is the only surface.
- No results for running windows, because their titles can be private
  (`k230_card_private`) and the overview already lists them.
- No power actions as results.

## Capabilities

### Modified Capabilities

- `runtime/shell`: the drawer search matches more than apps, and Enter acts on
  the first of those results.
- `runtime/device-settings`: Settings destinations are reachable by name.

## Impact

- `nix/rust-shell-client/src/service_ui.rs` (`filter_app_indices` becomes a
  `search` module with a result type, ranking and the Settings table),
  `src/main.rs` (activating a Settings or action result from the drawer),
  `src/render.rs` (list rows and the first-row outline),
  `src/catalog.rs` / `src/app_actions.rs` (action names kept from the scan).
- No change to Nix, the compositor, the on-screen keyboard or Settings itself.

Host-verifiable for ranking, rows and hit-testing. It needs the physical board
for the injected-key run and the glass check (tasks 3 and 4). It builds on
`the-base-keys-launch-apps-and-drive-the-overview`, which supplies the focus
and the Enter-launches-first behaviour this change generalises.
