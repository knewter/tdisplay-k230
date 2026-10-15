## ADDED Requirements

### Requirement: Secondary click on empty Home space opens the Home menu

*Grounding: host test
`home_screen::tests::secondary_click_on_empty_home_space_opens_the_menu_but_not_on_an_icon`.*
<!-- UNVERIFIED: no board observation yet (task 1.2). -->

A secondary click on an empty, addressable Home cell SHALL open the same
Home menu that a long press on that space opens, under the same conditions.
It SHALL NOT open while that menu is already open, while rearranging, while a
folder is open, or while a drag or touch contact is active. A secondary click
on an app icon SHALL continue to open that app's menu.

#### Scenario: Right-click on empty space

- **WHEN** a person right-clicks (for example, a two-finger trackpad click)
  on an empty Home cell
- **THEN** the Home menu opens, the same as after a long press there

#### Scenario: Right-click on an app is unchanged

- **WHEN** a person right-clicks an app icon on Home
- **THEN** that app's menu opens and the Home menu does not
