## 1. Picker fits and places on tap

- [x] 1.1 Picker rows fit the card at every surface: two columns and smaller
      rows where needed, with labels scaled. Host test
      `home_grid::tests::every_picker_row_sits_inside_the_card_at_every_surface`;
      renders in `docs/evidence/home-screen/widget-picker-fit/host/`.
- [x] 1.2 A tap on a widget row places it and closes the sheet. Host tests
      `home_screen::tests::a_plain_tap_on_a_widget_preview_places_it_and_closes_the_sheet`
      and `a_tap_on_a_widget_row_works_on_landscape_surfaces_too`
      (`cargo test --lib`, 516 passed, 2026-10-15).
- [ ] 1.3 Board: on the HDMI monitor, every Widgets-page row is inside the
      card, and a click on the Battery row places a Battery widget on Home.
