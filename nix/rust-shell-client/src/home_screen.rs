//! Home screen gesture state machine: wires `home_pager::HomePager`,
//! `home_grid`'s geometry, and `home_state::HomeLayout` into the single
//! touch-contact dispatch `main.rs` drives, mirroring how `navigation.rs`
//! and `theme_carousel.rs` are each driven today by one `down`/`motion`/
//! `up`/`tick` contact.

use crate::home_grid::{self, HomeSlot};
use crate::home_pager::{HomePager, LONG_PRESS_MS, TAP_SLOP};
use crate::home_state::HomeLayout;

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum HomeAction {
    /// Launch, or focus if already running, this desktop-entry id.
    Launch(String),
    /// The layout changed (pin/unpin/reorder/page move/remove); the caller
    /// should persist it (`home_state::save`).
    LayoutChanged,
}

#[derive(Clone, Copy, Debug)]
struct Contact {
    id: i32,
    start: (f64, f64),
    held_ms: u32,
    long_fired: bool,
    slot_at_down: Option<HomeSlot>,
}

/// How long an icon must be dragged against the pager's edge, while in
/// rearrange mode, before the page turns underneath it.
const EDGE_HOLD_MS: u32 = 550;
/// How close to the panel's left/right edge a rearrange drag must be to
/// count as "at the edge" for the page-turn-while-dragging behavior.
const EDGE_ZONE_PX: f64 = 32.0;

pub struct HomeScreen {
    pub layout: HomeLayout,
    pub pager: HomePager,
    pub rearranging: bool,
    /// The icon currently being dragged in rearrange mode, and its live
    /// finger position (for the renderer's floating drag preview).
    pub drag: Option<(HomeSlot, (f64, f64))>,
    contact: Option<Contact>,
    edge_held_ms: u32,
    edge_side: i8, // -1 left, 1 right, 0 neither
}

impl HomeScreen {
    pub fn new(layout: HomeLayout, page_width: f64) -> Self {
        let mut pager = HomePager::new(page_width);
        pager.set_page(0);
        Self {
            layout,
            pager,
            rearranging: false,
            drag: None,
            contact: None,
            edge_held_ms: 0,
            edge_side: 0,
        }
    }

    pub fn page_count(&self) -> usize {
        self.layout.page_count()
    }

    /// Any grid cell within the current page's bounds resolves to a slot,
    /// filled or not -- an empty cell is still a valid rearrange-mode drop
    /// target. Callers that only want an actual icon hit go through
    /// [`Self::filled_slot_at`] instead.
    fn slot_at(&self, point: (f64, f64), width: u32, height: u32) -> Option<HomeSlot> {
        if let Some(dock_slot) = home_grid::dock_slot_at(point, width, height) {
            return Some(HomeSlot::Dock { slot: dock_slot });
        }
        let page = self.pager.page(self.page_count());
        home_grid::slot_at(point, width, height, home_grid::apps_per_page(height))
            .map(|slot| HomeSlot::Grid { page, slot })
    }

    /// A slot only counts as an icon hit if it is actually filled --
    /// dragging or tapping empty grid space is not the same as touching a
    /// pinned icon.
    fn filled_slot_at(&self, point: (f64, f64), width: u32, height: u32) -> Option<HomeSlot> {
        self.slot_at(point, width, height)
            .filter(|slot| self.layout.get(*slot).is_some())
    }

    pub fn down(&mut self, id: i32, point: (f64, f64), time_ms: u32, width: u32, height: u32) {
        if self.contact.is_some() {
            self.cancel();
            return;
        }
        let slot_at_down = self.filled_slot_at(point, width, height);
        self.contact = Some(Contact {
            id,
            start: point,
            held_ms: 0,
            long_fired: false,
            slot_at_down,
        });
        if !self.rearranging {
            self.pager.down(point, time_ms);
        }
        let _ = time_ms;
    }

