//! Home screen gesture state machine: wires `home_pager::HomePager`,
//! `home_grid`'s geometry, and `home_state::HomeLayout` into the single
//! touch-contact dispatch `main.rs` drives, mirroring how `navigation.rs`
//! and `theme_carousel.rs` are each driven today by one `down`/`motion`/
//! `up`/`tick` contact.
//!
//! This change (`the-home-screen-has-widgets-and-folders`) widens what can
//! be dragged and dropped: an existing Home item (app, folder, or widget)
//! being rearranged, or a brand-new app arriving from the drawer's
//! long-press-drag (see [`DragSource`]). Dropping one item onto another now
//! resolves through [`merge_two`]: two apps become a folder, an app onto a
//! folder joins it, and anything that cannot merge falls back to swapping
//! positions (the original behavior) when the two items are the same size,
//! or simply reverts when they are not.

use crate::home_grid::{self, HomeSlot};
use crate::home_pager::{HomePager, LONG_PRESS_MS, TAP_SLOP};
use crate::home_state::{FolderData, HomeItem, HomeLayout, WidgetKind};
use crate::home_widgets::{battery::BatteryState, weather::WeatherDisplay};

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum HomeAction {
    /// Launch, or focus if already running, this desktop-entry id.
    Launch(String),
    /// The layout changed (pin/unpin/reorder/page move/remove/folder
    /// edit/rename); the caller should persist it (`home_state::save`).
    LayoutChanged,
    /// The picker's "Wallpaper & style" row was tapped: the caller
    /// navigates to the existing theme/background chooser route exactly as
    /// a real tap on its own Settings entry point would (`main.rs`'s
    /// `theme_action(ThemeIntent::Open)`), without this module touching
    /// any theme-picker file itself.
    OpenWallpaperAndStyle,
}

/// Where a live drag's item is coming from. Every source drives the same
/// drop resolution ([`HomeScreen::drop_dragged_item`]); only what happens
/// to the *origin* differs:
/// - `Existing`: an already-pinned item being rearranged; its old cell is
///   cleared on a successful drop.
/// - `FromDrawer`: a brand-new app arriving mid-gesture from the drawer's
///   own long-press-drag (task 1); there is no old cell to clear.
/// - `Widget`: a brand-new widget arriving from the widget-picker sheet's
///   long-press-drag (task: "long-press one to drag it onto Home").
/// - `FromFolder`: a member app being dragged back out of an *open* folder
///   (task 3); releasing back over the still-open folder card cancels
///   (the member stays put), releasing anywhere else removes it from the
///   folder (dissolving it if that leaves one member) and places it.
#[derive(Clone, Debug, PartialEq)]
pub enum DragSource {
    Existing(HomeSlot),
    FromDrawer(String),
    Widget(WidgetKind),
    FromFolder { folder: HomeSlot, app_id: String },
}

/// Which page the widget-picker sheet (task: long-press empty Home space)
/// is showing. `Widgets`/`HomeSettings` both reserve row 0 for a "Back to
/// Menu" affordance, sharing `home_grid::picker_row_rect`'s row geometry
/// with `Menu`'s own three rows rather than adding separate chrome.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum WidgetPickerPage {
    Menu,
    Widgets,
    HomeSettings,
}

/// State for Home's widget-picker sheet. Placing a widget is not tracked
/// here at all: long-pressing a preview row arms `HomeScreen::drag`
/// directly (`DragSource::Widget`) and closes the sheet, exactly like the
/// drawer's own long-press-drag reveals Home -- both end up driving the
/// same [`HomeScreen::drop_dragged_item`].
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct WidgetPicker {
    pub page: WidgetPickerPage,
}

fn picker_row_count(page: WidgetPickerPage) -> usize {
    match page {
        WidgetPickerPage::Menu => 3,          // Widgets / Wallpaper & style / Home settings
        // Back, plus one row per `WidgetKind::ALL` entry (data-driven so a
        // new clock style or widget never needs a second hand-counted
        // constant to stay in step with it).
        WidgetPickerPage::Widgets => WidgetKind::ALL.len() + 1,
        WidgetPickerPage::HomeSettings => 2,  // Back, the read-only grid-size stub row
    }
}

/// Which widget, if any, `row` names on the Widgets page (row 0 is always
/// "Back", never a widget) -- `WidgetKind::ALL`'s own order, one row each.
fn widget_for_row(page: WidgetPickerPage, row: usize) -> Option<WidgetKind> {
    if page != WidgetPickerPage::Widgets || row == 0 {
        return None;
    }
    WidgetKind::ALL.get(row - 1).copied()
}

/// State for Home's open-folder overlay (task 5). Rename is armed at the
/// data level (`editing_name`/`name_buffer`); `main.rs` wires a real
/// system-keyboard grab into it (mirroring the Wi-Fi password field's own
/// `sync_wifi_keyboard`), calling `push_folder_name_char`/
/// `backspace_folder_name` as keys arrive and `apply_folder_rename`/
/// `cancel_folder_rename` on Enter/Escape.
#[derive(Clone, Debug, PartialEq)]
pub struct OpenFolder {
    pub slot: HomeSlot,
    pub editing_name: bool,
    pub name_buffer: String,
}

#[derive(Clone, Debug)]
struct Contact {
    id: i32,
    start: (f64, f64),
    held_ms: u32,
    long_fired: bool,
    slot_at_down: Option<HomeSlot>,
    /// Set at `down` when this touch landed on a filled icon's remove badge
    /// while already rearranging. A badge press never becomes a drag (see
    /// `down`): `up` removes that icon outright, matching iOS/webOS's
    /// jiggle-mode badge, which is a tap gesture, not a drag-to-target one.
    badge_at_down: Option<HomeSlot>,
    /// Set at `down` when this touch landed on an addressable but *empty*
    /// grid/dock cell, outside rearrange mode and any overlay -- the
    /// long-press target for the widget-picker sheet (task: "long-press
    /// empty Home space").
    empty_slot_at_down: bool,
    /// Set at `down`, while the open-folder overlay is showing, to the
    /// member app id under the touch, if any -- the long-press target for
    /// dragging that app back out of the folder (task 3).
    folder_app_at_down: Option<String>,
    /// Set at `down`, while the widget-picker sheet is on its Widgets page
    /// and the touch landed on a preview row, to that row's widget -- the
    /// long-press target for dragging it onto Home.
    picker_widget_at_down: Option<WidgetKind>,
}

/// How close to the panel's left/right edge a live drag must hold to count
/// as "at the edge" for the page-turn-while-dragging behavior (`home-widget-
/// design` task 1: "holding within about 40px of the left or right edge").
pub const EDGE_ZONE_PX: f64 = 40.0;
/// How long a drag must dwell in the edge zone before the *first* page turn
/// (task 1: "pages over after about 350-400ms").
pub const EDGE_HOLD_FIRST_MS: u32 = 380;
/// How long a drag must keep dwelling before each *subsequent* page turn
/// while still held at the edge -- shorter than the first, matching Pixel
/// Launcher's own "keeps paging with a short repeat delay".
pub const EDGE_HOLD_REPEAT_MS: u32 = 260;
/// How long an eased page-switch (edge-hold or fling triggered) takes to
/// settle, so the transition always reads as a smooth slide -- never an
/// instant jump -- under the lifted item (task 1: "the page-switch
/// animation stays smooth").
const PAGE_SWITCH_ANIM_MS: u32 = 220;
/// A horizontal drag-point velocity at or above this counts as a "quick,
/// deliberate" mid-drag fling-to-page (task 1), independent of edge
/// proximity or dwell time.
const FLING_PAGE_VELOCITY_PX_PER_SEC: f64 = 900.0;
/// After a fling triggers a page turn, a short lockout before another fling
/// (or edge-hold) can trigger a second one -- without this, one continuous
/// fast swipe would fire several page turns off a single gesture.
const FLING_LOCKOUT_MS: u32 = 260;

/// A short, human-editable default so a freshly merged folder is never
/// blank; task 5 makes the name editable via a tap regardless.
const DEFAULT_FOLDER_NAME: &str = "Folder";

pub struct HomeScreen {
    pub layout: HomeLayout,
    pub pager: HomePager,
    pub rearranging: bool,
    /// The item currently being dragged (existing or drawer-origin), and
    /// its live finger position (for the renderer's floating drag preview).
    pub drag: Option<(DragSource, (f64, f64))>,
    /// Set while Home's open-folder overlay (task 5) is showing; `None`
    /// otherwise. While open, this overlay owns every touch (see `down`).
    pub open_folder: Option<OpenFolder>,
    /// Set while the widget-picker sheet (task: long-press empty Home
    /// space) is showing; `None` otherwise.
    pub widget_picker: Option<WidgetPicker>,
    /// The on-screen keyboard's reserved height in this panel's own
    /// coordinate space, mirrored from `main.rs`'s `sync_home_keyboard`
    /// (task 2) -- `0.0` except while the open folder's name is being
    /// edited and the keyboard is actually showing. Shifts the folder
    /// overlay's card up so its content stays clear of the keyboard
    /// (`home_grid::folder_overlay_rect_inset`).
    pub keyboard_inset: f64,
    /// Live battery-widget content (`home_widgets::battery`), updated by
    /// the caller on its own poll timer; defaults to `Absent`, this board's
    /// actual current state, so a fresh `HomeScreen` never shows a stale
    /// placeholder before the first poll runs.
    pub battery: BatteryState,
    /// Live weather-widget content (`home_widgets::weather`), updated by
    /// the caller from its own cache/fetch cadence; defaults to
    /// `Unavailable` until the first cache read/fetch completes.
    pub weather: WeatherDisplay,
    contact: Option<Contact>,
    edge_held_ms: u32,
    edge_side: i8, // -1 left, 1 right, 0 neither
    /// Whether this edge-hold session has already turned a page once --
    /// `tick` uses [`EDGE_HOLD_FIRST_MS`] before the first turn and the
    /// shorter [`EDGE_HOLD_REPEAT_MS`] for every one after, while the drag
    /// keeps dwelling at the same edge.
    edge_hold_triggered_once: bool,
    /// The drag point's own horizontal timestamp/position, for the mid-drag
    /// fling check -- `None` right after a drag begins (or right after a
    /// fling/edge-hold just fired), so the very next motion sample only
    /// records a fresh baseline instead of computing a velocity against a
    /// stale point from *before* this drag (or this lockout) started.
    drag_track_ms: Option<u32>,
    drag_track_x: f64,
    /// The drag point's most recently computed horizontal velocity, in
    /// panel px/sec (negative = moving left).
    drag_velocity_px_s: f64,
    /// Counts down to zero after a fling or edge-hold page turn, blocking a
    /// second trigger from the same continuous gesture.
    fling_lockout_ms: u32,
    /// `home_grid::apps_per_page` for this drag's own panel height, cached
    /// at the most recent drag-point update -- `tick`'s own edge-hold-
    /// triggered new-page creation needs it but is not itself handed a
    /// panel height (it mirrors every other tick-driven animation in this
    /// shell, which take only an elapsed-ms accumulator).
    apps_per_page_cache: usize,
    /// A live eased transition from one page position to another, driven
    /// every `tick` independently of any pager-owned drag/momentum/settle
    /// state (`home_pager::HomePager::set_position` is the sink) -- the
    /// edge-hold and fling page-switches both start one of these instead of
    /// jumping the pager's position instantly.
    page_switch: Option<PageSwitchAnim>,
}

/// See [`HomeScreen::page_switch`]'s own doc.
#[derive(Clone, Copy, Debug)]
struct PageSwitchAnim {
    from: f64,
    target: f64,
    elapsed_ms: u32,
    duration_ms: u32,
}

