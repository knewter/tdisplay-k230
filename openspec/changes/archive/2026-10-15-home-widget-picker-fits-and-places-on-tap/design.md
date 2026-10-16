## Context

`home_grid::picker_row_rect` stacked fixed 92 px rows with 14 px gaps from the
card's top. The Widgets page has one Back row plus one row per `WidgetKind`
(seven today). That is 20 + 7x92 + 6x14 = 748 px, but the card is 556 px tall
at 1280x800 and shorter on the 1232x568 landscape panel. Hit-testing and
painting share `picker_row_rect`, so the overflowing rows were drawn, but a
press on them failed the card test first and dismissed the sheet.

## Goals / Non-Goals

**Goals:** every row of every picker page inside the card at every surface;
a tap or click places a widget.

**Non-Goals:** scrolling the picker, or changing the drag path or the menu.

## Decisions

1. **One geometry for every page, sized for the longest.** `picker_grid`
   sizes rows for `WidgetKind::ALL.len() + 1`. Rows take the card's height
   up to 92 px, with the gap dropping to 8 px before rows go below 56 px.
   When one column would squeeze rows below 85 % of full height and the card
   is wide enough for two 360 px columns, the rows split into two columns.
   The portrait panel keeps one column at full size.
2. **Labels scale with the row.** The title and subtitle offsets and sizes
   scale by `row height / 92`, clamped to 0.6-1.0, and the subtitle is at
   least 11 px.
3. **Tap to place uses existing layout rules.** `HomeLayout::first_fit` on
   the page in view, else `place_first_fit`, the same placement path as
   pinning. It returns `HomeAction::LayoutChanged`, so the shell saves
   `home.json` as it does after a drop.
4. **Evidence.** Host tests cover rows inside the card at five surfaces
   (568x1232, 1232x568, 1280x800, 1280x720, 1920x1080), a tap placing a
   widget in portrait, and the last row at two landscape sizes. Host renders
   are in `docs/evidence/home-screen/widget-picker-fit/host/`. The board
   proof is a tap on a row on the HDMI monitor placing that widget.