    pub fn motion(
        &mut self,
        id: i32,
        point: (f64, f64),
        time_ms: u32,
        width: u32,
        _height: u32,
    ) -> bool {
        let Some(contact) = self.contact.as_mut() else {
            return false;
        };
        if contact.id != id {
            return false;
        }
        if let Some((slot, _)) = self.drag {
            self.drag = Some((slot, point));
            self.edge_side = if point.0 < EDGE_ZONE_PX {
                -1
            } else if point.0 > f64::from(width) - EDGE_ZONE_PX {
                1
            } else {
                0
            };
            if self.edge_side == 0 {
                self.edge_held_ms = 0;
            }
            return true;
        }
        if (point.0 - contact.start.0).abs() > TAP_SLOP
            || (point.1 - contact.start.1).abs() > TAP_SLOP
        {
            contact.long_fired = true; // a real drag preempts a long-press
        }
        if self.rearranging {
            return false; // no page-swipe-by-empty-drag while rearranging
        }
        self.pager.motion(point, time_ms, self.page_count())
    }

    /// Advances the pager's momentum/settle animation and, while a finger
    /// rests without moving on a filled icon, the long-press timer. Returns
    /// whether a repaint is needed.
    pub fn tick(&mut self, elapsed_ms: u32) -> bool {
        let mut redraw = false;
        if !self.rearranging {
            redraw |= self.pager.tick(elapsed_ms, self.page_count());
        }
        if self.drag.is_some() && self.edge_side != 0 {
            self.edge_held_ms = self.edge_held_ms.saturating_add(elapsed_ms);
            if self.edge_held_ms >= EDGE_HOLD_MS {
                self.edge_held_ms = 0;
                let count = self.page_count();
                let current = self.pager.page(count);
                let next = if self.edge_side < 0 {
                    current.saturating_sub(1)
                } else {
                    (current + 1).min(count.saturating_sub(1))
                };
                if next != current {
                    self.pager.set_page(next);
                    redraw = true;
                }
            }
        }
        if let Some(contact) = self.contact.as_mut() {
            if !contact.long_fired && self.drag.is_none() && !self.pager.dragging() {
                contact.held_ms = contact.held_ms.saturating_add(elapsed_ms);
                if contact.held_ms >= LONG_PRESS_MS {
                    contact.long_fired = true;
                    if let Some(slot) = contact.slot_at_down {
                        self.rearranging = true;
                        self.drag = Some((slot, contact.start));
                        redraw = true;
                    }
                }
            }
        }
        redraw
    }

    pub fn up(
        &mut self,
        id: i32,
        point: (f64, f64),
        _time_ms: u32,
        width: u32,
        height: u32,
    ) -> Option<HomeAction> {
        let contact = self.contact.take()?;
        if contact.id != id {
            return None;
        }
        if let Some((slot, _)) = self.drag.take() {
            return Some(self.drop_dragged_icon(slot, point, width, height));
        }
        if self.pager.dragging() {
            self.pager.up(self.page_count());
            return None;
        }
        if self.rearranging {
            if home_grid::hits(point, home_grid::done_button_rect(width)) {
                self.rearranging = false;
                return None;
            }
            if self.filled_slot_at(point, width, height).is_some() {
                return None; // tapping another icon while rearranging is a no-op
            }
            self.rearranging = false; // tap on empty space exits, like both references
            return None;
        }
        self.filled_slot_at(point, width, height).and_then(|slot| {
            self.layout
                .get(slot)
                .map(|id| HomeAction::Launch(id.to_string()))
        })
    }

    fn drop_dragged_icon(
        &mut self,
        from: HomeSlot,
        point: (f64, f64),
        width: u32,
        height: u32,
    ) -> HomeAction {
        let apps_per_page = home_grid::apps_per_page(height);
        if home_grid::hits(point, home_grid::remove_target_rect(width)) {
            if let Some(id) = self.layout.get(from) {
                self.layout.remove_id(&id.to_string());
            }
            return HomeAction::LayoutChanged;
        }
        let Some(id) = self.layout.get(from).map(str::to_string) else {
            return HomeAction::LayoutChanged;
        };
        let target = self.slot_at(point, width, height).unwrap_or(from);
        if target != from {
            // Swap rather than overwrite, so dropping onto an occupied slot
            // never silently deletes the icon that was already there.
            let displaced = self.layout.get(target).map(str::to_string);
            self.layout.set(target, Some(id), apps_per_page);
            self.layout.set(from, displaced, apps_per_page);
        }
        HomeAction::LayoutChanged
    }

