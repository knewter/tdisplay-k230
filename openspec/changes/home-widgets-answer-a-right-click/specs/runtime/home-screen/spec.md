## ADDED Requirements

### Requirement: Home widgets can be moved and removed with a mouse

*Grounding: <!-- UNVERIFIED --> until tasks 1.1, 1.2 and 2.1 are recorded.*

A secondary click on a Home widget SHALL enter rearrange mode without picking
the widget up and without opening any menu. It SHALL NOT do so while the Home
menu or a folder is open, while already rearranging, or while a drag or touch
contact is active. In rearrange mode every widget SHALL show a remove badge at
its top-left corner, and a click on that badge SHALL remove the widget. A
press and drag on a widget in rearrange mode SHALL move it, as for icons.

#### Scenario: Right-click a widget

- **WHEN** a person right-clicks (for example, a two-finger trackpad click) on
  a Home widget
- **THEN** Home enters rearrange mode and nothing is picked up or removed

#### Scenario: Remove a widget with its badge

- **WHEN** Home is in rearrange mode and a person clicks a widget's remove
  badge
- **THEN** that widget is removed from Home

#### Scenario: Move a widget with the mouse

- **WHEN** Home is in rearrange mode and a person presses on a widget and
  drags it to another free area
- **THEN** the widget moves there
