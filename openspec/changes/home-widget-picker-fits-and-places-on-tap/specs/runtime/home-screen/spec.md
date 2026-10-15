## ADDED Requirements

### Requirement: The widget picker fits its card and places a widget on tap

*Grounding: host tests
`home_grid::tests::every_picker_row_sits_inside_the_card_at_every_surface`,
`home_screen::tests::a_plain_tap_on_a_widget_preview_places_it_and_closes_the_sheet`,
`home_screen::tests::a_tap_on_a_widget_row_works_on_landscape_surfaces_too`;
host renders `docs/evidence/home-screen/widget-picker-fit/host/`; the board
capture of the defect is
`docs/evidence/home-screen/widget-picker-fit/board/before-widget-rows-past-the-card-1280x800-grim.png`.*
<!-- UNVERIFIED: the fixed picker on the board (task 1.3). -->

Every row of every widget-picker page SHALL lie inside the picker card at
every supported surface size, using two columns and shorter rows where one
column does not fit. A tap or click on a widget row SHALL place that widget
at the first free spot it fits on the page in view, else on the first page
with room, close the sheet and save the layout. A press-and-hold on the row
SHALL still drag the widget instead.

#### Scenario: Landscape picker rows are pressable

- **WHEN** a person opens the Widgets page on a landscape surface and presses
  its last row
- **THEN** the press lands on that row inside the card, not outside it

#### Scenario: Tap adds a widget

- **WHEN** a person taps or clicks the Battery row
- **THEN** a Battery widget appears on Home and the sheet closes