    pub fn cancel(&mut self) {
        self.contact = None;
        self.drag = None;
        self.edge_held_ms = 0;
        self.edge_side = 0;
        self.pager.cancel();
    }

    /// Which slot, if any, should show an immediate "pressed" highlight:
    /// the finger is down on a filled icon and hasn't started a page drag
    /// or a rearrange drag yet.
    pub fn pressed(&self, width: u32, height: u32) -> Option<HomeSlot> {
        let contact = self.contact.as_ref()?;
        if self.drag.is_some() || self.pager.dragging() {
            return None;
        }
        self.filled_slot_at(contact.start, width, height)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::home_state::HomeLayout as Layout;

    const WIDTH: u32 = 568;
    const HEIGHT: u32 = 1232;

    fn screen_with(dock: &[Option<&str>]) -> HomeScreen {
        let mut layout = Layout::default();
        layout.schema = crate::home_state::SCHEMA;
        layout.dock = dock.iter().map(|entry| entry.map(String::from)).collect();
        layout.pages = vec![vec![Some("a.desktop".into()), Some("b.desktop".into()), None, None]];
        HomeScreen::new(layout, WIDTH as f64)
    }

    #[test]
    fn tap_on_an_icon_launches_it() {
        let mut screen = screen_with(&[None; 4]);
        let (x, y, w, h) = home_grid::tile_rect(WIDTH, HEIGHT, 0);
        let point = (x + w / 2.0, y + h / 2.0);
        screen.down(1, point, 0, WIDTH, HEIGHT);
        assert_eq!(
            screen.up(1, point, 20, WIDTH, HEIGHT),
            Some(HomeAction::Launch("a.desktop".into()))
        );
    }

    #[test]
    fn tap_on_empty_grid_space_does_nothing() {
        let mut screen = screen_with(&[None; 4]);
        let (x, y, w, h) = home_grid::tile_rect(WIDTH, HEIGHT, 2); // unfilled slot
        let point = (x + w / 2.0, y + h / 2.0);
        screen.down(1, point, 0, WIDTH, HEIGHT);
        assert_eq!(screen.up(1, point, 20, WIDTH, HEIGHT), None);
    }

    #[test]
    fn long_press_on_an_icon_enters_rearrange_and_starts_dragging_it() {
        let mut screen = screen_with(&[None; 4]);
        let (x, y, w, h) = home_grid::tile_rect(WIDTH, HEIGHT, 0);
        let point = (x + w / 2.0, y + h / 2.0);
        screen.down(1, point, 0, WIDTH, HEIGHT);
        assert!(!screen.rearranging);
        let mut ticks = 0;
        while !screen.rearranging && ticks < 100 {
            screen.tick(16);
            ticks += 1;
        }
        assert!(screen.rearranging);
        assert!(screen.drag.is_some());
    }

    #[test]
    fn dragging_before_long_press_fires_pages_instead() {
        let mut screen = screen_with(&[None; 4]);
        let (x, y, _, _) = home_grid::tile_rect(WIDTH, HEIGHT, 0);
        let point = (x + 10.0, y + 10.0);
        screen.down(1, point, 0, WIDTH, HEIGHT);
        screen.motion(1, (point.0 - 400.0, point.1), 30, WIDTH, HEIGHT);
        screen.tick(16);
        assert!(!screen.rearranging, "a real drag must preempt the long-press timer");
        assert!(screen.pager.dragging());
    }

    #[test]
    fn drag_to_remove_target_unpins_without_uninstalling() {
        let mut screen = screen_with(&[None; 4]);
        let (x, y, w, h) = home_grid::tile_rect(WIDTH, HEIGHT, 0);
        let start = (x + w / 2.0, y + h / 2.0);
        screen.down(1, start, 0, WIDTH, HEIGHT);
        let mut ticks = 0;
        while !screen.rearranging && ticks < 100 {
            screen.tick(16);
            ticks += 1;
        }
        let remove = home_grid::remove_target_rect(WIDTH);
        let drop_point = (remove.0 + 4.0, remove.1 + 4.0);
        screen.motion(1, drop_point, 500, WIDTH, HEIGHT);
        assert_eq!(
            screen.up(1, drop_point, 520, WIDTH, HEIGHT),
            Some(HomeAction::LayoutChanged)
        );
        assert_eq!(screen.layout.get(HomeSlot::Grid { page: 0, slot: 0 }), None);
    }

    #[test]
    fn drag_swaps_with_the_target_slot_instead_of_overwriting() {
        let mut screen = screen_with(&[None; 4]);
        let (x0, y0, w, h) = home_grid::tile_rect(WIDTH, HEIGHT, 0);
        let start = (x0 + w / 2.0, y0 + h / 2.0);
        screen.down(1, start, 0, WIDTH, HEIGHT);
        let mut ticks = 0;
        while !screen.rearranging && ticks < 100 {
            screen.tick(16);
            ticks += 1;
        }
        let (x1, y1, w1, h1) = home_grid::tile_rect(WIDTH, HEIGHT, 1);
        let target = (x1 + w1 / 2.0, y1 + h1 / 2.0);
        screen.motion(1, target, 500, WIDTH, HEIGHT);
        assert_eq!(
            screen.up(1, target, 520, WIDTH, HEIGHT),
            Some(HomeAction::LayoutChanged)
        );
        assert_eq!(
            screen.layout.get(HomeSlot::Grid { page: 0, slot: 0 }),
            Some("b.desktop")
        );
        assert_eq!(
            screen.layout.get(HomeSlot::Grid { page: 0, slot: 1 }),
            Some("a.desktop")
        );
    }

    #[test]
    fn done_button_exits_rearrange_mode() {
        let mut screen = screen_with(&[None; 4]);
        screen.rearranging = true;
        let done = home_grid::done_button_rect(WIDTH);
        let point = (done.0 + 4.0, done.1 + 4.0);
        screen.down(1, point, 0, WIDTH, HEIGHT);
        screen.up(1, point, 20, WIDTH, HEIGHT);
        assert!(!screen.rearranging);
    }

    #[test]
    fn tap_on_empty_space_while_rearranging_exits_mode() {
        let mut screen = screen_with(&[None; 4]);
        screen.rearranging = true;
        let (x, y, w, h) = home_grid::tile_rect(WIDTH, HEIGHT, 2); // unfilled
        let point = (x + w / 2.0, y + h / 2.0);
        screen.down(1, point, 0, WIDTH, HEIGHT);
        screen.up(1, point, 20, WIDTH, HEIGHT);
        assert!(!screen.rearranging);
    }

    #[test]
    fn dock_tap_launches_the_dock_app() {
        let mut screen = screen_with(&[Some("dock.desktop"), None, None, None]);
        let (x, y, w, h) = home_grid::dock_rect(WIDTH, HEIGHT, 0);
        let point = (x + w / 2.0, y + h / 2.0);
        screen.down(1, point, 0, WIDTH, HEIGHT);
        assert_eq!(
            screen.up(1, point, 20, WIDTH, HEIGHT),
            Some(HomeAction::Launch("dock.desktop".into()))
        );
    }

    #[test]
    fn second_contact_cancels_the_first_without_a_stray_action() {
        let mut screen = screen_with(&[None; 4]);
        let (x, y, w, h) = home_grid::tile_rect(WIDTH, HEIGHT, 0);
        let point = (x + w / 2.0, y + h / 2.0);
        screen.down(1, point, 0, WIDTH, HEIGHT);
        screen.down(2, (10.0, 10.0), 5, WIDTH, HEIGHT);
        assert_eq!(screen.up(1, point, 20, WIDTH, HEIGHT), None);
    }
}
