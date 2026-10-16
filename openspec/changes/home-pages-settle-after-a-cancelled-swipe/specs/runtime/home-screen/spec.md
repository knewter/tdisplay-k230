## ADDED Requirements

### Requirement: Home always comes to rest on a whole page that exists

*Grounding: host tests in `home_pager` and `home_screen`; on-board behaviour
is <!-- UNVERIFIED --> until tasks 2.1 and 2.2 are recorded.*

When a page drag ends without a release, for example a two-finger trackpad pan
the shell cancels, Home SHALL settle to the nearest page rather than stop
between two. When the number of pages shrinks so that the page in view no
longer exists, Home SHALL settle onto the last page that does, including in
rearrange mode. At rest, what Home paints and where a press lands SHALL
always refer to the same page.

#### Scenario: Cancelled trackpad pan

- **WHEN** a two-finger trackpad pan moves Home partway between pages and the
  shell cancels it
- **THEN** Home settles to the nearest page, and a press on a widget shown
  there acts on that widget

#### Scenario: Last page emptied

- **WHEN** the only item on the last page is removed
- **THEN** Home settles onto the previous page and its page dots reflect the
  new count
