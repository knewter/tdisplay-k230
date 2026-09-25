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
            // Already in rearrange mode: no fresh long-press timer is
            // needed (a grab below, or a plain tap, decides this touch),
            // so mark the long-press as already "used" up front.
            long_fired: self.rearranging,
            slot_at_down,
        });
        if self.rearranging {
            // A fresh touch on any filled icon grabs it immediately,
            // exactly as real launchers' own "jiggle mode" lets any icon
            // be picked up without holding again. Touching empty space, or
            // a non-drag tap on an icon, is resolved at `up` instead.
            if let Some(slot) = slot_at_down {
                self.drag = Some((slot, point));
            }
        } else {
            self.pager.down(point, time_ms);
        }
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
            return self.drop_dragged_icon(slot, point, width, height);
        }
        if self.pager.dragging() {
            self.pager.up(self.page_count());
            return None;
        }
        if self.rearranging {
            // A touch on a filled icon always armed `self.drag` immediately
            // in `down` (above), so reaching here with `self.rearranging`
            // still true means this touch started on empty space or the
            // Done pill -- either way, exit rearrange mode, matching both
            // reference launchers' "tap elsewhere to stop jiggling".
            self.rearranging = false;
            return None;
        }
        self.filled_slot_at(point, width, height).and_then(|slot| {
            self.layout
                .get(slot)
                .map(|id| HomeAction::Launch(id.to_string()))
        })
    }

    /// `None` when the drop changed nothing (a plain tap-release on an
    /// already-grabbed icon, with no actual move) -- the caller then skips
    /// persisting, so tapping icons while rearranging does not write to
    /// disk on every touch.
    fn drop_dragged_icon(
        &mut self,
        from: HomeSlot,
        point: (f64, f64),
        width: u32,
        height: u32,
    ) -> Option<HomeAction> {
        let apps_per_page = home_grid::apps_per_page(height);
        if home_grid::hits(point, home_grid::remove_target_rect(width)) {
            let id = self.layout.get(from)?.to_string();
            self.layout.remove_id(&id);
            return Some(HomeAction::LayoutChanged);
        }
        let id = self.layout.get(from)?.to_string();
        let target = self.slot_at(point, width, height).unwrap_or(from);
        if target == from {
            return None;
        }
        // Swap rather than overwrite, so dropping onto an occupied slot
        // never silently deletes the icon that was already there.
        let displaced = self.layout.get(target).map(str::to_string);
        self.layout.set(target, Some(id), apps_per_page);
        self.layout.set(from, displaced, apps_per_page);
        Some(HomeAction::LayoutChanged)
    }

    pub fn cancel(&mut self) {
        self.contact = None;
        self.drag = None;
        self.edge_held_ms = 0;
        self.edge_side = 0;
        self.pager.cancel();
    }

    /// True while the pager is coasting/settling, or a rearrange drag is
    /// held near a page edge accumulating toward an auto-page-turn -- the
    /// caller should poll at the fast tick rate in either case rather than
    /// waiting for the next Wayland event.
    pub fn is_animating(&self) -> bool {
        self.pager.is_animating() || (self.drag.is_some() && self.edge_side != 0)
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

/// Best-effort match between a running Sway container's `app_id` and a
/// desktop-entry id (or its `Exec` binary's basename, as a fallback hint).
/// See `design.md` decision 6: no stable desktop-entry-id-to-`app_id`
/// mapping exists in this stack, so this is a heuristic a caller falls back
/// from on any miss, never treated as authoritative.
pub fn app_id_matches(app_id: &str, entry_id: &str, exec_hint: Option<&str>) -> bool {
    let normalized_entry = entry_id.strip_suffix(".desktop").unwrap_or(entry_id).to_lowercase();
    let app_id_lower = app_id.to_lowercase();
    if app_id_lower == normalized_entry {
        return true;
    }
    exec_hint.is_some_and(|hint| !hint.is_empty() && app_id_lower == hint.to_lowercase())
}

/// Walks an already-parsed `swaymsg -t get_tree` JSON tree for the first
/// container whose `app_id` matches `entry_id`/`exec_hint`
/// ([`app_id_matches`]), returning its `id` (for a `[con_id=...] focus`
/// command). Mirrors `tools/notification_center.py`'s own `get_tree` walk:
/// a bounded node budget, not just recursion, so a malformed or huge tree
/// cannot hang this call.
pub fn find_running_con_id(
    tree: &serde_json::Value,
    entry_id: &str,
    exec_hint: Option<&str>,
) -> Option<i64> {
    let mut pending = vec![tree];
    let mut budget = 4096;
    while let Some(node) = pending.pop() {
        if budget == 0 {
            break;
        }
        budget -= 1;
        let Some(object) = node.as_object() else {
            continue;
        };
        if object.get("type").and_then(|value| value.as_str()) == Some("con") {
            if let Some(app_id) = object.get("app_id").and_then(|value| value.as_str()) {
                if app_id_matches(app_id, entry_id, exec_hint) {
                    return object.get("id").and_then(|value| value.as_i64());
                }
            }
        }
        if let Some(nodes) = object.get("nodes").and_then(|value| value.as_array()) {
            pending.extend(nodes);
        }
        if let Some(nodes) = object.get("floating_nodes").and_then(|value| value.as_array()) {
            pending.extend(nodes);
        }
    }
    None
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
    fn already_rearranging_a_fresh_drag_moves_an_icon_without_a_second_long_press() {
        let mut screen = screen_with(&[None; 4]);
        screen.rearranging = true;
        let (x0, y0, w, h) = home_grid::tile_rect(WIDTH, HEIGHT, 0);
        let start = (x0 + w / 2.0, y0 + h / 2.0);
        let (x1, y1, w1, h1) = home_grid::tile_rect(WIDTH, HEIGHT, 1);
        let target = (x1 + w1 / 2.0, y1 + h1 / 2.0);
        screen.down(1, start, 0, WIDTH, HEIGHT);
        assert!(screen.drag.is_some(), "a filled icon is grabbed immediately while rearranging");
        screen.motion(1, target, 20, WIDTH, HEIGHT);
        assert_eq!(
            screen.up(1, target, 40, WIDTH, HEIGHT),
            Some(HomeAction::LayoutChanged)
        );
        assert_eq!(screen.layout.get(HomeSlot::Grid { page: 0, slot: 1 }), Some("a.desktop"));
        assert!(screen.rearranging, "still rearranging after one successful move");
    }

    #[test]
    fn a_plain_tap_release_while_rearranging_does_not_persist() {
        let mut screen = screen_with(&[None; 4]);
        screen.rearranging = true;
        let point = tile_center_for_test(0);
        screen.down(1, point, 0, WIDTH, HEIGHT);
        assert_eq!(screen.up(1, point, 20, WIDTH, HEIGHT), None);
        assert!(screen.rearranging, "a tap on the grabbed icon itself does not exit rearrange mode");
        assert_eq!(screen.layout.get(HomeSlot::Grid { page: 0, slot: 0 }), Some("a.desktop"));
    }

    fn tile_center_for_test(slot: usize) -> (f64, f64) {
        let (x, y, w, h) = home_grid::tile_rect(WIDTH, HEIGHT, slot);
        (x + w / 2.0, y + h / 2.0)
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

    #[test]
    fn app_id_matches_the_stripped_entry_id_case_insensitively() {
        assert!(app_id_matches("foot", "foot.desktop", None));
        assert!(app_id_matches("Foot", "foot.desktop", None));
        assert!(!app_id_matches("footclient", "foot.desktop", None));
        assert!(!app_id_matches("other", "foot.desktop", Some("")));
    }

    #[test]
    fn app_id_matches_falls_back_to_the_exec_hint() {
        assert!(app_id_matches("org.gnome.texteditor", "gnome-text-editor.desktop", Some("org.gnome.TextEditor")));
        assert!(!app_id_matches("unrelated", "gnome-text-editor.desktop", Some("org.gnome.TextEditor")));
    }

    #[test]
    fn find_running_con_id_walks_nested_nodes_and_floating_nodes() {
        let tree = serde_json::json!({
            "type": "root",
            "nodes": [
                {"type": "output", "nodes": [
                    {"type": "con", "app_id": "htop", "id": 11},
                ]},
            ],
            "floating_nodes": [
                {"type": "con", "app_id": "foot", "id": 22},
            ],
        });
        assert_eq!(find_running_con_id(&tree, "foot.desktop", None), Some(22));
        assert_eq!(find_running_con_id(&tree, "htop.desktop", None), Some(11));
        assert_eq!(find_running_con_id(&tree, "gone.desktop", None), None);
    }

    #[test]
    fn find_running_con_id_uses_exec_hint_when_app_id_differs() {
        let tree = serde_json::json!({
            "type": "root",
            "nodes": [{"type": "con", "app_id": "org.gnome.TextEditor", "id": 5}],
        });
        assert_eq!(
            find_running_con_id(&tree, "gnome-text-editor.desktop", Some("org.gnome.TextEditor")),
            Some(5)
        );
        assert_eq!(find_running_con_id(&tree, "gnome-text-editor.desktop", None), None);
    }
}
