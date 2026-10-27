## MODIFIED Requirements

### Requirement: The app drawer filters its grid by a live search query

<!-- UNVERIFIED: ranking, the result list and Enter's target are specified from source read at cff47b1e. No board run has typed a Settings or action query yet (the-drawer-search-finds-settings-and-app-actions tasks 3 and 4). -->
*Grounding: `docs/design/app-drawer-review.md` section 2.4 and the system-keyboard path in `docs/evidence/app-drawer/system-keyboard-board/README.md` ground the field and its keyboard. `service_ui::filter_app_indices` and `app_actions.rs` were read for the sources; `docs/design/shell-ux-review-webos-firefoxos-2026-10.md` gap 2 is the reason for widening them.*

The app drawer SHALL present a tappable search field above its icon grid. While the field is empty the drawer SHALL show the full grid. Once it holds text the drawer SHALL replace the grid with a ranked list of results, updated with each keystroke and matched without regard to letter case. Results SHALL come only from the installed applications, the desktop-entry actions of those applications, and the Settings destinations the Settings screen currently offers; a destination for hardware that is absent SHALL NOT appear. Names that start with the text SHALL rank before names with a later word that starts with it, before names that merely contain it. Each row SHALL be at least 99 pixels tall. Choosing an application SHALL launch the same application the unfiltered grid would, choosing an action SHALL run that action, and choosing a Settings destination SHALL open Settings on it without changing any setting. The first result SHALL be outlined, and Enter from the base's keys SHALL choose exactly that result. Clearing the field SHALL restore the full grid.

#### Scenario: Typing a search query filters the grid live

- **WHEN** a person types part of an application's name, in either case
- **THEN** the list shows that application, matching names first, updating with each keystroke

#### Scenario: A filtered result launches the correct application

- **WHEN** a person chooses an application result while a query is active
- **THEN** the same application that name identifies launches, exactly as if it had been tapped in the unfiltered grid

#### Scenario: A Settings destination is found by name

- **WHEN** a person types `wifi`
- **THEN** a Wi-Fi Settings result is listed, and choosing it opens the Wi-Fi page

#### Scenario: Nothing changes state

- **WHEN** a person types `do not disturb` and chooses the result
- **THEN** Settings opens and Do Not Disturb keeps the value it had

#### Scenario: Absent hardware is not offered

- **WHEN** the modem has not answered and a person types `location`
- **THEN** no Location result is listed

#### Scenario: Enter chooses the outlined result

- **WHEN** a person presses LILYGO, types `about` and presses Enter
- **THEN** the first outlined result, About, opens

#### Scenario: Results never carry private content

- **WHEN** a notification, window title or file name contains the typed text
- **THEN** no result shows it

#### Scenario: Clearing the search restores the full grid

- **WHEN** a person clears the search field's text
- **THEN** every installed application reappears in the grid
