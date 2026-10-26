## Why

A review of fresh grim captures of every shell surface and every drawer app
(2026-10-26, landscape, `dwdcnvqb`) found things that are broken and things
that look unfinished. The operator asked for all of it to be fixed.

What a person runs into today:

- **Broken.**
  - Viewnior never opens; tapping it does nothing.
  - btop opens to "Terminal size too small".
  - Scrolled Settings cuts card text in half under the section header.
  - The background chooser shows a cut-off fragment at the output edge.
  - The drawer leaves a 32 px band at the top through which the app shows.
  - Tapping the overview's "Home · tap or swipe up" cue only goes Home in
    the middle of the bottom edge.
  - Overview cards for the terminal show a letter instead of the app icon.
- **Unfinished.**
  - Six games share one generic gamepad icon; Clock and Timer share one too.
  - Two file managers are listed as "Files (Nautilus)" and
    "Files (Portfolio)".
  - Clock, Timer and Weather are bare text in a terminal's top-left corner,
    and every terminal-launched app's card is titled "Terminal".
  - GTK3 apps (the puzzles, Galculator, Viewnior) ignore the theme: grey
    default widgets, tiny menus and buttons.
  - Nautilus and Portfolio show minimise and maximise buttons that do
    nothing here.
  - Home's dock packs its icons to the left, the Battery – Details widget
    reports zero readings as data, and the weather glyph overlaps the
    temperature.
  - The shade repeats "0 notifications" beside "No new notifications" and
    shows battery as "100% - Full".
  - Settings shows raw state ("link-up"), jargon ("Session preference"),
    a truncated audio subtitle and a whole row for two links.

## What Changes

- **Drawer:** the sheet covers the output from the top edge; Help matches
  the search field's height and shape; tile labels use a lighter weight.
- **Apps:**
  - Viewnior runs on Wayland.
  - btop opens at a size it accepts.
  - Every game, Clock and Timer gets an icon of its own.
  - Clock, Timer and Weather become full-screen touch apps with large type.
    Timer gets tappable controls; Weather shows current conditions and
    hours from the same wttr.in data as the Home widget.
  - Terminal-launched apps get their own app id, so their cards show their
    own name and icon.
- **Files:** Nautilus is the one "Files" entry. Portfolio stays installed
  but is hidden from the drawer.
- **GTK theming:** the appearance adapter also themes GTK3 apps (colours,
  type size, touch-sized controls). GTK3 and GTK4 apps show only a close
  button.
- **Shade:**
  - The count line is drawn only when there are notifications.
  - The empty state is centred in the list column.
  - Battery text reads "100% · Full".
  - The keyboard tile says what it does.
- **Settings:**
  - Vision and Themes move into the title row.
  - The scrolled body is clipped below a divider with a short fade.
  - Values read as words: Wi-Fi "Connected", Motion as "Reduce motion".
  - The audio output name is shown without the "tap to change" suffix.
  - Vision's Text size card keeps its flat group tint: that treatment is
    the shell's visual language for a container of choices, not a defect.
- **Themes:** carousel columns fade at their edges instead of cutting a
  neighbour's thumbnail at the output edge.
- **Home:**
  - A dock packed against its start is centred once; after that the
    person's arrangement stands.
  - Battery – Details omits readings the gauge reports as zero while the
    battery is full and idle, and states "On charger".
  - Weather keeps the temperature clear of the glyph.
- **Overview:**
  - The compositor reads the same desktop entries as the launcher, so cards
    show app icons.
  - A plain tap anywhere on the overview's bottom band outside the cards
    goes Home.

Non-goals:

- Re-theming third-party icons, or restyling apps beyond GTK theming.
- Changing gestures, motion, or the card layout.
- Removing Portfolio from the image.
- Moving items in an existing saved Home layout, beyond centring a packed
  dock once.
- Omawrite's start-up time: it is an external input and only measured here.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `runtime/app-launcher`: drawer sheet and chrome; every entry opens and has
  its own icon.
- `runtime/files`: one "Files" entry instead of two.
- `runtime/notification-center`: shade header and empty state.
- `runtime/device-settings`: Settings header, scroll clipping and wording.
- `runtime/shell-themes`: GTK3 app theming; window buttons; carousel edges.
- `runtime/home-screen`: dock centring, Battery – Details, Weather layout.
- `runtime/card-shell`: overview card icons; the footer cue's tap.
- `runtime/shell`: Clock, Timer and Weather apps; app ids for terminal apps.

## Impact

- `nix/rust-shell-client/src/` (render, navigation, service_ui, home_grid,
  home_widgets, theme carousel).
- `nix/card-shell/adapter.c`.
- `nix/shell.nix`, `nix/handheld-desktop-entries.nix`, new icons and the
  terminal-app script under `nix/`.
- `tools/device_settings.py`, `tools/app_appearance.py`, `tools/theme_gtk.py`
  and the generated defaults.

Needs the physical board: proof is native grim captures of each surface and
app on the board, plus the operator's look on glass. Host tests and renders
come first.