/// What dropping `dragged` onto an already-occupied cell should produce, if
/// anything: two apps merge into a new folder, an app joins an existing
/// folder, or a folder absorbs a lone app dropped onto it. Anything else
/// (a widget involved on either side, two folders, an app dropped onto
/// itself) returns `None` -- the caller's own same-span check then decides
/// between a plain swap and reverting.
fn merge_two(dragged: HomeItem, existing: HomeItem) -> Option<HomeItem> {
    match (dragged, existing) {
        (HomeItem::App { id: a }, HomeItem::App { id: b }) if a != b => {
            Some(HomeItem::Folder(FolderData { name: DEFAULT_FOLDER_NAME.into(), apps: vec![b, a] }))
        }
        (HomeItem::App { id: a }, HomeItem::Folder(mut folder)) => {
            if folder.apps.contains(&a) {
                None
            } else {
                folder.apps.push(a);
                Some(HomeItem::Folder(folder))
            }
        }
        (HomeItem::Folder(mut dragged_folder), HomeItem::App { id: b }) => {
            // Folding the target app into the *dragged* folder (rather than
            // the reverse) keeps the folder a person is actively holding as
            // the one that survives, matching where their attention is.
            if dragged_folder.apps.contains(&b) {
                None
            } else {
                dragged_folder.apps.push(b);
                Some(HomeItem::Folder(dragged_folder))
            }
        }
        _ => None,
    }
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
            open_folder: None,
            widget_picker: None,
            keyboard_inset: 0.0,
            battery: BatteryState::Absent,
            weather: WeatherDisplay::Unavailable,
            contact: None,
            edge_held_ms: 0,
            edge_side: 0,
            edge_hold_triggered_once: false,
            drag_track_ms: None,
            drag_track_x: 0.0,
            drag_velocity_px_s: 0.0,
            fling_lockout_ms: 0,
            apps_per_page_cache: 1,
            page_switch: None,
        }
    }

    pub fn page_count(&self) -> usize {
        self.layout.page_count()
    }

    /// Clears every piece of cross-page-drag tracking state -- called at the
    /// moment a fresh drag begins (`down`, and every `tick`/
    /// `begin_external_drag` site that sets `self.drag = Some(..)`), so a
    /// stale velocity/edge-dwell/lockout reading from a *previous*, already-
    /// finished drag can never leak into the next one's very first motion
    /// sample.
    fn reset_drag_tracking(&mut self) {
        self.drag_track_ms = None;
        self.drag_velocity_px_s = 0.0;
        self.edge_held_ms = 0;
        self.edge_side = 0;
        self.edge_hold_triggered_once = false;
        self.fling_lockout_ms = 0;
        self.page_switch = None;
    }

    /// Records a live drag's current finger position for both the edge-hold
    /// page-switch (`edge_side`/`edge_held_ms`, advanced by `tick`) and the
    /// mid-drag fling check (`maybe_fling`). Shared by the internal
    /// (`motion`) and external drawer-origin (`external_drag_motion`) drag
    /// paths so the two behave identically.
    fn note_drag_point(&mut self, point: (f64, f64), time_ms: u32, width: u32, height: u32) {
        self.apps_per_page_cache = home_grid::apps_per_page(height).max(1);
        if let Some(last_ms) = self.drag_track_ms {
            let elapsed = time_ms.wrapping_sub(last_ms);
            if elapsed > 0 && elapsed < 1000 {
                self.drag_velocity_px_s = ((point.0 - self.drag_track_x) * 1000.0 / f64::from(elapsed)).clamp(-4000.0, 4000.0);
            }
        }
        self.drag_track_x = point.0;
        self.drag_track_ms = Some(time_ms);
        let new_edge_side = if point.0 < EDGE_ZONE_PX {
            -1
        } else if point.0 > f64::from(width) - EDGE_ZONE_PX {
            1
        } else {
            0
        };
        if new_edge_side != self.edge_side {
            self.edge_held_ms = 0;
            self.edge_hold_triggered_once = false;
        }
        self.edge_side = new_edge_side;
        self.maybe_fling();
    }

    /// A quick, deliberate horizontal fling mid-drag pages over immediately,
    /// independent of edge proximity or any dwell (task 1: "allow a quick,
    /// deliberate horizontal fling mid-drag to page"). Never creates a new
    /// page itself -- reaching the true last page still requires the
    /// edge-hold's own dwell, matching a fling's "quick nudge" character
    /// rather than a page-creating commitment.
    fn maybe_fling(&mut self) {
        if self.page_switch.is_some() || self.fling_lockout_ms > 0 {
            return;
        }
        if self.drag_velocity_px_s.abs() < FLING_PAGE_VELOCITY_PX_PER_SEC {
            return;
        }
        let count = self.page_count();
        let current = self.pager.page(count);
        // Negative velocity == finger moving left, matching
        // `HomePager::motion`'s own sign convention (dragging left reveals
        // the next page to the right).
        if self.drag_velocity_px_s < 0.0 {
            if current + 1 < count {
                self.start_page_switch(current + 1);
                self.fling_lockout_ms = FLING_LOCKOUT_MS;
            }
        } else if current > 0 {
            self.start_page_switch(current - 1);
            self.fling_lockout_ms = FLING_LOCKOUT_MS;
        }
    }

    /// Starts (or retargets) the eased page-switch animation toward `target`.
    /// A no-op if already there.
    fn start_page_switch(&mut self, target: usize) {
        let from = self.pager.position();
        let target = target as f64;
        if (from - target).abs() < 0.001 {
            return;
        }
        self.page_switch = Some(PageSwitchAnim { from, target, elapsed_ms: 0, duration_ms: PAGE_SWITCH_ANIM_MS });
        self.edge_held_ms = 0;
    }

    /// Advances a live edge-hold dwell timer and triggers a page-switch (or,
    /// at the true last page's right edge, a brand-new page -- task 1:
    /// "dragging onto the last page's right edge creates a new page") once
    /// it crosses [`EDGE_HOLD_FIRST_MS`] (or [`EDGE_HOLD_REPEAT_MS`] for a
    /// repeat within the same edge-hold session). A no-op whenever a
    /// page-switch animation is already live, so a fling and an edge-hold
    /// can never both fire for the same moment.
    fn advance_edge_hold(&mut self, elapsed_ms: u32) {
        if self.edge_side == 0 || self.page_switch.is_some() {
            return;
        }
        self.edge_held_ms = self.edge_held_ms.saturating_add(elapsed_ms);
        let threshold = if self.edge_hold_triggered_once { EDGE_HOLD_REPEAT_MS } else { EDGE_HOLD_FIRST_MS };
        if self.edge_held_ms < threshold {
            return;
        }
        self.edge_held_ms = 0;
        self.edge_hold_triggered_once = true;
        let count = self.page_count();
        let current = self.pager.page(count);
        if self.edge_side > 0 && current + 1 >= count {
            let new_page = self.layout.add_blank_page(self.apps_per_page_cache);
            self.start_page_switch(new_page);
        } else {
            let next = if self.edge_side < 0 {
                current.saturating_sub(1)
            } else {
                (current + 1).min(count.saturating_sub(1))
            };
            self.start_page_switch(next);
        }
    }

    /// Advances any live page-switch animation. Always safe to call (a
    /// no-op with none live), and deliberately not gated on a drag still
    /// being held, so a switch that started right before release finishes
    /// its smooth slide rather than snapping.
    fn advance_page_switch(&mut self, elapsed_ms: u32) -> bool {
        let Some(anim) = self.page_switch.as_mut() else { return false };
        anim.elapsed_ms = anim.elapsed_ms.saturating_add(elapsed_ms.min(48));
        let t = (f64::from(anim.elapsed_ms) / f64::from(anim.duration_ms)).min(1.0);
        let eased = 1.0 - (1.0 - t).powi(3);
        let position = anim.from + (anim.target - anim.from) * eased;
        let done = t >= 1.0;
        let target = anim.target;
        self.pager.set_position(if done { target } else { position }, self.page_count());
        if done {
            self.page_switch = None;
        }
        true
    }

    /// `Some((side, progress))` while a live drag is dwelling in an edge
    /// zone, `progress` in `0.0..=1.0` toward the next page turn -- the
    /// renderer's own edge highlight/arrow (task 1: "a visible edge
    /// highlight or arrow showing it's about to switch") fades/grows in with
    /// this.
    pub fn drag_edge_indicator(&self) -> Option<(i8, f64)> {
        if self.drag.is_none() || self.edge_side == 0 || self.page_switch.is_some() {
            return None;
        }
        let threshold = if self.edge_hold_triggered_once { EDGE_HOLD_REPEAT_MS } else { EDGE_HOLD_FIRST_MS };
        let progress = (f64::from(self.edge_held_ms) / f64::from(threshold.max(1))).clamp(0.0, 1.0);
        Some((self.edge_side, progress))
    }

    /// Whether the live drag's item would actually fit at its current drop
    /// target -- the renderer's "no room here" indication (task 1) for a
    /// multi-cell widget hovering somewhere its span cannot land. `true`
    /// with no live drag or no resolvable target (nothing to contradict).
    pub fn drop_target_fits(&self, width: u32, height: u32) -> bool {
        let Some(item) = self.dragged_item() else { return true };
        let Some(slot) = self.drop_target(width, height) else { return true };
        self.layout.would_fit(slot, item.span())
    }

    /// Any grid cell within the current page's bounds resolves to a slot,
    /// filled or not -- an empty cell is still a valid rearrange-mode drop
    /// target. Callers that only want an actual icon hit go through
    /// [`Self::filled_slot_at`] instead. Returns the *raw* cell, not
    /// necessarily an item's anchor -- see [`Self::filled_slot_at`] for the
    /// anchor-resolved version widgets need.
    fn slot_at(&self, point: (f64, f64), width: u32, height: u32) -> Option<HomeSlot> {
        if let Some(dock_slot) = home_grid::dock_slot_at(point, width, height) {
            return Some(HomeSlot::Dock { slot: dock_slot });
        }
        let page = self.pager.page(self.page_count());
        home_grid::slot_at(point, width, height, home_grid::apps_per_page(height))
            .map(|slot| HomeSlot::Grid { page, slot })
    }

    /// The item actually under `point`, resolved to its anchor slot -- a
    /// tap or long-press anywhere within a multi-cell widget's whole span
    /// resolves to that widget, not to whichever raw cell the finger
    /// happened to land on (`home_state::HomeLayout::anchor_at`).
    fn filled_slot_at(&self, point: (f64, f64), width: u32, height: u32) -> Option<HomeSlot> {
        let raw = self.slot_at(point, width, height)?;
        self.layout.anchor_at(raw).map(|(anchor, _)| anchor)
    }

    /// Which filled slot's remove badge (if any) `point` lands in, while
    /// rearranging -- checked across every anchored item on the current
    /// page plus the dock, since a badge sits at a plate's corner, outside
    /// that icon's own tile-cell hit region.
    fn badge_at(&self, point: (f64, f64), width: u32, height: u32) -> Option<HomeSlot> {
        let page = self.pager.page(self.page_count());
        let apps_per_page = home_grid::apps_per_page(height);
        let candidates = (0..apps_per_page)
            .map(|slot| HomeSlot::Grid { page, slot })
            .chain((0..home_grid::DOCK_SLOTS).map(|slot| HomeSlot::Dock { slot }));
        candidates
            .filter(|slot| self.layout.get(*slot).is_some())
            .find(|slot| {
                let corner = home_grid::plate_top_left(width, height, *slot);
                home_grid::hits_circle(point, corner, home_grid::REMOVE_BADGE_HIT_RADIUS)
            })
    }

    /// Sets the on-screen keyboard's reserved height, in this panel's own
    /// coordinate space -- `main.rs::sync_home_keyboard` calls this exactly
    /// like `WifiView::set_keyboard_inset` (task 2).
    pub fn set_keyboard_inset(&mut self, inset: f64) {
        self.keyboard_inset = inset.max(0.0);
    }

    /// The open folder's own member-app id under `point`, if the folder
    /// overlay is showing and `point` lands on one of its member tiles.
    fn folder_app_id_at(&self, point: (f64, f64), width: u32, height: u32) -> Option<String> {
        let open = self.open_folder.as_ref()?;
        let folder = self.layout.get(open.slot)?.as_folder()?;
        let index = home_grid::folder_app_at(point, width, height, folder.apps.len(), self.keyboard_inset)?;
        folder.apps.get(index).cloned()
    }

    pub fn down(&mut self, id: i32, point: (f64, f64), time_ms: u32, width: u32, height: u32) {
        if self.contact.is_some() {
            self.cancel();
            return;
        }
        if self.open_folder.is_some() {
            // The overlay owns this touch: a plain release resolves at
            // `up` (`resolve_folder_tap`), and a hold on a member tile is
            // armed here for `tick` to promote into a drag-out (task 3).
            let folder_app_at_down = self.folder_app_id_at(point, width, height);
            self.contact = Some(Contact {
                id,
                start: point,
                held_ms: 0,
                long_fired: folder_app_at_down.is_none(),
                slot_at_down: None,
                badge_at_down: None,
                empty_slot_at_down: false,
                folder_app_at_down,
                picker_widget_at_down: None,
            });
            return;
        }
        if let Some(picker) = self.widget_picker {
            // Likewise: a plain release resolves at `up`
            // (`resolve_picker_tap`); a hold on a Widgets-page preview row
            // is armed here for `tick` to promote into a placement drag.
            let count = picker_row_count(picker.page);
            let picker_widget_at_down = home_grid::picker_row_at(point, width, height, count)
                .and_then(|row| widget_for_row(picker.page, row));
            self.contact = Some(Contact {
                id,
                start: point,
                held_ms: 0,
                long_fired: picker_widget_at_down.is_none(),
                slot_at_down: None,
                badge_at_down: None,
                empty_slot_at_down: false,
                folder_app_at_down: None,
                picker_widget_at_down,
            });
            return;
        }
        let badge_at_down = if self.rearranging {
            self.badge_at(point, width, height)
        } else {
            None
        };
        let slot_at_down = self.filled_slot_at(point, width, height);
        // An addressable cell (grid within the page, or dock) that is not
        // already occupied -- the widget-picker's own long-press target
        // (task: "long-press empty Home space"), only outside rearrange
        // mode (where every touch on empty space already means something
        // else -- exit rearranging, see `up`).
        let empty_slot_at_down = !self.rearranging
            && badge_at_down.is_none()
            && slot_at_down.is_none()
            && self.slot_at(point, width, height).is_some();
        self.contact = Some(Contact {
            id,
            start: point,
            held_ms: 0,
            // Already in rearrange mode: no fresh long-press timer is
            // needed (a grab below, or a plain tap, decides this touch),
            // so mark the long-press as already "used" up front.
            long_fired: self.rearranging,
            slot_at_down,
            badge_at_down,
            empty_slot_at_down,
            folder_app_at_down: None,
            picker_widget_at_down: None,
        });
        if self.rearranging {
            // A fresh touch on any filled icon grabs it immediately,
            // exactly as real launchers' own "jiggle mode" lets any icon
            // be picked up without holding again -- unless it landed on
            // that icon's own remove badge instead, which never drags.
            // Touching empty space, or a non-drag tap on an icon, is
            // resolved at `up` instead.
            if badge_at_down.is_none() {
                if let Some(slot) = slot_at_down {
                    self.reset_drag_tracking();
                    self.drag = Some((DragSource::Existing(slot), point));
                    self.note_drag_point(point, time_ms, width, height);
                }
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
        height: u32,
    ) -> bool {
        let Some(contact) = self.contact.as_mut() else {
            return false;
        };
        if contact.id != id {
            return false;
        }
        if self.drag.is_some() {
            if let Some(entry) = self.drag.as_mut() {
                entry.1 = point;
            }
            self.note_drag_point(point, time_ms, width, height);
            return true;
        }
        if self.open_folder.is_some() || self.widget_picker.is_some() {
            // Not yet dragging out of the folder / off the picker sheet --
            // nothing else moves while either overlay is showing (no
            // scrolling in either card today).
            return false;
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

    /// Advances the pager's momentum/settle animation, a live cross-page-
    /// drag's edge-hold dwell and page-switch slide, and, while a finger
    /// rests without moving on a filled icon (or an open folder's member
    /// tile, or a picker preview row), the long-press timer. Returns whether
    /// a repaint is needed.
    ///
    /// The three long-press-to-drag paths below (open-folder member, picker
    /// widget, plain Home icon) only ever *arm* a drag while none is yet
    /// live (`self.drag.is_none()`); once armed, every one of them falls
    /// through to this function's own final section so the same edge-hold/
    /// fling/page-switch machinery drives every drag source identically,
    /// regardless of which overlay (if any) was showing when it started.
    pub fn tick(&mut self, elapsed_ms: u32) -> bool {
        let mut redraw = false;
        if self.open_folder.is_some() && self.drag.is_none() {
            if let Some(contact) = self.contact.as_mut() {
                if !contact.long_fired {
                    if let Some(app_id) = contact.folder_app_at_down.clone() {
                        contact.held_ms = contact.held_ms.saturating_add(elapsed_ms);
                        if contact.held_ms >= LONG_PRESS_MS {
                            contact.long_fired = true;
                            let start = contact.start;
                            if let Some(folder_slot) = self.open_folder.as_ref().map(|open| open.slot) {
                                self.reset_drag_tracking();
                                self.drag = Some((DragSource::FromFolder { folder: folder_slot, app_id }, start));
                                redraw = true;
                            }
                        }
                    }
                }
            }
        } else if self.widget_picker.is_some() && self.drag.is_none() {
            if let Some(contact) = self.contact.as_mut() {
                if !contact.long_fired {
                    if let Some(kind) = contact.picker_widget_at_down {
                        contact.held_ms = contact.held_ms.saturating_add(elapsed_ms);
                        if contact.held_ms >= LONG_PRESS_MS {
                            contact.long_fired = true;
                            let start = contact.start;
                            self.reset_drag_tracking();
                            self.drag = Some((DragSource::Widget(kind), start));
                            self.widget_picker = None; // the sheet gets out of the way once a drag starts
                            redraw = true;
                        }
                    }
                }
            }
        } else if self.drag.is_none() {
            if !self.rearranging {
                redraw |= self.pager.tick(elapsed_ms, self.page_count());
            }
            if let Some(contact) = self.contact.as_mut() {
                if !contact.long_fired && !self.pager.dragging() {
                    contact.held_ms = contact.held_ms.saturating_add(elapsed_ms);
                    if contact.held_ms >= LONG_PRESS_MS {
                        contact.long_fired = true;
                        if let Some(slot) = contact.slot_at_down {
                            let start = contact.start;
                            self.rearranging = true;
                            self.reset_drag_tracking();
                            self.drag = Some((DragSource::Existing(slot), start));
                            redraw = true;
                        } else if contact.empty_slot_at_down {
                            self.widget_picker = Some(WidgetPicker { page: WidgetPickerPage::Menu });
                            redraw = true;
                        }
                    }
                }
            }
        }

        if self.fling_lockout_ms > 0 {
            self.fling_lockout_ms = self.fling_lockout_ms.saturating_sub(elapsed_ms.min(self.fling_lockout_ms));
        }
        if self.drag.is_some() {
            self.advance_edge_hold(elapsed_ms);
        }
        redraw |= self.advance_page_switch(elapsed_ms);
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
        // A live drag always takes priority, even while an overlay is also
        // showing -- a drag-out-of-folder (task 3) or a picker-widget drag
        // both keep `open_folder`/`widget_picker` set (respectively) for as
        // long as the drag is live, so this must be checked before either
        // overlay's own tap resolution.
        if let Some((source, _)) = self.drag.take() {
            return self.drop_dragged_item(source, point, width, height);
        }
        if self.open_folder.is_some() {
            return self.resolve_folder_tap(point, width, height);
        }
        if self.widget_picker.is_some() {
            return self.resolve_picker_tap(point, width, height);
        }
        if let Some(slot) = contact.badge_at_down {
            // The badge is a tap gesture, not a drag-to-target one (see
            // `down`): releasing anywhere removes the icon it belonged to.
            self.layout.remove_slot(slot);
            return Some(HomeAction::LayoutChanged);
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
        let slot = self.filled_slot_at(point, width, height)?;
        match self.layout.get(slot)?.clone() {
            HomeItem::App { id } => Some(HomeAction::Launch(id)),
            HomeItem::Folder(_) => {
                self.open_folder = Some(OpenFolder { slot, editing_name: false, name_buffer: String::new() });
                None
            }
            HomeItem::Widget { .. } => None, // tapping a widget outside rearrange does nothing yet
        }
    }

    /// Resolves a release while the open-folder overlay is showing: a tap
    /// on a member app launches it and closes the overlay, a tap on the
    /// name label arms rename (data-level only -- see `OpenFolder`'s own
    /// doc), and a tap anywhere outside the card closes it with no other
    /// effect.
    fn resolve_folder_tap(&mut self, point: (f64, f64), width: u32, height: u32) -> Option<HomeAction> {
        let open = self.open_folder.clone()?;
        let card = home_grid::folder_overlay_rect_inset(width, height, self.keyboard_inset);
        if !home_grid::hits(point, card) {
            self.open_folder = None;
            return None;
        }
        let Some(HomeItem::Folder(folder)) = self.layout.get(open.slot).cloned() else {
            self.open_folder = None;
            return None;
        };
        if home_grid::hits(point, home_grid::folder_name_rect_inset(width, height, self.keyboard_inset)) {
            if let Some(open) = self.open_folder.as_mut() {
                open.editing_name = true;
                open.name_buffer = folder.name.clone();
            }
            return None;
        }
        if let Some(index) = home_grid::folder_app_at(point, width, height, folder.apps.len(), self.keyboard_inset) {
            let app_id = folder.apps[index].clone();
            self.open_folder = None;
            return Some(HomeAction::Launch(app_id));
        }
        None
    }

    /// Resolves a release while the widget-picker sheet is showing: on the
    /// Menu page, taps navigate to Widgets/Wallpaper & style/Home settings;
    /// on either sub-page, row 0 ("Back") returns to Menu; a tap anywhere
    /// outside the card closes the sheet entirely. A plain tap on a widget
    /// preview does nothing -- only the long-press-drag (`tick`) places it,
    /// matching the task's own "long-press one to drag it onto Home".
    fn resolve_picker_tap(&mut self, point: (f64, f64), width: u32, height: u32) -> Option<HomeAction> {
        let picker = self.widget_picker?;
        let card = home_grid::picker_rect(width, height);
        if !home_grid::hits(point, card) {
            self.widget_picker = None;
            return None;
        }
        let count = picker_row_count(picker.page);
        let row = home_grid::picker_row_at(point, width, height, count)?;
        match picker.page {
            WidgetPickerPage::Menu => match row {
                0 => self.widget_picker = Some(WidgetPicker { page: WidgetPickerPage::Widgets }),
                1 => {
                    self.widget_picker = None;
                    return Some(HomeAction::OpenWallpaperAndStyle);
                }
                2 => self.widget_picker = Some(WidgetPicker { page: WidgetPickerPage::HomeSettings }),
                _ => {}
            },
            WidgetPickerPage::Widgets | WidgetPickerPage::HomeSettings => {
                if row == 0 {
                    self.widget_picker = Some(WidgetPicker { page: WidgetPickerPage::Menu });
                }
            }
        }
        None
    }

    /// Closes the widget-picker sheet without acting on it -- used by
    /// `main.rs` for an explicit dismiss (e.g. a hardware Back), mirroring
    /// [`Self::close_folder`].
    pub fn close_widget_picker(&mut self) {
        self.widget_picker = None;
    }

    /// Applies whatever is in the open folder's rename buffer, if it is
    /// non-empty, and leaves rename mode. A caller wiring a real
    /// system-keyboard grab (task 5's "request keyboard interactivity")
    /// calls [`Self::push_folder_name_char`]/[`Self::backspace_folder_name`]
    /// as keys arrive, then this once the field is dismissed/confirmed.
    pub fn apply_folder_rename(&mut self) -> Option<HomeAction> {
        let open = self.open_folder.as_ref()?;
        let slot = open.slot;
        let new_name = open.name_buffer.trim().to_string();
        if new_name.is_empty() {
            return None;
        }
        let Some(HomeItem::Folder(mut folder)) = self.layout.get(slot).cloned() else {
            return None;
        };
        folder.name = new_name;
        self.layout.set(slot, Some(HomeItem::Folder(folder)), 1);
        if let Some(open) = self.open_folder.as_mut() {
            open.editing_name = false;
        }
        Some(HomeAction::LayoutChanged)
    }

    pub fn cancel_folder_rename(&mut self) {
        if let Some(open) = self.open_folder.as_mut() {
            open.editing_name = false;
        }
    }

    pub fn push_folder_name_char(&mut self, ch: char) {
        if let Some(open) = self.open_folder.as_mut() {
            if open.editing_name && open.name_buffer.chars().count() < 40 {
                open.name_buffer.push(ch);
            }
        }
    }

    pub fn backspace_folder_name(&mut self) {
        if let Some(open) = self.open_folder.as_mut() {
            if open.editing_name {
                open.name_buffer.pop();
            }
        }
    }

    pub fn close_folder(&mut self) {
        self.open_folder = None;
    }

    /// Begins a drag whose item did not previously exist anywhere on Home
    /// -- the drawer's long-press-drag hand-off (task 1). The caller
    /// (`main.rs`) is expected to have already revealed Home; this only
    /// arms the drag/edge-page-switch state, exactly like a rearrange
    /// drag's own `self.drag`.
    pub fn begin_external_drag(&mut self, app_id: String, point: (f64, f64)) {
        self.reset_drag_tracking();
        self.drag = Some((DragSource::FromDrawer(app_id), point));
    }

    /// Updates a live external (drawer-origin) drag's finger position, edge-
    /// page-switch dwell tracking, and mid-drag fling check (`note_drag_
    /// point`, shared with the internal `motion` path). Unlike that path,
    /// this has no `Contact` of its own to gate on (the drawer's own touch
    /// owns the gesture -- see `navigation.rs`'s own drag-arm doc).
    pub fn external_drag_motion(&mut self, point: (f64, f64), time_ms: u32, width: u32, height: u32) {
        if let Some(entry) = self.drag.as_mut() {
            entry.1 = point;
        }
        self.note_drag_point(point, time_ms, width, height);
    }

    /// Resolves a live drag's drop point (used both by an internal
    /// rearrange release and, from `main.rs`, an external drawer-drag
    /// release once it has already ruled out Cancel).
    pub fn release_drag(&mut self, point: (f64, f64), width: u32, height: u32) -> Option<HomeAction> {
        let (source, _) = self.drag.take()?;
        self.drop_dragged_item(source, point, width, height)
    }

    /// Abandons a live drag with no layout change at all -- an internal
    /// rearrange drag has no such path today (releasing always resolves to
    /// somewhere), but an external drawer-drag's Cancel target uses this.
    pub fn cancel_external_drag(&mut self) {
        self.drag = None;
        self.reset_drag_tracking();
    }

    /// `None` when the drop changed nothing (a plain tap-release on an
    /// already-grabbed icon, with no actual move, or a drop somewhere that
    /// cannot resolve to any slot at all) -- the caller then skips
    /// persisting.
    fn drop_dragged_item(
        &mut self,
        source: DragSource,
        point: (f64, f64),
        width: u32,
        height: u32,
    ) -> Option<HomeAction> {
        let apps_per_page = home_grid::apps_per_page(height);
        if let DragSource::Existing(slot) = &source {
            if home_grid::hits(point, home_grid::remove_target_rect(width)) {
                self.layout.remove_slot(*slot);
                return Some(HomeAction::LayoutChanged);
            }
        }
        let target = self.slot_at(point, width, height);
        match source {
            DragSource::Existing(from) => match target {
                Some(target) => self.move_existing(from, target, apps_per_page),
                None => {
                    // The drop point resolved to no grid/dock cell at all --
                    // e.g. released right in the edge margin just past the
                    // last tile column, which sits *inside* the edge-hold
                    // trigger zone (`EDGE_ZONE_PX`) but outside any tile's
                    // own hit rect, a very natural place to lift off right
                    // after watching a cross-page drag turn the page. Land
                    // on the page currently on screen instead of silently
                    // reverting the drag to its origin page (operator
                    // report: "the item snaps back to its original page").
                    let page = self.pager.page(self.page_count());
                    self.move_existing_to_page(from, page, apps_per_page)
                }
            },
            DragSource::FromDrawer(id) => {
                let item = HomeItem::app(id);
                let placed = match target {
                    Some(target) => self.place_new(item.clone(), target, apps_per_page),
                    None => None,
                };
                if placed.is_some() {
                    placed
                } else {
                    // No resolvable/compatible target (e.g. dropped past
                    // the last page, or onto a widget) -- still place the
                    // app somewhere rather than silently discarding a drag
                    // the person just carried out of the drawer.
                    self.layout.place_first_fit(item, apps_per_page);
                    Some(HomeAction::LayoutChanged)
                }
            }
            DragSource::Widget(kind) => {
                // Exactly the same fallback shape as `FromDrawer`, just
                // placing a widget instead of an app -- `place_first_fit`
                // is already generic over `HomeItem` (home_state.rs), so
                // this reuses it unchanged.
                let item = HomeItem::Widget { widget: kind };
                let placed = match target {
                    Some(target) => self.place_new(item.clone(), target, apps_per_page),
                    None => None,
                };
                if placed.is_some() {
                    placed
                } else {
                    self.layout.place_first_fit(item, apps_per_page);
                    Some(HomeAction::LayoutChanged)
                }
            }
            DragSource::FromFolder { folder, app_id } => {
                // Cancel target is the folder's *own* grid/dock slot, not
                // its whole (much larger) open card -- the card visually
                // covers most of the page it sits on, so treating the
                // entire card as "still the folder" would make almost any
                // drop onto that same page read as a cancel. Dropping back
                // precisely onto the folder's own icon is the same
                // "return it" gesture reference launchers use once a
                // dragged item leaves an open folder.
                if target == Some(folder) {
                    return None;
                }
                self.layout.remove_app(&app_id); // dissolves the folder if this leaves one member
                let item = HomeItem::app(app_id);
                let placed = match target {
                    Some(target) => self.place_new(item.clone(), target, apps_per_page),
                    None => None,
                };
                if placed.is_none() {
                    self.layout.place_first_fit(item, apps_per_page);
                }
                self.open_folder = None; // the drag left the folder; close the overlay
                Some(HomeAction::LayoutChanged)
            }
        }
    }

    /// Moves an already-pinned item from `from` to `target`: a plain move
    /// into an empty cell, a merge (folder create/add) when `target` holds
    /// something mergeable, or a same-span swap as the fallback. When none
    /// of those apply -- `target` itself cannot fit the item's span, or it
    /// holds something that can neither merge nor swap with it -- this
    /// falls back to the nearest free cell on `target`'s own page rather
    /// than reverting: `target`'s page is wherever the drag *currently* is
    /// (which, mid a cross-page drag, is no longer necessarily `from`'s own
    /// page), so silently giving up here is exactly the "snaps back to its
    /// original page" bug a real cross-page drag must not exhibit.
    fn move_existing(&mut self, from: HomeSlot, target: HomeSlot, apps_per_page: usize) -> Option<HomeAction> {
        if target == from {
            return None;
        }
        let dragged = self.layout.get(from)?.clone();
        match self.layout.get(target).cloned() {
            None => {
                self.layout.remove_slot(from);
                if self.layout.place(target, dragged.clone(), apps_per_page, false) {
                    Some(HomeAction::LayoutChanged)
                } else if let HomeSlot::Grid { page, .. } = target {
                    self.place_on_page_or_restore(from, page, dragged, apps_per_page)
                } else {
                    // A dock target that doesn't fit (e.g. a widget aimed at
                    // the dock, which is never widget-eligible) -- put it
                    // back exactly where it was.
                    self.layout.place(from, dragged, apps_per_page, false);
                    None
                }
            }
            Some(existing) => {
                if let Some(merged) = merge_two(dragged.clone(), existing.clone()) {
                    self.layout.remove_slot(from);
                    self.layout.set(target, Some(merged), apps_per_page);
                    Some(HomeAction::LayoutChanged)
                } else if dragged.span() == existing.span() {
                    self.layout.set(target, Some(dragged), apps_per_page);
                    self.layout.set(from, Some(existing), apps_per_page);
                    Some(HomeAction::LayoutChanged)
                } else if let HomeSlot::Grid { page, .. } = target {
                    self.layout.remove_slot(from);
                    self.place_on_page_or_restore(from, page, dragged, apps_per_page)
                } else {
                    None
                }
            }
        }
    }

    /// Places `dragged` at the first free-fitting cell on `page`, or -- if
    /// `page` truly has no room for it -- restores it to `from` instead of
    /// losing it. `from` must already have been cleared by the caller.
    /// Shared by both of [`Self::move_existing`]'s own fallback sites and
    /// [`Self::move_existing_to_page`] (the "no resolvable target at all"
    /// case), all three of which face the exact same choice between landing
    /// on the page the drag is currently over versus reverting.
    fn place_on_page_or_restore(
        &mut self,
        from: HomeSlot,
        page: usize,
        dragged: HomeItem,
        apps_per_page: usize,
    ) -> Option<HomeAction> {
        // Recreates `page` if the drag's own origin-cell `remove_slot` just
        // pruned it away for being (still) empty -- see `ensure_page`'s own
        // doc for why this must run before `first_fit`.
        self.layout.ensure_page(page, apps_per_page);
        if let Some(slot) = self.layout.first_fit(page, &dragged, apps_per_page) {
            self.layout.place(HomeSlot::Grid { page, slot }, dragged, apps_per_page, false);
            Some(HomeAction::LayoutChanged)
        } else {
            self.layout.place(from, dragged, apps_per_page, false);
            None
        }
    }

    /// Moves an already-pinned item from `from` onto `page` at its nearest
    /// free-fitting cell, used when a rearrange drag's release point
    /// resolves to no slot at all (e.g. right in the edge margin, just past
    /// the last tile column, which sits inside the edge-hold trigger zone
    /// but outside every tile's own hit rect). `page` is whichever page is
    /// actually on screen at release -- not necessarily `from`'s own page,
    /// mid a cross-page drag.
    fn move_existing_to_page(&mut self, from: HomeSlot, page: usize, apps_per_page: usize) -> Option<HomeAction> {
        if let HomeSlot::Grid { page: from_page, .. } = from {
            if from_page == page {
                return None; // never left its own page; nothing to commit
            }
        }
        let dragged = self.layout.get(from)?.clone();
        self.layout.remove_slot(from);
        self.place_on_page_or_restore(from, page, dragged, apps_per_page)
    }

    /// Places a brand-new item (the drawer's drag hand-off) at `target`: a
    /// plain placement into an empty cell, or a merge when `target` holds
    /// something mergeable. `None` (no placement at all) when `target` is
    /// occupied by something incompatible -- the caller's own
    /// `place_first_fit` fallback then still lands the app somewhere.
    fn place_new(&mut self, item: HomeItem, target: HomeSlot, apps_per_page: usize) -> Option<HomeAction> {
        match self.layout.get(target).cloned() {
            None => {
                if self.layout.place(target, item, apps_per_page, false) {
                    Some(HomeAction::LayoutChanged)
                } else {
                    None
                }
            }
            Some(existing) => {
                let merged = merge_two(item, existing)?;
                self.layout.set(target, Some(merged), apps_per_page);
                Some(HomeAction::LayoutChanged)
            }
        }
    }

    pub fn cancel(&mut self) {
        self.contact = None;
        self.drag = None;
        self.reset_drag_tracking();
        self.pager.cancel();
    }

    /// True while the pager is coasting/settling, a rearrange drag is held
    /// near a page edge accumulating toward an auto-page-turn, or an
    /// edge-hold/fling page-switch is mid-slide -- the caller should poll at
    /// the fast tick rate in any of these rather than waiting for the next
    /// Wayland event.
    pub fn is_animating(&self) -> bool {
        self.pager.is_animating() || (self.drag.is_some() && self.edge_side != 0) || self.page_switch.is_some()
    }

    /// Which slot, if any, should show an immediate "pressed" highlight:
    /// the finger is down on a filled icon and hasn't started a page drag
    /// or a rearrange drag yet.
    pub fn pressed(&self, width: u32, height: u32) -> Option<HomeSlot> {
        let contact = self.contact.as_ref()?;
        if self.drag.is_some() || self.pager.dragging() || contact.badge_at_down.is_some() {
            return None;
        }
        self.filled_slot_at(contact.start, width, height)
    }

    /// While a rearrange drag is live, the slot it would land on if
    /// released right now -- the renderer highlights this as a visible drop
    /// target, matching the affordance every reference launcher gives a
    /// dragged icon. Works the same for an external (drawer-origin) drag.
    pub fn drop_target(&self, width: u32, height: u32) -> Option<HomeSlot> {
        let (_, point) = self.drag.as_ref()?;
        self.slot_at(*point, width, height)
    }

    /// The concrete item currently being lifted, if any -- for `Existing`,
    /// whatever is (still) at its origin slot; for `FromDrawer`, a fresh
    /// `HomeItem::App` wrapping the dragged id. The renderer uses this to
    /// decide how to paint the floating drag preview.
    pub fn dragged_item(&self) -> Option<HomeItem> {
        match self.drag.as_ref()?.0.clone() {
            DragSource::Existing(slot) => self.layout.get(slot).cloned(),
            DragSource::FromDrawer(id) => Some(HomeItem::app(id)),
            DragSource::Widget(kind) => Some(HomeItem::Widget { widget: kind }),
            DragSource::FromFolder { app_id, .. } => Some(HomeItem::app(app_id)),
        }
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
        if matches!(object.get("type").and_then(|value| value.as_str()), Some("con" | "floating_con")) {
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
    use crate::home_state::{HomeLayout as Layout, WidgetKind};

    const WIDTH: u32 = 568;
    const HEIGHT: u32 = 1232;

    fn screen_with(dock: &[Option<&str>]) -> HomeScreen {
        let layout = Layout {
            schema: crate::home_state::SCHEMA,
            dock: dock.iter().map(|entry| entry.map(HomeItem::app)).collect(),
            pages: vec![vec![Some(HomeItem::app("a.desktop")), Some(HomeItem::app("b.desktop")), None, None]],
        };
        HomeScreen::new(layout, WIDTH as f64)
    }

    fn tile_center_for_test(slot: usize) -> (f64, f64) {
        let (x, y, w, h) = home_grid::tile_rect(WIDTH, HEIGHT, slot);
        (x + w / 2.0, y + h / 2.0)
    }

    fn folder_member_point(index: usize) -> (f64, f64) {
        let (x, y, w, h) = home_grid::folder_app_rect(WIDTH, HEIGHT, index);
        (x + w / 2.0, y + h / 2.0)
    }

    #[test]
    fn tap_on_an_icon_launches_it() {
        let mut screen = screen_with(&[None; 4]);
        let point = tile_center_for_test(0);
        screen.down(1, point, 0, WIDTH, HEIGHT);
        assert_eq!(
            screen.up(1, point, 20, WIDTH, HEIGHT),
            Some(HomeAction::Launch("a.desktop".into()))
        );
    }

    #[test]
    fn tap_on_empty_grid_space_does_nothing() {
        let mut screen = screen_with(&[None; 4]);
        let point = tile_center_for_test(2); // unfilled slot
        screen.down(1, point, 0, WIDTH, HEIGHT);
        assert_eq!(screen.up(1, point, 20, WIDTH, HEIGHT), None);
    }

    #[test]
    fn long_press_on_an_icon_enters_rearrange_and_starts_dragging_it() {
        let mut screen = screen_with(&[None; 4]);
        let point = tile_center_for_test(0);
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
        let start = tile_center_for_test(0);
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
    fn drag_swaps_with_the_target_slot_instead_of_overwriting_when_it_holds_the_same_app_twice() {
        // Two identical ids can't happen in practice, but the swap
        // fallback itself is exercised via two distinct *folders*
        // (folders never merge with each other) so this still proves the
        // same-span-swap path independent of the folder-merge path below.
        let mut screen = screen_with(&[None; 4]);
        screen.layout.pages[0][0] = Some(HomeItem::Folder(FolderData { name: "One".into(), apps: vec!["a.desktop".into()] }));
        screen.layout.pages[0][1] = Some(HomeItem::Folder(FolderData { name: "Two".into(), apps: vec!["b.desktop".into()] }));
        let start = tile_center_for_test(0);
        screen.down(1, start, 0, WIDTH, HEIGHT);
        let mut ticks = 0;
        while !screen.rearranging && ticks < 100 {
            screen.tick(16);
            ticks += 1;
        }
        let target = tile_center_for_test(1);
        screen.motion(1, target, 500, WIDTH, HEIGHT);
        assert_eq!(screen.up(1, target, 520, WIDTH, HEIGHT), Some(HomeAction::LayoutChanged));
        assert_eq!(
            screen.layout.get(HomeSlot::Grid { page: 0, slot: 0 }).and_then(HomeItem::as_folder).map(|f| f.name.as_str()),
            Some("Two")
        );
        assert_eq!(
            screen.layout.get(HomeSlot::Grid { page: 0, slot: 1 }).and_then(HomeItem::as_folder).map(|f| f.name.as_str()),
            Some("One")
        );
    }

    #[test]
    fn dragging_one_app_onto_another_on_home_creates_a_folder() {
        let mut screen = screen_with(&[None; 4]);
        let start = tile_center_for_test(0);
        screen.down(1, start, 0, WIDTH, HEIGHT);
        let mut ticks = 0;
        while !screen.rearranging && ticks < 100 {
            screen.tick(16);
            ticks += 1;
        }
        let target = tile_center_for_test(1);
        screen.motion(1, target, 500, WIDTH, HEIGHT);
        assert_eq!(screen.up(1, target, 520, WIDTH, HEIGHT), Some(HomeAction::LayoutChanged));
        assert_eq!(screen.layout.get(HomeSlot::Grid { page: 0, slot: 0 }), None, "source cell cleared");
        let folder = screen.layout.get(HomeSlot::Grid { page: 0, slot: 1 }).and_then(HomeItem::as_folder).expect("a folder now sits at the target");
        assert_eq!(folder.apps, vec!["b.desktop", "a.desktop"]);
    }

    #[test]
    fn dragging_an_app_onto_an_existing_folder_joins_it() {
        let mut screen = screen_with(&[None; 4]);
        screen.layout.pages[0][1] =
            Some(HomeItem::Folder(FolderData { name: "Fun".into(), apps: vec!["b.desktop".into(), "c.desktop".into()] }));
        let start = tile_center_for_test(0);
        screen.down(1, start, 0, WIDTH, HEIGHT);
        let mut ticks = 0;
        while !screen.rearranging && ticks < 100 {
            screen.tick(16);
            ticks += 1;
        }
        let target = tile_center_for_test(1);
        screen.motion(1, target, 500, WIDTH, HEIGHT);
        assert_eq!(screen.up(1, target, 520, WIDTH, HEIGHT), Some(HomeAction::LayoutChanged));
        let folder = screen.layout.get(HomeSlot::Grid { page: 0, slot: 1 }).and_then(HomeItem::as_folder).unwrap();
        assert_eq!(folder.apps, vec!["b.desktop", "c.desktop", "a.desktop"]);
    }

    #[test]
    fn a_folder_left_with_one_app_dissolves_into_it() {
        let mut screen = screen_with(&[None; 4]);
        screen.layout.pages[0][0] =
            Some(HomeItem::Folder(FolderData { name: "Fun".into(), apps: vec!["a.desktop".into(), "b.desktop".into()] }));
        screen.layout.remove_app("a.desktop");
        assert_eq!(screen.layout.get(HomeSlot::Grid { page: 0, slot: 0 }), Some(&HomeItem::app("b.desktop")));
    }

    #[test]
    fn tapping_a_folder_tile_opens_the_overlay_instead_of_launching() {
        let mut screen = screen_with(&[None; 4]);
        screen.layout.pages[0][0] =
            Some(HomeItem::Folder(FolderData { name: "Fun".into(), apps: vec!["a.desktop".into(), "b.desktop".into()] }));
        let point = tile_center_for_test(0);
        screen.down(1, point, 0, WIDTH, HEIGHT);
        assert_eq!(screen.up(1, point, 20, WIDTH, HEIGHT), None);
        assert_eq!(screen.open_folder.as_ref().map(|open| open.slot), Some(HomeSlot::Grid { page: 0, slot: 0 }));
    }

    #[test]
    fn tapping_an_app_inside_an_open_folder_launches_it_and_closes_the_overlay() {
        let mut screen = screen_with(&[None; 4]);
        screen.layout.pages[0][0] =
            Some(HomeItem::Folder(FolderData { name: "Fun".into(), apps: vec!["a.desktop".into(), "b.desktop".into()] }));
        screen.open_folder = Some(OpenFolder { slot: HomeSlot::Grid { page: 0, slot: 0 }, editing_name: false, name_buffer: String::new() });
        let point = home_grid::folder_app_rect(WIDTH, HEIGHT, 1);
        let point = (point.0 + point.2 / 2.0, point.1 + point.3 / 2.0);
        screen.down(1, point, 0, WIDTH, HEIGHT);
        assert_eq!(screen.up(1, point, 20, WIDTH, HEIGHT), Some(HomeAction::Launch("b.desktop".into())));
        assert!(screen.open_folder.is_none());
    }

    #[test]
    fn tapping_outside_the_open_folder_card_closes_it_with_no_action() {
        let mut screen = screen_with(&[None; 4]);
        screen.layout.pages[0][0] =
            Some(HomeItem::Folder(FolderData { name: "Fun".into(), apps: vec!["a.desktop".into(), "b.desktop".into()] }));
        screen.open_folder = Some(OpenFolder { slot: HomeSlot::Grid { page: 0, slot: 0 }, editing_name: false, name_buffer: String::new() });
        let outside = (5.0, 5.0);
        screen.down(1, outside, 0, WIDTH, HEIGHT);
        assert_eq!(screen.up(1, outside, 20, WIDTH, HEIGHT), None);
        assert!(screen.open_folder.is_none());
    }

    #[test]
    fn tapping_the_folder_name_arms_rename_and_apply_persists_it() {
        let mut screen = screen_with(&[None; 4]);
        screen.layout.pages[0][0] =
            Some(HomeItem::Folder(FolderData { name: "Fun".into(), apps: vec!["a.desktop".into(), "b.desktop".into()] }));
        screen.open_folder = Some(OpenFolder { slot: HomeSlot::Grid { page: 0, slot: 0 }, editing_name: false, name_buffer: String::new() });
        let name_rect = home_grid::folder_name_rect(WIDTH, HEIGHT);
        let point = (name_rect.0 + 4.0, name_rect.1 + 4.0);
        screen.down(1, point, 0, WIDTH, HEIGHT);
        assert_eq!(screen.up(1, point, 20, WIDTH, HEIGHT), None);
        assert!(screen.open_folder.as_ref().unwrap().editing_name);
        assert_eq!(screen.open_folder.as_ref().unwrap().name_buffer, "Fun");
        screen.backspace_folder_name();
        screen.backspace_folder_name();
        screen.push_folder_name_char('u');
        screen.push_folder_name_char('n');
        screen.push_folder_name_char('!');
        assert_eq!(screen.apply_folder_rename(), Some(HomeAction::LayoutChanged));
        let folder = screen.layout.get(HomeSlot::Grid { page: 0, slot: 0 }).and_then(HomeItem::as_folder).unwrap();
        assert_eq!(folder.name, "Fun!");
        assert!(!screen.open_folder.as_ref().unwrap().editing_name);
    }

    #[test]
    fn a_widget_can_be_long_pressed_and_dragged_by_touching_any_of_its_cells() {
        let mut screen = screen_with(&[None; 4]);
        screen.layout.pages[0] = vec![None; 8];
        screen.layout.pages[0][0] = Some(HomeItem::Widget { widget: WidgetKind::Clock });
        // Touch the *last* cell the clock covers (slot 7 of an 8-cell,
        // 4-wide/2-row page), not its anchor -- this must still resolve to
        // and drag the whole widget.
        let point = tile_center_for_test(7);
        screen.down(1, point, 0, WIDTH, HEIGHT);
        let mut ticks = 0;
        while !screen.rearranging && ticks < 100 {
            screen.tick(16);
            ticks += 1;
        }
        assert_eq!(screen.drag.as_ref().map(|(source, _)| source.clone()), Some(DragSource::Existing(HomeSlot::Grid { page: 0, slot: 0 })));
    }

    #[test]
    fn dragging_a_widget_over_another_widgets_full_span_shows_no_room() {
        let mut screen = screen_with(&[None; 4]);
        screen.layout.pages[0] = vec![None; 16];
        screen.layout.pages[0][0] = Some(HomeItem::Widget { widget: WidgetKind::Clock }); // covers 0..8
        screen.layout.pages[0][8] = Some(HomeItem::Widget { widget: WidgetKind::Weather }); // covers 8,9,12,13
        let start = tile_center_for_test(8);
        screen.down(1, start, 0, WIDTH, HEIGHT);
        let mut ticks = 0;
        while !screen.rearranging && ticks < 100 {
            screen.tick(16);
            ticks += 1;
        }
        assert!(screen.drag.is_some(), "the weather widget is picked up");
        // Hover over one of the clock's own cells -- its 4x2 span leaves no
        // room anywhere within it for another widget.
        let over_the_clock = tile_center_for_test(1);
        screen.motion(1, over_the_clock, 500, WIDTH, HEIGHT);
        assert_eq!(screen.drop_target(WIDTH, HEIGHT), Some(HomeSlot::Grid { page: 0, slot: 1 }));
        assert!(!screen.drop_target_fits(WIDTH, HEIGHT), "the clock already fully occupies its own span");
        // A plain, unoccupied cell (slot 10, outside both widgets' spans)
        // does have room.
        let empty_cell = tile_center_for_test(10);
        screen.motion(1, empty_cell, 520, WIDTH, HEIGHT);
        assert!(screen.drop_target_fits(WIDTH, HEIGHT), "an empty cell has room for the dragged widget");
    }

    #[test]
    fn already_rearranging_a_fresh_drag_moves_an_icon_without_a_second_long_press() {
        let mut screen = screen_with(&[None; 4]);
        screen.rearranging = true;
        let start = tile_center_for_test(0);
        let target = tile_center_for_test(2);
        screen.down(1, start, 0, WIDTH, HEIGHT);
        assert!(screen.drag.is_some(), "a filled icon is grabbed immediately while rearranging");
        screen.motion(1, target, 20, WIDTH, HEIGHT);
        assert_eq!(
            screen.up(1, target, 40, WIDTH, HEIGHT),
            Some(HomeAction::LayoutChanged)
        );
        assert_eq!(screen.layout.get(HomeSlot::Grid { page: 0, slot: 2 }), Some(&HomeItem::app("a.desktop")));
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
        assert_eq!(screen.layout.get(HomeSlot::Grid { page: 0, slot: 0 }), Some(&HomeItem::app("a.desktop")));
    }

    #[test]
    fn tapping_a_grid_icons_remove_badge_removes_it_without_dragging() {
        let mut screen = screen_with(&[None; 4]);
        screen.rearranging = true;
        let badge = home_grid::plate_top_left(WIDTH, HEIGHT, HomeSlot::Grid { page: 0, slot: 0 });
        screen.down(1, badge, 0, WIDTH, HEIGHT);
        assert!(screen.drag.is_none(), "a badge press never arms a drag");
        assert_eq!(screen.up(1, badge, 20, WIDTH, HEIGHT), Some(HomeAction::LayoutChanged));
        assert_eq!(screen.layout.get(HomeSlot::Grid { page: 0, slot: 0 }), None);
        assert!(screen.rearranging, "removing one icon does not itself end rearrange mode");
    }

    #[test]
    fn tapping_a_dock_icons_remove_badge_removes_it() {
        let mut screen = screen_with(&[Some("dock.desktop"), None, None, None]);
        screen.rearranging = true;
        let badge = home_grid::plate_top_left(WIDTH, HEIGHT, HomeSlot::Dock { slot: 0 });
        screen.down(1, badge, 0, WIDTH, HEIGHT);
        assert_eq!(screen.up(1, badge, 20, WIDTH, HEIGHT), Some(HomeAction::LayoutChanged));
        assert_eq!(screen.layout.get(HomeSlot::Dock { slot: 0 }), None);
    }

    #[test]
    fn a_remove_badge_only_fires_while_rearranging() {
        let mut screen = screen_with(&[None; 4]);
        let point = home_grid::plate_top_left(WIDTH, HEIGHT, HomeSlot::Grid { page: 0, slot: 0 });
        screen.down(1, point, 0, WIDTH, HEIGHT);
        assert_eq!(
            screen.up(1, point, 20, WIDTH, HEIGHT),
            Some(HomeAction::Launch("a.desktop".into()))
        );
    }

    #[test]
    fn drop_target_tracks_the_slot_under_the_dragged_icon() {
        let mut screen = screen_with(&[None; 4]);
        let start = tile_center_for_test(0);
        screen.down(1, start, 0, WIDTH, HEIGHT);
        let mut ticks = 0;
        while !screen.rearranging && ticks < 100 {
            screen.tick(16);
            ticks += 1;
        }
        assert_eq!(screen.drop_target(WIDTH, HEIGHT), Some(HomeSlot::Grid { page: 0, slot: 0 }));
        let target = tile_center_for_test(1);
        screen.motion(1, target, 500, WIDTH, HEIGHT);
        assert_eq!(screen.drop_target(WIDTH, HEIGHT), Some(HomeSlot::Grid { page: 0, slot: 1 }));
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
        let point = tile_center_for_test(2); // unfilled
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
    fn dragging_an_app_into_the_dock_places_it_there() {
        let mut screen = screen_with(&[None; 4]);
        let start = tile_center_for_test(0);
        screen.down(1, start, 0, WIDTH, HEIGHT);
        let mut ticks = 0;
        while !screen.rearranging && ticks < 100 {
            screen.tick(16);
            ticks += 1;
        }
        let (x, y, w, h) = home_grid::dock_rect(WIDTH, HEIGHT, 2);
        let target = (x + w / 2.0, y + h / 2.0);
        screen.motion(1, target, 500, WIDTH, HEIGHT);
        assert_eq!(screen.up(1, target, 520, WIDTH, HEIGHT), Some(HomeAction::LayoutChanged));
        assert_eq!(screen.layout.get(HomeSlot::Dock { slot: 2 }), Some(&HomeItem::app("a.desktop")));
        assert_eq!(screen.layout.get(HomeSlot::Grid { page: 0, slot: 0 }), None);
    }

    #[test]
    fn dragging_an_app_onto_a_dock_folder_joins_it() {
        let mut screen = screen_with(&[None; 4]);
        screen.layout.dock[0] = Some(HomeItem::Folder(FolderData { name: "Dock Folder".into(), apps: vec!["x.desktop".into()] }));
        let start = tile_center_for_test(0);
        screen.down(1, start, 0, WIDTH, HEIGHT);
        let mut ticks = 0;
        while !screen.rearranging && ticks < 100 {
            screen.tick(16);
            ticks += 1;
        }
        let (x, y, w, h) = home_grid::dock_rect(WIDTH, HEIGHT, 0);
        let target = (x + w / 2.0, y + h / 2.0);
        screen.motion(1, target, 500, WIDTH, HEIGHT);
        assert_eq!(screen.up(1, target, 520, WIDTH, HEIGHT), Some(HomeAction::LayoutChanged));
        let folder = screen.layout.get(HomeSlot::Dock { slot: 0 }).and_then(HomeItem::as_folder).unwrap();
        assert_eq!(folder.apps, vec!["x.desktop", "a.desktop"]);
    }

    #[test]
    fn second_contact_cancels_the_first_without_a_stray_action() {
        let mut screen = screen_with(&[None; 4]);
        let point = tile_center_for_test(0);
        screen.down(1, point, 0, WIDTH, HEIGHT);
        screen.down(2, (10.0, 10.0), 5, WIDTH, HEIGHT);
        assert_eq!(screen.up(1, point, 20, WIDTH, HEIGHT), None);
    }

    // -- Drawer long-press-drag hand-off (task 1) --

    #[test]
    fn an_external_drag_from_the_drawer_drops_onto_an_empty_cell() {
        let mut screen = screen_with(&[None; 4]);
        let point = tile_center_for_test(2); // empty
        screen.begin_external_drag("new.desktop".into(), point);
        assert_eq!(screen.dragged_item(), Some(HomeItem::app("new.desktop")));
        assert_eq!(screen.release_drag(point, WIDTH, HEIGHT), Some(HomeAction::LayoutChanged));
        assert_eq!(screen.layout.get(HomeSlot::Grid { page: 0, slot: 2 }), Some(&HomeItem::app("new.desktop")));
    }

    #[test]
    fn an_external_drag_dropped_onto_an_existing_app_creates_a_folder() {
        let mut screen = screen_with(&[None; 4]);
        let point = tile_center_for_test(0); // holds "a.desktop"
        screen.begin_external_drag("new.desktop".into(), point);
        assert_eq!(screen.release_drag(point, WIDTH, HEIGHT), Some(HomeAction::LayoutChanged));
        let folder = screen.layout.get(HomeSlot::Grid { page: 0, slot: 0 }).and_then(HomeItem::as_folder).unwrap();
        assert_eq!(folder.apps, vec!["a.desktop", "new.desktop"]);
    }

    #[test]
    fn an_external_drag_dropped_into_the_dock_places_it_there() {
        let mut screen = screen_with(&[None; 4]);
        let (x, y, w, h) = home_grid::dock_rect(WIDTH, HEIGHT, 1);
        let point = (x + w / 2.0, y + h / 2.0);
        screen.begin_external_drag("new.desktop".into(), point);
        assert_eq!(screen.release_drag(point, WIDTH, HEIGHT), Some(HomeAction::LayoutChanged));
        assert_eq!(screen.layout.get(HomeSlot::Dock { slot: 1 }), Some(&HomeItem::app("new.desktop")));
    }

    #[test]
    fn cancelling_an_external_drag_leaves_the_layout_untouched() {
        let mut screen = screen_with(&[None; 4]);
        let point = tile_center_for_test(2);
        screen.begin_external_drag("new.desktop".into(), point);
        screen.cancel_external_drag();
        assert!(screen.drag.is_none());
        assert!(!screen.layout.contains_app("new.desktop"));
    }

    #[test]
    fn an_external_drag_held_at_the_edge_switches_pages() {
        let mut screen = screen_with(&[None; 4]);
        screen.layout.pages.push(vec![None; 4]);
        screen.begin_external_drag("new.desktop".into(), (WIDTH as f64 - 5.0, 600.0));
        screen.external_drag_motion((WIDTH as f64 - 5.0, 600.0), 0, WIDTH, HEIGHT);
        let mut ticks = 0;
        while screen.pager.page(screen.page_count()) == 0 && ticks < 100 {
            screen.tick(16);
            ticks += 1;
        }
        assert_eq!(screen.pager.page(screen.page_count()), 1);
    }

    #[test]
    fn edge_hold_does_not_switch_before_the_first_dwell_threshold() {
        let mut screen = screen_with(&[None; 4]);
        screen.layout.pages.push(vec![None; 4]);
        screen.begin_external_drag("new.desktop".into(), (WIDTH as f64 - 5.0, 600.0));
        screen.external_drag_motion((WIDTH as f64 - 5.0, 600.0), 0, WIDTH, HEIGHT);
        // Just under the ~350-400ms first-dwell threshold (task 1).
        screen.tick(EDGE_HOLD_FIRST_MS - 20);
        assert_eq!(screen.pager.page(screen.page_count()), 0, "has not switched yet");
        let (side, progress) = screen.drag_edge_indicator().expect("still dwelling at the right edge");
        assert_eq!(side, 1);
        assert!((0.9..1.0).contains(&progress), "close to triggering but not yet: {progress}");
    }

    #[test]
    fn edge_hold_repeats_with_a_shorter_delay_than_the_first_turn() {
        let mut screen = screen_with(&[None; 4]);
        screen.layout.pages.push(vec![None; 4]);
        screen.layout.pages.push(vec![None; 4]);
        screen.begin_external_drag("new.desktop".into(), (WIDTH as f64 - 5.0, 600.0));
        screen.external_drag_motion((WIDTH as f64 - 5.0, 600.0), 0, WIDTH, HEIGHT);
        screen.tick(EDGE_HOLD_FIRST_MS);
        let mut ticks = 0;
        while screen.pager.page(screen.page_count()) == 0 && ticks < 50 {
            screen.tick(16);
            ticks += 1;
        }
        assert_eq!(screen.pager.page(screen.page_count()), 1, "first turn, at the slower first-dwell delay");
        // The repeat delay is shorter than the first: this alone is enough
        // to trigger the second turn, without needing another full
        // first-dwell wait.
        screen.tick(EDGE_HOLD_REPEAT_MS);
        let mut ticks = 0;
        while screen.pager.page(screen.page_count()) == 1 && ticks < 50 {
            screen.tick(16);
            ticks += 1;
        }
        assert_eq!(screen.pager.page(screen.page_count()), 2, "second turn, at the faster repeat delay");
    }

    #[test]
    fn edge_hold_at_the_last_page_creates_a_new_page_instead_of_stalling() {
        let mut screen = screen_with(&[None; 4]);
        assert_eq!(screen.page_count(), 1);
        screen.begin_external_drag("new.desktop".into(), (WIDTH as f64 - 5.0, 600.0));
        screen.external_drag_motion((WIDTH as f64 - 5.0, 600.0), 0, WIDTH, HEIGHT);
        let mut ticks = 0;
        while screen.page_count() < 2 && ticks < 100 {
            screen.tick(30);
            ticks += 1;
        }
        assert_eq!(screen.page_count(), 2, "a brand-new page was created");
        let mut ticks = 0;
        while screen.pager.page(screen.page_count()) == 0 && ticks < 100 {
            screen.tick(16);
            ticks += 1;
        }
        assert_eq!(screen.pager.page(screen.page_count()), 1, "and the pager slides onto it");
        assert!(screen.layout.pages[1].iter().all(Option::is_none), "the new page starts empty");
    }

    #[test]
    fn a_quick_horizontal_fling_mid_drag_pages_immediately_without_an_edge_dwell() {
        let mut screen = screen_with(&[None; 4]);
        screen.layout.pages.push(vec![None; 4]);
        screen.begin_external_drag("new.desktop".into(), (300.0, 600.0));
        screen.external_drag_motion((300.0, 600.0), 0, WIDTH, HEIGHT); // baseline, away from any edge
        // A fast leftward motion (well above the fling threshold, and
        // nowhere near an edge zone) should page over on its own.
        screen.external_drag_motion((100.0, 600.0), 40, WIDTH, HEIGHT);
        let mut ticks = 0;
        while screen.pager.page(screen.page_count()) == 0 && ticks < 50 {
            screen.tick(16);
            ticks += 1;
        }
        assert_eq!(screen.pager.page(screen.page_count()), 1, "flung to the next page without dwelling at an edge");
    }

    // -- Cross-page rearrange drag: release must commit to the NEW page,
    // not revert to the drag's origin page (operator report on real glass:
    // dragging an icon/widget across the edge visibly switches Home to the
    // next page, but lifting the finger snaps it back to where it started).

    /// Drags an existing icon from page 0 to the right edge, ticking until
    /// the edge-hold dwell threshold turns the page, then releases onto an
    /// empty cell on page 1 -- the item must land there, not revert to its
    /// origin slot on page 0.
    #[test]
    fn dragging_an_existing_icon_across_the_edge_lands_on_the_new_page() {
        let mut screen = screen_with(&[None; 4]);
        screen.layout.pages.push(vec![None; 4]); // page 1, all empty
        let start = tile_center_for_test(0); // holds "a.desktop"
        screen.down(1, start, 0, WIDTH, HEIGHT);
        let mut ticks = 0;
        while !screen.rearranging && ticks < 100 {
            screen.tick(16);
            ticks += 1;
        }
        assert!(screen.rearranging);
        // Drag to (and hold at) the right edge until the page turns.
        let edge_point = (WIDTH as f64 - 5.0, 600.0);
        screen.motion(1, edge_point, 500, WIDTH, HEIGHT);
        let mut ticks = 0;
        while screen.pager.page(screen.page_count()) == 0 && ticks < 100 {
            screen.tick(16);
            ticks += 1;
        }
        assert_eq!(screen.pager.page(screen.page_count()), 1, "the page switched while still dragging");
        // Move onto an empty cell on the now-current page 1 and release.
        let drop_point = tile_center_for_test(2);
        screen.motion(1, drop_point, 900, WIDTH, HEIGHT);
        assert_eq!(
            screen.up(1, drop_point, 920, WIDTH, HEIGHT),
            Some(HomeAction::LayoutChanged)
        );
        assert_eq!(
            screen.layout.get(HomeSlot::Grid { page: 1, slot: 2 }),
            Some(&HomeItem::app("a.desktop")),
            "dropped item must land on the new page, not revert to its origin"
        );
        assert_eq!(
            screen.layout.get(HomeSlot::Grid { page: 0, slot: 0 }),
            None,
            "origin cell must be cleared once the drop commits"
        );
    }

    /// Same cross-page drag, but the new page's target cell is already
    /// occupied -- the item must land on the nearest *free* cell on the new
    /// page, not revert to its origin.
    #[test]
    fn dragging_an_existing_icon_across_the_edge_onto_an_occupied_cell_lands_nearby_on_the_new_page() {
        let mut screen = screen_with(&[None; 4]);
        screen.layout.pages.push(vec![
            Some(HomeItem::app("existing.desktop")),
            None,
            None,
            None,
        ]); // page 1, slot 0 occupied
        let start = tile_center_for_test(0); // holds "a.desktop"
        screen.down(1, start, 0, WIDTH, HEIGHT);
        let mut ticks = 0;
        while !screen.rearranging && ticks < 100 {
            screen.tick(16);
            ticks += 1;
        }
        let edge_point = (WIDTH as f64 - 5.0, 600.0);
        screen.motion(1, edge_point, 500, WIDTH, HEIGHT);
        let mut ticks = 0;
        while screen.pager.page(screen.page_count()) == 0 && ticks < 100 {
            screen.tick(16);
            ticks += 1;
        }
        assert_eq!(screen.pager.page(screen.page_count()), 1);
        // Release directly onto page 1's already-occupied slot 0.
        let drop_point = tile_center_for_test(0);
        screen.motion(1, drop_point, 900, WIDTH, HEIGHT);
        let action = screen.up(1, drop_point, 920, WIDTH, HEIGHT);
        assert_eq!(action, Some(HomeAction::LayoutChanged));
        assert_eq!(
            screen.layout.get(HomeSlot::Grid { page: 0, slot: 0 }),
            None,
            "origin cell must be cleared -- the drop did not revert"
        );
        assert!(
            screen.layout.contains_app("a.desktop"),
            "the dragged app must still exist somewhere"
        );
        // "existing.desktop" (or a merged folder with it) must still be at
        // its own slot -- the drop must not have clobbered it.
        let slot0 = screen.layout.get(HomeSlot::Grid { page: 1, slot: 0 }).cloned();
        assert!(
            matches!(slot0, Some(HomeItem::Folder(_))) || slot0 == Some(HomeItem::app("existing.desktop")),
            "unexpected page-1 slot-0 contents: {slot0:?}"
        );
    }

    /// Same cross-page drag, but the finger is released right where it has
    /// been dwelling -- in the edge zone itself -- rather than moved back
    /// toward the grid's center first, matching how a person actually lifts
    /// off after watching the page turn under their finger. The release
    /// point (`width - 5`) sits inside `EDGE_ZONE_PX`'s 40px trigger band
    /// but outside every tile's own hit rect (the grid's `SIDE_MARGIN` is
    /// only 22px), so `slot_at` resolves to no cell at all here -- this is
    /// the exact root cause: `drop_dragged_item`'s `DragSource::Existing`
    /// arm used to `return None` outright on an unresolvable target, with
    /// no same-page fallback (every other drag source already had one),
    /// silently discarding the drop and leaving the item exactly where it
    /// started -- which then reads as "snapped back to its original page".
    #[test]
    fn releasing_right_at_the_edge_where_the_page_just_turned_still_commits_to_the_new_page() {
        let mut screen = screen_with(&[None; 4]);
        screen.layout.pages.push(vec![None; 4]);
        let start = tile_center_for_test(0); // holds "a.desktop"
        screen.down(1, start, 0, WIDTH, HEIGHT);
        let mut ticks = 0;
        while !screen.rearranging && ticks < 100 {
            screen.tick(16);
            ticks += 1;
        }
        let edge_point = (WIDTH as f64 - 5.0, 600.0);
        screen.motion(1, edge_point, 500, WIDTH, HEIGHT);
        let mut ticks = 0;
        while screen.pager.page(screen.page_count()) == 0 && ticks < 100 {
            screen.tick(16);
            ticks += 1;
        }
        assert_eq!(screen.pager.page(screen.page_count()), 1, "the page switched while still dragging");
        assert_eq!(
            home_grid::slot_at(edge_point, WIDTH, HEIGHT, home_grid::apps_per_page(HEIGHT)),
            None,
            "sanity check: this release point must be outside every tile's own hit rect"
        );
        // Release right here, at the edge -- no further motion inward.
        assert_eq!(
            screen.up(1, edge_point, 920, WIDTH, HEIGHT),
            Some(HomeAction::LayoutChanged)
        );
        assert_eq!(
            screen.layout.get(HomeSlot::Grid { page: 0, slot: 0 }),
            None,
            "origin cell must be cleared -- must not have snapped back"
        );
        assert!(
            screen.layout.pages[1].iter().any(|cell| cell.as_ref() == Some(&HomeItem::app("a.desktop"))),
            "the item must have landed somewhere on the new (now-current) page"
        );
    }

    /// A widget dragged across the edge and released onto the new page's
    /// already-occupied cell (a plain app, spanning a different size, so
    /// neither a merge nor a same-span swap applies) must land on the
    /// nearest free cell on that *new* page -- not revert to its origin,
    /// and not clobber the app already there.
    #[test]
    fn dragging_a_widget_across_the_edge_onto_an_incompatible_occupied_cell_lands_nearby_on_the_new_page() {
        let per_page = home_grid::apps_per_page(HEIGHT);
        let mut screen = screen_with(&[None; 4]);
        screen.layout.pages[0] = vec![None; per_page];
        screen.layout.pages[0][0] = Some(HomeItem::Widget { widget: WidgetKind::Clock }); // covers 0..8 (4x2)
        let mut page1 = vec![None; per_page];
        page1[0] = Some(HomeItem::app("existing.desktop"));
        screen.layout.pages.push(page1);

        let start = tile_center_for_test(0); // the widget's anchor cell
        screen.down(1, start, 0, WIDTH, HEIGHT);
        let mut ticks = 0;
        while !screen.rearranging && ticks < 100 {
            screen.tick(16);
            ticks += 1;
        }
        assert_eq!(
            screen.drag.as_ref().map(|(source, _)| source.clone()),
            Some(DragSource::Existing(HomeSlot::Grid { page: 0, slot: 0 }))
        );
        let edge_point = (WIDTH as f64 - 5.0, 600.0);
        screen.motion(1, edge_point, 500, WIDTH, HEIGHT);
        let mut ticks = 0;
        while screen.pager.page(screen.page_count()) == 0 && ticks < 100 {
            screen.tick(16);
            ticks += 1;
        }
        assert_eq!(screen.pager.page(screen.page_count()), 1);
        // Release directly onto page 1's already-occupied slot 0.
        let drop_point = tile_center_for_test(0);
        screen.motion(1, drop_point, 900, WIDTH, HEIGHT);
        assert_eq!(
            screen.up(1, drop_point, 920, WIDTH, HEIGHT),
            Some(HomeAction::LayoutChanged)
        );
        assert_eq!(
            screen.layout.get(HomeSlot::Grid { page: 0, slot: 0 }),
            None,
            "origin cell must be cleared -- the drop did not revert"
        );
        assert_eq!(
            screen.layout.get(HomeSlot::Grid { page: 1, slot: 0 }),
            Some(&HomeItem::app("existing.desktop")),
            "the app already on the new page must be untouched"
        );
        assert_eq!(
            screen.layout.get(HomeSlot::Grid { page: 1, slot: 4 }),
            Some(&HomeItem::Widget { widget: WidgetKind::Clock }),
            "the widget must land on the new page's nearest free cell (row 1, since row 0 has no 4-wide gap left)"
        );
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
                {"type": "floating_con", "app_id": "foot", "id": 22},
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

    // -- Widget picker (coordinator follow-up: "long-press on empty Home space") --

    fn long_press(screen: &mut HomeScreen, point: (f64, f64)) {
        screen.down(1, point, 0, WIDTH, HEIGHT);
        let mut ticks = 0;
        while screen.contact.is_some() && screen.widget_picker.is_none() && screen.drag.is_none() && ticks < 100 {
            screen.tick(16);
            ticks += 1;
        }
    }

    #[test]
    fn long_pressing_empty_home_space_opens_the_widget_picker_menu() {
        let mut screen = screen_with(&[None; 4]);
        let point = tile_center_for_test(2); // unfilled
        long_press(&mut screen, point);
        assert_eq!(screen.widget_picker, Some(WidgetPicker { page: WidgetPickerPage::Menu }));
    }

    #[test]
    fn long_pressing_a_filled_icon_never_opens_the_picker() {
        let mut screen = screen_with(&[None; 4]);
        let point = tile_center_for_test(0); // "a.desktop"
        long_press(&mut screen, point);
        assert!(screen.widget_picker.is_none());
        assert!(screen.rearranging);
    }

    #[test]
    fn tapping_widgets_then_long_pressing_clock_drags_and_places_it() {
        let mut screen = screen_with(&[None; 4]);
        let empty = tile_center_for_test(2);
        long_press(&mut screen, empty);
        assert_eq!(screen.widget_picker, Some(WidgetPicker { page: WidgetPickerPage::Menu }));
        // Release the long-press touch itself somewhere inside the card
        // but below every menu row (a dead zone), before starting a fresh
        // tap on a menu row -- a harmless no-op release, exactly like a
        // real finger lift after the hold that opened the sheet.
        let (card_x, _, card_w, _) = home_grid::picker_rect(WIDTH, HEIGHT);
        let dead_zone = (card_x + card_w / 2.0, 900.0);
        assert_eq!(screen.up(1, dead_zone, 520, WIDTH, HEIGHT), None);
        assert_eq!(screen.widget_picker, Some(WidgetPicker { page: WidgetPickerPage::Menu }), "still on Menu, unmoved by the dead-zone release");
        let row0 = home_grid::picker_row_rect(WIDTH, HEIGHT, 0);
        let row0_point = (row0.0 + row0.2 / 2.0, row0.1 + row0.3 / 2.0);
        screen.down(1, row0_point, 0, WIDTH, HEIGHT);
        assert_eq!(screen.up(1, row0_point, 20, WIDTH, HEIGHT), None);
        assert_eq!(screen.widget_picker, Some(WidgetPicker { page: WidgetPickerPage::Widgets }));
        // Row 1 on the Widgets page is Clock.
        let clock_row = home_grid::picker_row_rect(WIDTH, HEIGHT, 1);
        let clock_point = (clock_row.0 + clock_row.2 / 2.0, clock_row.1 + clock_row.3 / 2.0);
        screen.down(1, clock_point, 0, WIDTH, HEIGHT);
        let mut ticks = 0;
        while screen.drag.is_none() && ticks < 100 {
            screen.tick(16);
            ticks += 1;
        }
        assert_eq!(screen.drag.as_ref().map(|(source, _)| source.clone()), Some(DragSource::Widget(WidgetKind::Clock)));
        assert!(screen.widget_picker.is_none(), "the sheet gets out of the way once the drag starts");
        // Slot 2 (column 2) cannot itself anchor a 4-wide Clock -- it would
        // spill past the row's right edge -- so this drop falls back to
        // `place_first_fit`'s own first fitting cell (see `home_state`'s
        // own span/occupancy tests for that rule); this only asserts the
        // widget lands *somewhere*, not at the literal drop point.
        let drop_point = tile_center_for_test(2);
        assert_eq!(screen.up(1, drop_point, 500, WIDTH, HEIGHT), Some(HomeAction::LayoutChanged));
        assert!(
            screen
                .layout
                .pages
                .iter()
                .flatten()
                .any(|cell| matches!(cell, Some(HomeItem::Widget { widget: WidgetKind::Clock }))),
            "the clock widget was placed somewhere on Home"
        );
    }

    #[test]
    fn a_plain_tap_on_a_widget_preview_does_nothing() {
        let mut screen = screen_with(&[None; 4]);
        screen.widget_picker = Some(WidgetPicker { page: WidgetPickerPage::Widgets });
        let clock_row = home_grid::picker_row_rect(WIDTH, HEIGHT, 1);
        let point = (clock_row.0 + clock_row.2 / 2.0, clock_row.1 + clock_row.3 / 2.0);
        screen.down(1, point, 0, WIDTH, HEIGHT);
        assert_eq!(screen.up(1, point, 20, WIDTH, HEIGHT), None);
        assert!(!screen.layout.pages[0].iter().any(|cell| matches!(cell, Some(HomeItem::Widget { .. }))));
        assert_eq!(screen.widget_picker, Some(WidgetPicker { page: WidgetPickerPage::Widgets }), "still on the same page");
    }

    #[test]
    fn wallpaper_and_style_row_returns_the_action_and_closes_the_sheet() {
        let mut screen = screen_with(&[None; 4]);
        screen.widget_picker = Some(WidgetPicker { page: WidgetPickerPage::Menu });
        let row1 = home_grid::picker_row_rect(WIDTH, HEIGHT, 1);
        let point = (row1.0 + row1.2 / 2.0, row1.1 + row1.3 / 2.0);
        screen.down(1, point, 0, WIDTH, HEIGHT);
        assert_eq!(screen.up(1, point, 20, WIDTH, HEIGHT), Some(HomeAction::OpenWallpaperAndStyle));
        assert!(screen.widget_picker.is_none());
    }

    #[test]
    fn home_settings_back_row_returns_to_the_menu() {
        let mut screen = screen_with(&[None; 4]);
        screen.widget_picker = Some(WidgetPicker { page: WidgetPickerPage::HomeSettings });
        let back = home_grid::picker_row_rect(WIDTH, HEIGHT, 0);
        let point = (back.0 + back.2 / 2.0, back.1 + back.3 / 2.0);
        screen.down(1, point, 0, WIDTH, HEIGHT);
        assert_eq!(screen.up(1, point, 20, WIDTH, HEIGHT), None);
        assert_eq!(screen.widget_picker, Some(WidgetPicker { page: WidgetPickerPage::Menu }));
    }

    #[test]
    fn tapping_outside_the_picker_card_closes_it() {
        let mut screen = screen_with(&[None; 4]);
        screen.widget_picker = Some(WidgetPicker { page: WidgetPickerPage::Menu });
        let outside = (5.0, 5.0);
        screen.down(1, outside, 0, WIDTH, HEIGHT);
        assert_eq!(screen.up(1, outside, 20, WIDTH, HEIGHT), None);
        assert!(screen.widget_picker.is_none());
    }

    // -- Drag an app out of an open folder (coordinator follow-up, task 3) --

    #[test]
    fn dragging_a_member_out_of_an_open_folder_onto_home_removes_and_places_it() {
        let mut screen = screen_with(&[None; 4]);
        screen.layout.pages[0][0] = Some(HomeItem::Folder(FolderData {
            name: "Fun".into(),
            apps: vec!["a.desktop".into(), "b.desktop".into(), "c.desktop".into()],
        }));
        screen.open_folder = Some(OpenFolder { slot: HomeSlot::Grid { page: 0, slot: 0 }, editing_name: false, name_buffer: String::new() });
        let member = folder_member_point(1); // "b.desktop"
        screen.down(1, member, 0, WIDTH, HEIGHT);
        let mut ticks = 0;
        while screen.drag.is_none() && ticks < 100 {
            screen.tick(16);
            ticks += 1;
        }
        assert_eq!(
            screen.drag.as_ref().map(|(source, _)| source.clone()),
            Some(DragSource::FromFolder { folder: HomeSlot::Grid { page: 0, slot: 0 }, app_id: "b.desktop".into() })
        );
        let drop_point = tile_center_for_test(1); // empty grid cell
        assert_eq!(screen.up(1, drop_point, 500, WIDTH, HEIGHT), Some(HomeAction::LayoutChanged));
        assert_eq!(screen.layout.get(HomeSlot::Grid { page: 0, slot: 1 }), Some(&HomeItem::app("b.desktop")));
        let folder = screen.layout.get(HomeSlot::Grid { page: 0, slot: 0 }).and_then(HomeItem::as_folder).unwrap();
        assert_eq!(folder.apps, vec!["a.desktop", "c.desktop"]);
        assert!(screen.open_folder.is_none(), "the overlay closes once the drag leaves it");
    }

    #[test]
    fn dragging_the_last_two_members_leaves_a_dissolved_folder_behind() {
        let mut screen = screen_with(&[None; 4]);
        screen.layout.pages[0][0] = Some(HomeItem::Folder(FolderData {
            name: "Fun".into(),
            apps: vec!["a.desktop".into(), "b.desktop".into()],
        }));
        screen.open_folder = Some(OpenFolder { slot: HomeSlot::Grid { page: 0, slot: 0 }, editing_name: false, name_buffer: String::new() });
        let member = folder_member_point(0); // "a.desktop"
        screen.down(1, member, 0, WIDTH, HEIGHT);
        let mut ticks = 0;
        while screen.drag.is_none() && ticks < 100 {
            screen.tick(16);
            ticks += 1;
        }
        let drop_point = tile_center_for_test(3);
        screen.up(1, drop_point, 500, WIDTH, HEIGHT);
        assert_eq!(screen.layout.get(HomeSlot::Grid { page: 0, slot: 3 }), Some(&HomeItem::app("a.desktop")));
        assert_eq!(screen.layout.get(HomeSlot::Grid { page: 0, slot: 0 }), Some(&HomeItem::app("b.desktop")), "dissolved into the last remaining app");
    }

    #[test]
    fn releasing_a_folder_drag_back_onto_the_folders_own_icon_cancels() {
        let mut screen = screen_with(&[None; 4]);
        screen.layout.pages[0][0] = Some(HomeItem::Folder(FolderData {
            name: "Fun".into(),
            apps: vec!["a.desktop".into(), "b.desktop".into(), "c.desktop".into()],
        }));
        screen.open_folder = Some(OpenFolder { slot: HomeSlot::Grid { page: 0, slot: 0 }, editing_name: false, name_buffer: String::new() });
        let member = folder_member_point(1);
        screen.down(1, member, 0, WIDTH, HEIGHT);
        let mut ticks = 0;
        while screen.drag.is_none() && ticks < 100 {
            screen.tick(16);
            ticks += 1;
        }
        assert!(screen.drag.is_some());
        // Release back onto the folder's own grid slot (its icon), not
        // merely somewhere within the open card's much larger bounds.
        let folder_icon = tile_center_for_test(0);
        assert_eq!(screen.up(1, folder_icon, 500, WIDTH, HEIGHT), None);
        let folder = screen.layout.get(HomeSlot::Grid { page: 0, slot: 0 }).and_then(HomeItem::as_folder).unwrap();
        assert_eq!(folder.apps, vec!["a.desktop", "b.desktop", "c.desktop"], "nothing changed");
        assert!(screen.open_folder.is_some(), "cancelling keeps the overlay open");
    }

    #[test]
    fn a_plain_tap_on_a_folder_member_still_launches_it_without_holding() {
        // Holding-vs-tapping the same member tile must both keep working:
        // a quick release launches (pre-existing behavior), only a genuine
        // hold arms the drag-out.
        let mut screen = screen_with(&[None; 4]);
        screen.layout.pages[0][0] = Some(HomeItem::Folder(FolderData {
            name: "Fun".into(),
            apps: vec!["a.desktop".into(), "b.desktop".into()],
        }));
        screen.open_folder = Some(OpenFolder { slot: HomeSlot::Grid { page: 0, slot: 0 }, editing_name: false, name_buffer: String::new() });
        let member = folder_member_point(0);
        screen.down(1, member, 0, WIDTH, HEIGHT);
        assert_eq!(screen.up(1, member, 20, WIDTH, HEIGHT), Some(HomeAction::Launch("a.desktop".into())));
    }

    #[test]
    fn a_keyboard_inset_shifts_the_folder_cards_own_hit_testing() {
        let mut screen = screen_with(&[None; 4]);
        screen.layout.pages[0][0] =
            Some(HomeItem::Folder(FolderData { name: "Fun".into(), apps: vec!["a.desktop".into()] }));
        screen.open_folder = Some(OpenFolder { slot: HomeSlot::Grid { page: 0, slot: 0 }, editing_name: false, name_buffer: String::new() });
        screen.set_keyboard_inset(40.0);
        let name_rect = home_grid::folder_name_rect_inset(WIDTH, HEIGHT, 40.0);
        let point = (name_rect.0 + 4.0, name_rect.1 + 4.0);
        screen.down(1, point, 0, WIDTH, HEIGHT);
        assert_eq!(screen.up(1, point, 20, WIDTH, HEIGHT), None);
        assert!(screen.open_folder.as_ref().unwrap().editing_name, "hit the shifted name rect, not the un-inset one");
    }
}
