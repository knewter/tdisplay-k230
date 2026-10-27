//! Touch hit regions and visible data for the transient Settings/shade panels.
//! Service I/O remains in `service_data::ServiceWorker` off the Wayland loop.

use crate::{
    catalog::AppEntry,
    navigation::{self, list_top, GRID_BOTTOM_INSET},
    home_widgets::battery::BatteryState,
    pipewire_ipc::GraphSnapshot,
    render::{
        settings_confirm_layout, settings_row_y, POWER_BUTTON_H, POWER_CANCEL_Y,
        POWER_CONFIRM_SLOP, POWER_CONFIRM_Y, POWER_OFF_Y, POWER_REBOOT_Y, SETTINGS_KEY_BACKLIGHT_ROW,
        settings_layout_for, settings_power_card_h, settings_row_h,
    },
    service_data::{
        ActionOutcome, ControlState, NotificationSnapshot, PowerAction, Priority, ServiceRequest,
        SettingsSnapshot,
    },
    slider,
    wifi_ui::WifiPublic,
    Route,
};
use std::time::Instant;

#[derive(Clone, Debug)]
pub struct Confirmation {
    pub token: String,
    pub action: PowerAction,
    pub label: String,
    pub expires_at: Instant,
}

#[derive(Clone, Debug, Default)]
pub struct ServiceView {
    pub settings: Option<SettingsSnapshot>,
    pub notifications: Option<NotificationSnapshot>,
    pub settings_error: Option<String>,
    pub notification_error: Option<String>,
    pub message: Option<String>,
    pub confirmation: Option<Confirmation>,
    pub notification_scroll: f64,
    /// How far the Settings body has scrolled under its header; nonzero only
    /// when a larger vision step makes the rows taller than the panel.
    pub settings_scroll: f64,
    /// How far Help has scrolled; nonzero only when a larger vision step
    /// makes its wrapped text taller than the output.
    pub help_scroll: f64,
    /// Active, single-contact history drag. Never used for a critical row.
    pub notification_swipe: Option<NotificationSwipe>,
    pub wifi: Option<WifiPublic>,
    /// Set only by an image that includes the compositor keyboard gestures.
    pub keyboard_gesture_hint: bool,
    /// Transient opt-in view, never a persistent navigation preference or bar.
    pub navigation_aid: bool,
    pub help_home_pending: bool,
    /// The PipeWire graph's own state (default sink, other sinks, and
    /// per-app streams), fed by `pipewire_ipc::spawn_monitor`'s background
    /// reader -- `None` until the first dump/monitor snapshot arrives, or
    /// if the monitor child never started/died (`audio_error` explains
    /// which). Unlike `settings`, this is never requested/refreshed by a
    /// `ServiceRequest` -- the monitor is already event-driven and always
    /// current, so there is nothing for a request/reply round trip to add.
    pub audio: Option<GraphSnapshot>,
    /// Set once the monitor child could not be spawned or exited, so the
    /// volume row/HUD can show "unavailable" instead of silently drawing
    /// nothing (mirrors `settings_error`'s own role for the k230-settings
    /// path).
    pub audio_error: Option<String>,
    /// The keyboard base's fuel gauge for the shade; `Absent` hides the
    /// battery text entirely (`keyboard_base`, `home_widgets::battery`).
    pub battery: BatteryState,
    /// `Some(preference)` only while the base's key backlight LED exists;
    /// `None` hides Settings' Key backlight row and its tap.
    pub key_backlight: Option<crate::keyboard_base::KeyBacklight>,
    /// The modem service's state, `Some` only once the modem has answered;
    /// `None` hides the shade's indicators and Settings' Cellular and
    /// Location rows (`modem`).
    pub modem: Option<crate::modem::ModemStatus>,
    /// The open Cellular or Location page, if any (`modem_ui`).
    pub modem_page: Option<crate::modem_ui::ModemPublic>,
    /// The open About or Date & time page, if any (`device_info`).
    pub info_page: Option<crate::device_info::InfoPublic>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct NotificationSwipe {
    pub event_id: u64,
    pub row_index: usize,
    pub offset: f64,
}

impl ServiceView {
    /// A full worker queue must not consume the only live confirmation token.
    pub fn request_queued(&mut self, request: &ServiceRequest, accepted: bool) -> bool {
        if accepted
            && matches!(
                request,
                ServiceRequest::PowerConfirm(_) | ServiceRequest::PowerCancel(_)
            )
        {
            self.confirmation = None;
            self.message = Some("Working…".into());
            true
        } else {
            false
        }
    }
}

/// A failed outcome's helper code stays in the log; the person sees the
/// recovery copy and `exit`, the surface's own visible way back.
pub fn action_message(outcome: &ActionOutcome, exit: &str) -> String {
    if let Some(code) = outcome.error.as_deref() {
        let state = crate::recovery::action_error_state(code);
        let label = if outcome.retry {
            crate::recovery::RecoveryAction::Retry.label()
        } else {
            exit
        };
        return state.message(Some(label));
    }
    outcome.label.clone().unwrap_or_else(|| outcome.state.clone())
}

/// The drawer's own search field state: a plain query string and whether
/// the on-screen keyboard is currently up. Deliberately holds nothing
/// about *which* apps match -- `filter_app_indices` recomputes that
/// fresh from the live catalog every time it is asked, which is cheap
/// enough (a linear scan of a bounded, at most 128-entry catalog,
/// `catalog::scan_apps`'s own cap) that caching the match set separately
/// would only be complexity, not a real saving; the *expensive* part this
/// exists to keep off the hot path -- painting -- is cached elsewhere
/// (`render::DrawerGridCache`, keyed in part on this same query string).
#[derive(Clone, Debug, Default, PartialEq)]
pub struct DrawerSearch {
    pub query: String,
    pub focused: bool,
    /// Height reserved by the shared system keyboard, in output logical pixels.
    pub keyboard_inset: f64,
    /// Focused by the base's LILYGO key rather than a tap: typing goes
    /// straight to the query, the on-screen keyboard stays down, Enter
    /// launches the first match and Esc clears, then closes.
    pub from_keys: bool,
}

/// What a key did to a key-focused drawer search (`DrawerSearch::key_action`).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SearchKey {
    Ignored,
    Edited,
    /// Launch the first match.
    Launch,
    /// Close the drawer.
    Close,
}

impl DrawerSearch {
    /// The base key's entry: focus without the on-screen keyboard.
    pub fn focus_from_keys(&mut self) {
        self.focused = true;
        self.from_keys = true;
    }

    /// `key_event`, plus Enter and Esc's meanings when the base's key
    /// focused the field.
    pub fn key_action(&mut self, keysym: u32, utf8: Option<&str>) -> SearchKey {
        if self.focused && self.from_keys {
            match keysym {
                0xff0d | 0xff8d if !self.query.is_empty() => return SearchKey::Launch,
                0xff0d | 0xff8d => return SearchKey::Ignored,
                0xff1b if !self.query.is_empty() => {
                    self.query.clear();
                    return SearchKey::Edited;
                }
                0xff1b => return SearchKey::Close,
                _ => {}
            }
        }
        if self.key_event(keysym, utf8) { SearchKey::Edited } else { SearchKey::Ignored }
    }

    /// Applies ordinary Wayland text and control keys only while Search owns focus.
    /// This public query is independent of Wi-Fi's secret password state.
    pub fn key_event(&mut self, keysym: u32, utf8: Option<&str>) -> bool {
        if !self.focused { return false; }
        match keysym {
            0xff08 => { self.query.pop(); }
            0xff0d | 0xff8d | 0xff1b => self.unfocus(),
            _ => {
                let Some(text) = utf8 else { return false; };
                if text.is_empty() || text.chars().any(char::is_control)
                    || self.query.len().saturating_add(text.len()) > 256 {
                    return false;
                }
                self.query.push_str(text);
            }
        }
        true
    }

    /// List geometry shares the actual configured wvkbd height, not a custom keypad.
    pub fn viewport_height(&self, height: u32) -> u32 {
        let inset = if self.keyboard_inset.is_finite() {
            self.keyboard_inset.clamp(0.0, f64::from(height))
        } else { 0.0 };
        height.saturating_sub(inset.ceil() as u32)
    }

    /// Opens the field: focuses it and shows the keyboard. A no-op if
    /// already focused (never clears an in-progress query).
    pub fn focus(&mut self) {
        self.focused = true;
        self.from_keys = false;
    }

    /// Closes the keyboard without clearing the query -- the filtered grid
    /// stays exactly as typed.
    pub fn unfocus(&mut self) {
        self.focused = false;
        self.from_keys = false;
        self.keyboard_inset = 0.0;
    }

    /// Clears the query entirely (the field's own trailing "clear" tap) but
    /// leaves focus/keyboard state alone.
    pub fn clear(&mut self) {
        self.query.clear();
    }
}

/// Every catalog index (not a filtered clone -- the caller already owns
/// `apps`, and `DrawerAction::Launch`/`LongPress` need the *filtered
/// display position* to map back to one of these, so returning indices
/// rather than entries keeps that mapping trivial: `matches[display_index]`)
/// whose name contains `query`, case-insensitively, as a substring
/// (covers a prefix match too, since a prefix is a substring). An empty
/// query matches everything, in catalog order, unfiltered. This is the
/// entire cost of "searching": a single linear pass over a bounded
/// (`catalog::scan_apps` caps at 128) list of short strings -- cheap
/// enough to redo on every keystroke without its own cache, unlike the
/// *painting* of the results (`render::DrawerGridCache`).
pub fn filter_app_indices(apps: &[AppEntry], query: &str) -> Vec<usize> {
    if query.is_empty() {
        return (0..apps.len()).collect();
    }
    let needle = query.to_lowercase();
    apps.iter()
        .enumerate()
        .filter(|(_, app)| app.name.to_lowercase().contains(&needle))
        .map(|(index, _)| index)
        .collect()
}

#[derive(Clone, Debug, PartialEq)]
pub enum PanelIntent {
    Hide,
    OpenSettings,
    OpenWifi,
    OpenCellular,
    OpenLocation,
    /// Settings' Date & time and About rows (`device_info`).
    OpenDateTime,
    OpenAbout,
    Help(crate::help::Action),
    Request(ServiceRequest),
    /// Flip the key backlight preference (a local file write, not a
    /// `k230-settings` request; see `keyboard_base`).
    ScrollNotifications(f64),
    /// The wide Shade's Location tile: flips GNSS in place through the
    /// modem worker, as the Location page's switch does.
    ToggleLocation,
}

/// Room for the shared brightness slider (task: "brightness should be a
/// slider" -- Android-style, at the top of the shade, same as the
/// Settings row's own) pushed everything below it down by 76px from the
/// old `186.0`/`266.0` (`SHADE_SLIDER_TOP` + `SHADE_SLIDER_H` + a 16px
/// gap, starting clear of the "Dismiss all" tap zone above it) -- see the
/// Shade paint arm in `render.rs` for the shifted preview-card literals
/// this cascades to.
/// A second slider (task: "volume slider in the shade under the
/// brightness slider") pushed everything below it down by another 76px
/// (`SHADE_SLIDER_H` + a 20px gap, the exact rhythm brightness's own
/// slider already established) -- from `342.0` to `418.0`.
/// The quick-toggle row (keyboard show/hide) and the 99 px tap floor
/// (`SHADE_TAP_MIN`) moved everything below "Dismiss all" down again: the
/// list now starts under the toggle band (`SHADE_TOGGLE_TOP` +
/// `shade_toggle_h()`) with a 19px gap -- from `418.0` to `480.0`.
/// A larger vision step grows the toggle (`shade_toggle_h`), so the list
/// moves down with it.
pub fn notification_top() -> f64 {
    SHADE_TOGGLE_TOP + shade_toggle_h() + 19.0
}
pub const NOTIFICATION_ROW: f64 = 116.0;

/// A notification row's pitch at the current vision text step: room for
/// its source (Label), summary (Body) and body or error (Caption) lines,
/// never less than `NOTIFICATION_ROW`.
pub fn notification_row() -> f64 {
    use crate::render::{TYPE_BODY, TYPE_CAPTION, TYPE_LABEL};
    let lines = (TYPE_LABEL + TYPE_BODY + TYPE_CAPTION) * crate::layout_text_scale() * 1.25;
    // 13 above the source, 4 between lines, 13 below, the 8 px gutter.
    (13.0_f64 + lines + 8.0 + 13.0 + 8.0).ceil().max(NOTIFICATION_ROW)
}

/// The Shade sheet's height: 65% of the output, as on the portrait panel,
/// but never so short that the notification list (which starts at the
/// fixed `notification_top()`) has no row of its own -- the landscape panel's
/// 568px height would otherwise end the sheet above the list. Capped at
/// the output's own height.
pub fn shade_panel_height(height: u32) -> f64 {
    let h = f64::from(height);
    (h * 0.65).max((notification_top() + notification_row() + 24.0).min(h))
}
/// Width of the wide Shade's left column (header, sliders); the notification
/// list takes the rest of the landscape panel.
pub const SHADE_WIDE_CONTROLS_W: f64 = 480.0;
/// Top of the wide Shade's list: under its own "Notifications" heading and
/// "Dismiss all" band (`0..SHADE_SETTINGS_BOTTOM` in the list column).
pub const SHADE_WIDE_LIST_TOP: f64 = SHADE_SETTINGS_BOTTOM;
/// The wide Shade's status line (battery, Wi-Fi, modem glyphs), between the
/// time header and the tiles. Text only, never a target.
pub const SHADE_WIDE_STATUS_TOP: f64 = SHADE_SETTINGS_BOTTOM;
/// The first row of quick tiles, under the status line.
pub const SHADE_WIDE_TILE_TOP: f64 = 152.0;
pub const SHADE_WIDE_TILE_GAP: f64 = 12.0;

/// The wide Shade's quick tiles, in grid order (two per row).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ShadeTile {
    Wifi,
    Keyboard,
    Location,
    Cellular,
}

/// The tiles the wide Shade shows: Location and Cellular only once the
/// modem has answered (`ServiceView::modem`), as on the Settings page.
pub fn shade_tiles(view: &ServiceView) -> Vec<ShadeTile> {
    let mut tiles = vec![ShadeTile::Wifi, ShadeTile::Keyboard];
    if view.modem.is_some() {
        tiles.extend([ShadeTile::Location, ShadeTile::Cellular]);
    }
    tiles
}

/// A tile's height: the keyboard toggle's own rule, so a larger vision step
/// grows it and it never drops under the tap floor, capped so two rows and
/// both sliders still fit the 568 px column (the tile's text shrinks to fit).
pub const SHADE_TILE_MAX_H: f64 = 112.0;
pub fn shade_tile_h() -> f64 {
    shade_toggle_h().min(SHADE_TILE_MAX_H)
}

/// Tile `index`'s rect `(x, y, w, h)` in a `controls_w` column: two columns
/// inside 24 px margins, rows `shade_tile_h()` apart plus the gap.
pub fn shade_tile_rect(index: usize, controls_w: f64) -> (f64, f64, f64, f64) {
    let w = (controls_w - 48.0 - SHADE_WIDE_TILE_GAP) / 2.0;
    let h = shade_tile_h();
    let x = 24.0 + (index % 2) as f64 * (w + SHADE_WIDE_TILE_GAP);
    let y = SHADE_WIDE_TILE_TOP + (index / 2) as f64 * (h + SHADE_WIDE_TILE_GAP);
    (x, y, w, h)
}

/// The wide Shade's slider stack starts under the two tile rows, whether or
/// not the second row is shown, so the sliders never move with the modem.
pub fn shade_wide_slider_top() -> f64 {
    SHADE_WIDE_TILE_TOP + 2.0 * (shade_tile_h() + SHADE_WIDE_TILE_GAP) + 4.0
}

/// How far the wide Shade moves the sliders from their portrait bands
/// (`SHADE_SLIDER_TOP`, `SHADE_VOLUME_TOP`); `settings_slider_y` maps a
/// touch back by it, and `render.rs` paints with it.
pub fn shade_slider_shift(wide: bool) -> f64 {
    if wide {
        shade_wide_slider_top() - SHADE_SLIDER_TOP
    } else {
        0.0
    }
}

/// The tile under `pos` on the wide Shade, if any.
pub fn shade_tile_at(pos: (f64, f64), layout: &ShadeLayout, view: &ServiceView) -> Option<ShadeTile> {
    if !layout.wide {
        return None;
    }
    shade_tiles(view).into_iter().enumerate().find_map(|(index, tile)| {
        let (x, y, w, h) = shade_tile_rect(index, layout.controls_w);
        (pos.0 >= x && pos.0 < x + w && pos.1 >= y && pos.1 < y + h).then_some(tile)
    })
}

/// Where the Shade's pieces sit. Portrait and HDMI outputs keep the single
/// column (the controls over the list, which starts at `notification_top()`);
/// the landscape panel (`help::wide`) puts the controls in a left column and
/// the notification list beside them at its full height, so several rows are
/// reachable. `render.rs` paints and every hit-test reads from this one
/// struct, so a tap and its paint cannot drift apart.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ShadeLayout {
    pub wide: bool,
    /// Width of the header and slider column (the whole panel when not wide).
    pub controls_w: f64,
    /// Screen x of the list's own origin; its cards sit 24 px inside it.
    pub list_x: f64,
    pub list_w: f64,
    pub list_top: f64,
    pub list_bottom: f64,
}

pub fn shade_layout(width: u32, height: u32) -> ShadeLayout {
    let w = f64::from(width);
    if crate::help::wide(width, height) {
        ShadeLayout {
            wide: true,
            controls_w: SHADE_WIDE_CONTROLS_W,
            list_x: SHADE_WIDE_CONTROLS_W,
            list_w: w - SHADE_WIDE_CONTROLS_W,
            list_top: SHADE_WIDE_LIST_TOP,
            list_bottom: shade_panel_height(height) - 24.0,
        }
    } else {
        ShadeLayout {
            wide: false,
            controls_w: w,
            list_x: 0.0,
            list_w: w,
            list_top: notification_top(),
            list_bottom: shade_panel_height(height) - 24.0,
        }
    }
}

impl ShadeLayout {
    /// Whether a touch at `pos` starts on the notification list's own region
    /// (below its top and, when wide, right of the controls column).
    pub fn in_list(&self, pos: (f64, f64)) -> bool {
        pos.1 >= self.list_top && pos.0 >= self.list_x
    }
}

/// The shell's tap floor on this panel: 48dp at ~2.07 px/dp is ~99 logical
/// px (`docs/design/shell-ux-critique.md` §7). Every Shade *tap* target's
/// hit band is at least this tall; the sliders are drag bands and keep
/// `slider::TOUCH_TARGET_PX`.
pub const SHADE_TAP_MIN: f64 = 99.0;
/// The Settings entry's band: everything above "Dismiss all" at the
/// header's right.
pub const SHADE_SETTINGS_BOTTOM: f64 = 112.0;
/// Width of the Settings and "Dismiss all" bands at the header's right:
/// 180 px at 100%, wider at a larger vision step so the larger link text
/// stays inside its own target, never more than half the column.
pub fn shade_link_w(controls_w: f64) -> f64 {
    (180.0 * crate::layout_text_scale()).min(controls_w * 0.5).max(180.0)
}
/// "Dismiss all"'s band, directly under the Settings entry and
/// `SHADE_TAP_MIN` tall (it was `116.0..190.0`, 74 px).
pub const SHADE_DISMISS_TOP: f64 = SHADE_SETTINGS_BOTTOM;
pub const SHADE_DISMISS_BOTTOM: f64 = SHADE_DISMISS_TOP + SHADE_TAP_MIN;
/// The Shade's own slider band -- starts below the "Dismiss all" tap
/// zone (`SHADE_DISMISS_TOP..SHADE_DISMISS_BOTTOM`) so the two never
/// overlap, and is at least `slider::TOUCH_TARGET_PX` tall.
pub const SHADE_SLIDER_TOP: f64 = SHADE_DISMISS_BOTTOM + 3.0;
pub const SHADE_SLIDER_H: f64 = 56.0;
/// The volume slider's own band, directly under the brightness slider
/// with the same 20px gap `notification_top()`'s own shift already
/// accounts for.
pub const SHADE_VOLUME_TOP: f64 = SHADE_SLIDER_TOP + SHADE_SLIDER_H + 20.0;
pub const SHADE_VOLUME_H: f64 = 56.0;
/// The keyboard quick toggle's band, under the volume slider: the same
/// `KeyboardToggle` request and `ControlState` gate as Settings' Keyboard
/// row, so the two cannot disagree.
pub const SHADE_TOGGLE_TOP: f64 = SHADE_VOLUME_TOP + SHADE_VOLUME_H + 16.0;
/// The toggle's band: the tap floor, or room for its Label and Body lines
/// (drawn 1.2 lines high, 10 px above and below, inside a card 8 px
/// shorter than the band) at the current vision step.
pub fn shade_toggle_h() -> f64 {
    let lines = (crate::render::TYPE_LABEL + crate::render::TYPE_BODY) * crate::layout_text_scale() * 1.2;
    (8.0_f64 + 20.0 + lines).ceil().max(SHADE_TAP_MIN)
}
/// The Settings row index the volume slider paints/hit-tests at --
/// directly after Brightness (row 1), before Keyboard/Motion, which both
/// shift down one row (`render.rs`'s own `SETTINGS_ROW_COUNT` bump).
pub const SETTINGS_VOLUME_ROW: u32 = 2;
const SWIPE_START: f64 = 18.0;
pub const SWIPE_COMMIT: f64 = 85.0;
const SWIPE_TRAVEL: f64 = 160.0;
pub const SWIPE_VERTICAL_CANCEL: f64 = 45.0;

/// The single dismiss gesture shared by every top-anchored overlay sheet
/// (Shade, Settings and its sub-pages): drag back up, toward the top edge
/// each of them opened from. `docs/design/shell-ux-critique.md` S2 found
/// Settings using the opposite (downward) direction from Shade despite
/// both sheets sharing the same top anchor and entry path (Settings opens
/// from within the shade's own downward pull) -- a one-off inconsistency,
/// not two legitimate conventions, so both routes read these same two
/// constants rather than each hand-rolling its own threshold. The Drawer
/// (`navigation.rs`) is a *bottom*-anchored sheet and correctly keeps its
/// own reversed convention (drag down, at the top of its already-scrolled
/// content, to send it back toward the bottom edge it rose from).
const OVERLAY_DISMISS_ZONE_Y: f64 = 180.0;
const OVERLAY_DISMISS_DY: f64 = -90.0;

/// A touch that never clears this many pixels of upward travel from its
/// start is still a tap (or an unrelated wobble) candidate, not a close
/// drag -- the same small-slop convention `TAP_SLOP` already uses elsewhere
/// in this shell (`home_pager.rs`, `theme_carousel.rs`), reused vertically
/// here instead of a fourth copy of the same number.
pub const CLOSE_DRAG_SLOP: f64 = 8.0;
/// Below this revealed fraction, a release commits to closing rather than
/// springing back open.
pub const CLOSE_DISMISS_PROGRESS: f64 = 0.6;
/// An upward release at or above this speed (px/ms) commits to closing
/// regardless of how far the panel had actually moved -- a decisive flick
/// dismisses even from near the top. Not board-derived; a deliberately
/// generous "clearly a flick, not a drift" pick, in the same units and
/// clamp range (`panel_scroll_velocity`) this panel's own scroll drag
/// already sits in.
pub const CLOSE_FLING_VELOCITY: f64 = 0.8;

/// Which sign of `dy` is "closing" for `route`'s own sheet: the top-
/// anchored Shade/Settings close by dragging up (`dy` negative), the
/// bottom-anchored Drawer (`navigation.rs`) closes by dragging down (`dy`
/// positive) -- the one place that direction difference lives, so
/// `close_drag_progress`/`close_drag_engaged` share one shape instead of
/// each route re-deriving its own mirrored copy.
fn close_direction(route: Route) -> f64 {
    if route == Route::Drawer {
        1.0
    } else {
        -1.0
    }
}

/// Live progress for an in-flight close drag: 1.0 where the drag began
/// (fully open) down to 0.0 once the finger has pulled the panel entirely
/// away in its own closing direction (`close_direction`) by a full
/// `panel_travel`. A move in the *opposite* direction only ever pushes
/// progress back *toward* 1.0 (clamped there, never past it) -- "a
/// [downward] drag during a close drag just moves the panel back [down]"
/// (Shade's own wording; Drawer's is the mirror image) falls out of the
/// clamp, not a special case.
pub fn close_drag_progress(route: Route, dy: f64, panel_travel: f64) -> f64 {
    (1.0 - (dy * close_direction(route)) / panel_travel.max(1.0)).clamp(0.0, 1.0)
}

/// The small-slop + direction lock that turns a touch already in an
/// eligible zone (`close_drag_zone`/the Drawer's own) into a *live* close
/// drag, mirrored from the same tap-vs-drag convention
/// `DrawerNavigation`/`notification_swipe_start` use (a minimum travel
/// before committing, dominant along the axis that matters) rather than
/// reacting to the very first pixel of motion. A touch that never clears
/// this must still resolve as an ordinary tap/scroll at release
/// (`panel_intent`, or the Drawer's own tap/long-press/scroll), not a
/// partial drag.
pub fn close_drag_engaged(route: Route, dx: f64, dy: f64) -> bool {
    dy * close_direction(route) >= CLOSE_DRAG_SLOP && dy.abs() > dx.abs()
}

/// Whether a close-drag candidate has moved clearly the other way (a
/// vertical drag away from closing), so a scrolling Settings page or Help
/// gets the gesture instead.
pub fn close_drag_refused(route: Route, dx: f64, dy: f64) -> bool {
    matches!(route, Route::Settings | Route::Help)
        && -dy * close_direction(route) >= CLOSE_DRAG_SLOP
        && dy.abs() > dx.abs()
}

/// Where a close drag may originate: the existing top dismiss zone, or at
/// or after the panel's own bottom edge -- the dim backdrop below it,
/// which also covers grabbing right at ("the panel's bottom edge/handle").
/// Both zones sit outside every scrollable/interactive region either route
/// paints (the notification list starts at `notification_top()`, well below
/// the dismiss zone, and `panel_intent`'s own fall-through already shows
/// nothing is hit-tested at or below `panel_travel` today), so a drag
/// starting here can never race a list scroll or a Settings control.
pub fn close_drag_zone(route: Route, y: f64, panel_travel: f64) -> bool {
    matches!(route, Route::Shade | Route::Settings | Route::Power | Route::Help)
        && (y < OVERLAY_DISMISS_ZONE_Y || y >= panel_travel)
}

/// The Drawer's own top chrome (handle + search field), from its panel
/// edge (`navigation::panel_top`) down to where the grid begins
/// (`navigation::list_top`) -- always an eligible drag-to-close start,
/// the same way Shade's dismiss zone is regardless of scroll. This used
/// to be a slim strip carved out of a much taller prose header (`docs/
/// design/app-drawer-review.md`'s bug-fix pass); the redesign's whole top
/// chrome is now this short and entirely interactive (a drag handle and a
/// tappable search field, nothing a scrolling thumb would brush past
/// accidentally), so the whole thing can be the handle zone again without
/// reintroducing the original problem.
pub fn drawer_handle_zone(y: f64, height: u32) -> bool {
    y >= navigation::panel_top(height) && y < list_top(height)
}

/// Where a Drawer close drag may originate: its own top chrome
/// (`drawer_handle_zone`, always eligible regardless of scroll, the same
/// way Shade's dismiss zone is), or the tile grid itself once already
/// scrolled to its own top (mirrors `DrawerNavigation::up`'s pre-existing
/// "dy > 110 && scroll <= 0.5" release check, now live instead of
/// release-only, so an ordinary scroll away from the top is never
/// hijacked). The dock band (`GRID_BOTTOM_INSET`) is excluded -- its
/// pinned tiles must stay tappable. The Drawer has no backdrop above it
/// today (unlike Shade/Settings; `apply_tray_backdrop` only covers those
/// two), so there is no third "backdrop" zone here.
///
/// This is only the *start*-zone test. Whether a touch that started here
/// stays eligible for the rest of its gesture is a separate question
/// (`drawer_close_candidate_after_scroll`) -- the grid sub-zone here only
/// ever reflects the scroll at the moment the finger went down, not
/// wherever the same continuous drag later carries it.
pub fn drawer_close_drag_zone(y: f64, height: u32, scroll: f64) -> bool {
    let header_bottom = list_top(height);
    let dock_top = f64::from(height) - GRID_BOTTOM_INSET;
    drawer_handle_zone(y, height) || (y >= header_bottom && y < dock_top && scroll <= 0.5)
}

/// Whether a Drawer close-drag candidate established at touch-down
/// (`drawer_close_drag_zone`, gated by the caller on "not already active"
/// and "no fling in flight") survives an ordinary motion sample that just
/// ran `DrawerNavigation::motion` instead of engaging a close.
///
/// Bug this exists to prevent: a touch that starts eligible because the
/// grid is at its own top (`scroll <= 0.5`) stays flagged eligible for its
/// *entire* gesture under the old logic, decided once at touch-down and
/// never revisited. So scrolling away from the top and then reversing
/// direction within that same held touch -- exactly "scroll down, then
/// swipe down again to scroll back up" -- could cross the close-drag slop
/// relative to the *original* touch-down point and engage a close, even
/// though the grid was no longer anywhere near its top. Real scrolling
/// away from the top must permanently disqualify the rest of that
/// gesture from closing; reversing back toward the top later must keep
/// scrolling, never convert into a close (Android's own behaviour, and
/// the literal bug report this fixes).
pub fn drawer_close_candidate_after_scroll(candidate: bool, scroll: f64) -> bool {
    candidate && scroll <= 0.5
}

/// Whether an upward drag that starts at `y` on the Shade panel itself
/// may close the sheet. Anywhere on the panel qualifies, except on the
/// notification list while it can still scroll further up: there the drag
/// keeps scrolling the list, as it does today.
pub fn shade_panel_close_zone(pos: (f64, f64), width: u32, height: u32, view: &ServiceView) -> bool {
    let y = pos.1;
    let in_controls = settings_slider_column_hit(Route::Shade, width, height, pos.0);
    let slider_y = settings_slider_y(Route::Shade, y, width, height);
    if in_controls && (slider_band(Route::Shade, slider_y, view) || volume_slider_band(Route::Shade, slider_y, view)) {
        // Owned entirely by the brightness or volume slider (task: "a
        // horizontal drag on the slider must not start a close drag") --
        // regardless of which way the touch actually moves, matching
        // `Carousel`'s own "owns whichever gesture starts inside its
        // band" rule.
        return false;
    }
    if notification_index(pos, width, height, view).is_none() {
        return true;
    }
    let count = view.notifications.as_ref().map_or(0, |items| items.events.len());
    view.notification_scroll >= notification_max_scroll(count, width, height) - 0.5
}

/// Which routes' touches at `y` land on the shared brightness slider (the
/// Settings row, or the Shade's own header band): a touch starting here
/// belongs entirely to the slider for the rest of the gesture -- a
/// horizontal drag sets the value, tap-to-jump included -- and must never
/// be promoted into a close drag or (on Shade) a notification scroll/
/// swipe, no matter which way it later moves. Gated on the control
/// actually being writable: when brightness is unavailable, no slider is
/// drawn there at all (`render.rs`), so the band must not silently steal
/// gestures from whatever plain text sits in its place instead.
/// A screen y on the Settings page as the slider column's design y: the
/// wide layout raises its columns under the one-row header
/// (`render::settings_wide_offset`), so `slider_band`, `volume_slider_band`
/// and `settings_output_picker_hit` take their y through this.
pub fn settings_slider_y(route: Route, y: f64, width: u32, height: u32) -> f64 {
    if route == Route::Settings && crate::settings_wide(width, height) {
        y - crate::render::settings_wide_offset(0, false).1
    } else if route == Route::Shade {
        // The wide Shade puts its sliders under the tiles.
        y - shade_slider_shift(shade_layout(width, height).wide)
    } else {
        y
    }
}

pub fn slider_band(route: Route, y: f64, view: &ServiceView) -> bool {
    let writable = view
        .settings
        .as_ref()
        .is_some_and(|settings| settings.brightness.state == ControlState::Writable);
    if !writable {
        return false;
    }
    match route {
        Route::Settings => {
            let y = y + view.settings_scroll;
            (settings_row_y(1)..settings_row_y(1) + settings_row_h(1)).contains(&y)
        }
        Route::Shade => (SHADE_SLIDER_TOP..SHADE_SLIDER_TOP + SHADE_SLIDER_H).contains(&y),
        _ => false,
    }
}

/// Same rule as `slider_band`, for the volume slider: available only once
/// the PipeWire monitor has reported a default sink (before the first
/// snapshot, or if the monitor never started, nothing is drawn there --
/// see `render.rs`'s own gate -- so the band must not steal a gesture
/// from whatever placeholder text sits there instead).
pub fn volume_slider_band(route: Route, y: f64, view: &ServiceView) -> bool {
    let available = view
        .audio
        .as_ref()
        .is_some_and(|audio| audio.sinks.iter().any(|sink| sink.is_default));
    if !available {
        return false;
    }
    match route {
        Route::Settings => {
            let top = settings_row_y(SETTINGS_VOLUME_ROW);
            (top..top + settings_row_h(SETTINGS_VOLUME_ROW)).contains(&(y + view.settings_scroll))
        }
        Route::Shade => (SHADE_VOLUME_TOP..SHADE_VOLUME_TOP + SHADE_VOLUME_H).contains(&y),
        _ => false,
    }
}

/// The Settings volume row's own device-picker entry point: the "tap to
/// change output" detail line specifically (`render.rs`'s own paint --
/// design.md's "one picker, two entry points": Settings launches the
/// same expanded HUD panel/list rather than duplicating it as a second
/// UI). Checked before `volume_slider_band`'s own arm on `Route::Settings`
/// only, so a tap here never becomes a drag; the Shade's compact volume
/// row shows no such text and has no equivalent zone (`_ => false` below
/// covers Shade and every other route).
pub fn settings_output_picker_hit(y: f64, route: Route, view: &ServiceView) -> bool {
    if route != Route::Settings {
        return false;
    }
    let has_default_sink = view
        .audio
        .as_ref()
        .is_some_and(|audio| audio.sinks.iter().any(|sink| sink.is_default));
    if !has_default_sink {
        return false;
    }
    // The detail occupies the middle line. Keep its tap band clear of the
    // heading above and the slider thumb (center +86, radius 16) below.
    let top = settings_row_y(SETTINGS_VOLUME_ROW) + crate::render::settings_output_detail_y() - 9.0;
    let band = (crate::render::settings_row_lines(SETTINGS_VOLUME_ROW).2 - crate::render::settings_output_detail_y() + 9.0).max(36.0);
    (top..top + band).contains(&(y + view.settings_scroll))
}

/// The speaker glyph at the volume slider's own left end doubles as the
/// mute toggle (task: "a speaker icon that toggles mute when tapped").
/// Mirrors `paint_speaker`'s glyph placement in `render.rs` (`left -
/// 30.0`): a hit box wide enough to comfortably clear Material's ~9mm
/// touch-target floor on this 330ppi panel, distinct from the track/thumb
/// area (`slider::track_bounds`'s own `left..right`) that
/// `slider::Drag` owns for the rest of the row.
pub fn volume_icon_tap_zone(x: f64, width: f64) -> bool {
    let (left, _) = slider::track_bounds(width);
    (left - 56.0..left).contains(&x)
}

/// A tap (no drag past the tap slop) that starts and ends on the dim
/// backdrop below a Shade/Settings sheet: the sheet closes, as tapping
/// outside a sheet does everywhere else.
pub fn backdrop_tap(route: Route, start: (f64, f64), end: (f64, f64), panel_travel: f64) -> bool {
    matches!(route, Route::Shade | Route::Settings | Route::Power | Route::Help)
        && start.1 >= panel_travel
        && end.1 >= panel_travel
        && (end.0 - start.0).abs() <= 18.0
        && (end.1 - start.1).abs() <= 18.0
}

/// Where a released close drag settles: fully closed (`0.0`) or back open
/// (`1.0`). A fast release in the closing direction commits to closing
/// outright; otherwise it is a plain threshold on how much of the panel
/// was already pulled away. `closing_velocity` uses the same sign
/// convention as `close_drag_progress`'s own `dy` after `close_direction`
/// is applied: positive means "moving in this route's own closing
/// direction", regardless of whether that is up (Shade/Settings) or down
/// (Drawer).
pub fn close_drag_release_target(progress: f64, closing_velocity: f64) -> f64 {
    if closing_velocity >= CLOSE_FLING_VELOCITY || progress < CLOSE_DISMISS_PROGRESS {
        0.0
    } else {
        1.0
    }
}

#[derive(Clone, Copy, Debug)]
struct PanelCloseSettle {
    from: f64,
    target: f64,
    started_ms: u64,
    duration_ms: u64,
}

/// Client-side live-tracking/settle state for a Shade/Settings close drag.
/// Unlike `RevealState` (the compositor-driven *open* reveal), this never
/// touches input-region readiness: the client already owns this touch the
/// whole time, it is simply choosing to move the panel with it instead of
/// resolving an ordinary tap. `tracking` (a live finger) and `settling` (an
/// eased animation to 0.0 or 1.0, started either by a release or by a
/// non-drag close such as a Settings back tap) are mutually exclusive;
/// `progress` is meaningful whenever either is true.
#[derive(Clone, Copy, Debug, Default)]
pub struct PanelClose {
    contact: Option<i32>,
    progress: f64,
    settle: Option<PanelCloseSettle>,
    just_settled_closed: bool,
}

impl PanelClose {
    /// Starts live tracking for `id`, from the ordinary fully-open state --
    /// the only state a close drag can begin from (a touch is only ever
    /// accepted into `close_drag_zone` while the panel is fully open and
    /// `input_ready`; see `close_drag_zone`'s own doc for why the eligible
    /// zones can never overlap a scroll/carousel drag already in progress).
    pub fn begin(&mut self, id: i32) {
        self.contact = Some(id);
        self.progress = 1.0;
        self.settle = None;
        self.just_settled_closed = false;
    }

    pub fn tracking(&self) -> bool {
        self.contact.is_some()
    }

    pub fn settling(&self) -> bool {
        self.settle.is_some()
    }

    pub fn active(&self) -> bool {
        self.tracking() || self.settling()
    }

    pub fn progress(&self) -> f64 {
        self.progress
    }

    /// Live update while tracking `id`. Returns whether the visible
    /// progress actually changed (worth a redraw).
    pub fn update(&mut self, id: i32, progress: f64) -> bool {
        if self.contact != Some(id) {
            return false;
        }
        let clamped = progress.clamp(0.0, 1.0);
        let changed = (clamped - self.progress).abs() >= 0.001;
        self.progress = clamped;
        changed
    }

    /// Ends live tracking for `id` and starts an eased settle to `target`
    /// (`0.0` closed, `1.0` back open) from wherever the finger left it.
    /// Returns `false` (no-op) if `id` was not the tracked contact.
    pub fn release(&mut self, id: i32, target: f64, now_ms: u64, reduced_motion: bool) -> bool {
        if self.contact != Some(id) {
            return false;
        }
        self.settle_to(target, now_ms, reduced_motion);
        true
    }

    /// A non-drag close (a Settings back/close tap, or any other
    /// programmatic close) starts the same settle directly from `from` --
    /// the caller's own current progress, ordinarily `1.0` (fully open),
    /// since that is the only state such a tap can fire from -- with no
    /// live-tracking phase. Takes `from` explicitly rather than reading
    /// `self.progress` because this may be the very first call on a fresh
    /// `PanelClose` (whose `Default` progress is `0.0`, meaning "not yet
    /// engaged", not "closed").
    pub fn begin_settle(&mut self, from: f64, target: f64, now_ms: u64, reduced_motion: bool) {
        self.progress = from;
        self.settle_to(target, now_ms, reduced_motion);
    }

    /// A touch sequence cancelled by the compositor mid-drag (rare):
    /// spring back open from wherever it was, the same eased way a
    /// release below the dismiss threshold already does, rather than
    /// leaving the panel stuck half-open with no owner. A no-op unless
    /// this was actually `active` (tracking or already settling).
    pub fn abandon_to_open(&mut self, now_ms: u64, reduced_motion: bool) {
        if self.active() {
            self.settle_to(1.0, now_ms, reduced_motion);
        }
    }

    fn settle_to(&mut self, target: f64, now_ms: u64, reduced_motion: bool) {
        self.contact = None;
        self.settle = Some(PanelCloseSettle {
            from: self.progress,
            target,
            started_ms: now_ms,
            // Same duration policy as `RevealState::settle_to`: a close
            // reads as the same kind of motion opening already does,
            // rather than a second animation curve to reason about.
            duration_ms: if reduced_motion { 60 } else { 160 },
        });
    }

    /// Advances an in-flight settle. Returns whether one is (or, on the
    /// frame it finishes, was) in progress -- the caller redraws whenever
    /// this is true, and checks `take_settled_closed` to know whether
    /// *this* call was the one that just reached fully closed.
    pub fn tick(&mut self, now_ms: u64) -> bool {
        let Some(settle) = self.settle else {
            return false;
        };
        let fraction = (now_ms.saturating_sub(settle.started_ms) as f64
            / (settle.duration_ms.max(1) as f64))
            .clamp(0.0, 1.0);
        // Ease out: the sheet leaves the finger at speed and slows into place.
        let eased = 1.0 - (1.0 - fraction).powi(3);
        self.progress = settle.from + (settle.target - settle.from) * eased;
        if fraction >= 1.0 {
            self.settle = None;
            self.just_settled_closed = settle.target <= 0.0;
        }
        true
    }

    /// Consumes the "just reached fully closed" flag `tick` may have set,
    /// so the caller unmaps exactly once.
    pub fn take_settled_closed(&mut self) -> bool {
        std::mem::take(&mut self.just_settled_closed)
    }

    /// Drops all state (a second-contact cancel, a route change, or a full
    /// hide/unmap), the same way `RevealState::clear` does for the open
    /// reveal.
    pub fn cancel(&mut self) {
        *self = Self::default();
    }
}

/// Pixel-per-millisecond coast after the finger releases a history list.
#[derive(Clone, Copy, Debug, Default)]
pub struct NotificationCoast {
    velocity: f64,
}

impl NotificationCoast {
    pub fn start(&mut self, velocity: f64) {
        self.velocity = if velocity.is_finite() && velocity.abs() >= 0.12 {
            velocity.clamp(-2.5, 2.5)
        } else {
            0.0
        };
    }

    pub fn stop(&mut self) -> bool {
        let moving = self.moving();
        self.velocity = 0.0;
        moving
    }

    pub fn moving(&self) -> bool {
        self.velocity != 0.0
    }

    pub fn tick(&mut self, scroll: &mut f64, max_scroll: f64, elapsed_ms: u32) -> bool {
        if !self.moving() {
            return false;
        }
        let dt = f64::from(elapsed_ms.min(48));
        if dt == 0.0 {
            return false;
        }
        let decay = (-dt / 180.0).exp();
        let next =
            (*scroll + self.velocity * 180.0 * (1.0 - decay)).clamp(0.0, max_scroll.max(0.0));
        let changed = (next - *scroll).abs() >= 0.01;
        *scroll = next;
        self.velocity *= decay;
        if self.velocity.abs() < 0.03 || next == 0.0 || next == max_scroll.max(0.0) {
            self.velocity = 0.0;
        }
        changed
    }
}

/// A release animates from the displayed row position, never from an endpoint.
#[derive(Clone, Copy, Debug)]
pub struct NotificationSwipeSettle {
    start: f64,
    target: f64,
    elapsed_ms: u32,
    duration_ms: u32,
    pub dismiss_id: Option<u64>,
}

impl NotificationSwipeSettle {
    pub fn new(start: f64, target: f64, dismiss_id: Option<u64>, reduced_motion: bool) -> Self {
        let distance = (target - start).abs();
        Self {
            start,
            target,
            elapsed_ms: 0,
            duration_ms: if reduced_motion {
                60
            } else {
                (distance * 0.4).clamp(120.0, 240.0) as u32
            },
            dismiss_id,
        }
    }

    pub fn tick(&mut self, offset: &mut f64, elapsed_ms: u32) -> bool {
        self.elapsed_ms = self.elapsed_ms.saturating_add(elapsed_ms.min(48));
        let t = (f64::from(self.elapsed_ms) / f64::from(self.duration_ms)).min(1.0);
        let eased = 1.0 - (1.0 - t).powi(3);
        let next = self.start + (self.target - self.start) * eased;
        let changed = (next - *offset).abs() >= 0.01;
        *offset = next;
        changed
    }

    pub fn finished(&self) -> bool {
        self.elapsed_ms >= self.duration_ms
    }
}

/// Whether an open shade should take the history a banner `PreviewPoll`
/// brought back. The shade otherwise reads history only when it opens, so a
/// notification that arrives, or replaces another by tag, while it is open
/// (the battery policy's "Shutdown cancelled" over its countdown) stayed
/// stale. Not while a dismiss waits for its own refresh, so the row it
/// removed optimistically does not come back.
pub fn shade_adopts_poll(
    shade_open: bool,
    dismiss_pending: bool,
    shown: Option<&NotificationSnapshot>,
    polled: &NotificationSnapshot,
) -> bool {
    shade_open && !dismiss_pending && shown.is_none_or(|shown| shown.events != polled.events)
}

/// Where the scrolling Settings body starts on screen: just under the
/// header's last line.
pub fn settings_body_top(width: u32, height: u32) -> f64 {
    let (scale, _) = crate::settings_content_transform(width, height);
    let first_y = if crate::settings_wide(width, height) {
        crate::render::settings_wide_first_y()
    } else {
        crate::render::settings_first_y()
    };
    (first_y - 8.0) * scale
}

/// How far the Settings body can scroll: its content bottom against the
/// screen. Zero whenever the rows already fit.
pub fn settings_max_scroll(width: u32, height: u32, view: &ServiceView) -> f64 {
    let (scale, _) = crate::settings_content_transform(width, height);
    let key_backlight = view.key_backlight.is_some();
    let bottom = if crate::settings_wide(width, height) {
        (0..3)
            .map(|column| {
                let dy = crate::render::settings_wide_offset_for(column, key_backlight, view.modem.is_some()).1;
                let end = match column {
                    0 => settings_row_y(SETTINGS_VOLUME_ROW) + settings_row_h(SETTINGS_VOLUME_ROW),
                    1 => {
                        let last = if key_backlight { SETTINGS_KEY_BACKLIGHT_ROW } else { 4 };
                        settings_row_y(last) + settings_row_h(last)
                    }
                    _ => crate::render::settings_content_bottom(Some(view)) - 32.0,
                };
                end + dy
            })
            .fold(0.0, f64::max)
            + 24.0
    } else {
        crate::render::settings_content_bottom(Some(view))
    };
    (bottom * scale - f64::from(height)).max(0.0)
}

pub fn notification_max_scroll(count: usize, width: u32, height: u32) -> f64 {
    let layout = shade_layout(width, height);
    (layout.list_top + count as f64 * notification_row() - layout.list_bottom).max(0.0)
}

fn notification_index(pos: (f64, f64), width: u32, height: u32, view: &ServiceView) -> Option<usize> {
    let layout = shade_layout(width, height);
    if pos.1 < layout.list_top || pos.1 >= layout.list_bottom || pos.0 < layout.list_x {
        return None;
    }
    let index =
        ((pos.1 - layout.list_top + view.notification_scroll) / notification_row()).floor() as usize;
    (index < view.notifications.as_ref()?.events.len()).then_some(index)
}

pub fn notification_swipe_start(
    start: (f64, f64),
    current: (f64, f64),
    width: u32,
    height: u32,
    view: &ServiceView,
) -> Option<NotificationSwipe> {
    let dx = current.0 - start.0;
    let dy = current.1 - start.1;
    let layout = shade_layout(width, height);
    if start.0 < layout.list_x + 24.0
        || start.0 >= f64::from(width) - 24.0
        || dx.abs() <= SWIPE_START
        || dx.abs() <= dy.abs()
    {
        return None;
    }
    let row_y =
        (start.1 - layout.list_top + view.notification_scroll).rem_euclid(notification_row());
    if row_y >= notification_row() - 8.0 {
        return None;
    }
    let row_index = notification_index(start, width, height, view)?;
    let event = &view.notifications.as_ref()?.events[row_index];
    (event.dismissible && event.priority != Priority::Critical).then_some(NotificationSwipe {
        event_id: event.id,
        row_index,
        offset: notification_swipe_offset(start.0, current.0),
    })
}

pub fn notification_swipe_offset(start_x: f64, current_x: f64) -> f64 {
    (current_x - start_x).clamp(-SWIPE_TRAVEL, SWIPE_TRAVEL)
}

pub fn notification_swipe_valid(view: &ServiceView, swipe: &NotificationSwipe) -> bool {
    view.notifications
        .as_ref()
        .and_then(|snapshot| snapshot.events.get(swipe.row_index))
        .is_some_and(|event| {
            event.id == swipe.event_id && event.dismissible && event.priority != Priority::Critical
        })
}

pub fn notification_swipe_hit(
    view: &ServiceView,
    swipe: &NotificationSwipe,
    pos: (f64, f64),
    width: u32,
    height: u32,
) -> bool {
    if !notification_swipe_valid(view, swipe) {
        return false;
    }
    let layout = shade_layout(width, height);
    let y = layout.list_top + swipe.row_index as f64 * notification_row() - view.notification_scroll;
    pos.1 >= y.max(layout.list_top)
        && pos.1 < (y + notification_row() - 8.0).min(layout.list_bottom)
        && pos.0 >= layout.list_x + 24.0 + swipe.offset
        && pos.0 < f64::from(width) - 24.0 + swipe.offset
}

pub fn notification_swipe_release(
    view: &ServiceView,
    swipe: &NotificationSwipe,
    vertical_delta: f64,
) -> Option<ServiceRequest> {
    (swipe.offset.abs() >= SWIPE_COMMIT
        && vertical_delta.abs() <= SWIPE_VERTICAL_CANCEL
        && notification_swipe_valid(view, swipe))
    .then_some(ServiceRequest::NotificationDismiss(swipe.event_id))
}

/// Which wide-layout column (0..=2) a Settings touch at screen `x` falls in:
/// the nearest column, split at the middle of the gutter between cards.
pub fn settings_wide_column(x: f64) -> usize {
    let first_gutter = crate::SETTINGS_WIDE_ORIGIN_X + crate::SETTINGS_WIDE_COL_W - 12.0;
    let index = ((x - first_gutter) / crate::SETTINGS_WIDE_COL_PITCH).floor() + 1.0;
    index.clamp(0.0, 2.0) as usize
}

/// Maps a real touch point on the wide (landscape) Settings page back to the
/// single-column design space every row/Power check below is written in, by
/// undoing the same `render::settings_wide_offset` the paint applies. `None`
/// when the point lies outside every item of its column (above the first
/// row, or below the last), so a column's offset can never make a tap land
/// on a row that belongs to another column.
pub fn settings_wide_design_point(point: (f64, f64), key_backlight: bool) -> Option<(f64, f64)> {
    settings_wide_design_point_for(point, key_backlight, false)
}

/// `settings_wide_design_point` when the Cellular and Location rows lead
/// column 2.
pub fn settings_wide_design_point_for(
    point: (f64, f64),
    key_backlight: bool,
    modem: bool,
) -> Option<(f64, f64)> {
    let column = settings_wide_column(point.0);
    let (dx, dy) = crate::render::settings_wide_offset_for(column, key_backlight, modem);
    let design = (point.0 - dx, point.1 - dy);
    // Slack of half a row gap above each column's first item.
    let first = |top: f64| top - crate::render::SETTINGS_ROW_GAP / 2.0;
    let last_row = if key_backlight { SETTINGS_KEY_BACKLIGHT_ROW } else { 4 };
    let in_column = match column {
        0 => design.1 >= first(settings_row_y(0)) && design.1 < first(settings_row_y(3)),
        1 => {
            design.1 >= first(settings_row_y(3))
                && design.1 < settings_row_y(last_row) + settings_row_h(last_row) + crate::render::SETTINGS_ROW_GAP / 2.0
        }
        _ => design.1 >= first(crate::render::settings_modem_row_y(key_backlight, 0)),
    };
    let _ = modem;
    in_column.then_some(design)
}

/// The screen x origin and design width the Settings sliders (brightness and
/// volume, both in the wide layout's first column) are laid out against:
/// the whole panel normally, the first column when wide.
pub fn settings_slider_frame(route: Route, width: u32, height: u32) -> (f64, f64) {
    if route == Route::Settings && crate::settings_wide(width, height) {
        (crate::SETTINGS_WIDE_ORIGIN_X, crate::SETTINGS_WIDE_COL_W)
    } else if route == Route::Shade {
        (0.0, shade_layout(width, height).controls_w)
    } else {
        (0.0, f64::from(width))
    }
}

/// The screen x origin and width of the Key backlight row's slider: the
/// whole panel normally, the middle column when wide (`settings_row_column`).
pub fn key_backlight_slider_frame(width: u32, height: u32) -> (f64, f64) {
    if crate::settings_wide(width, height) {
        let column = crate::render::settings_row_column(SETTINGS_KEY_BACKLIGHT_ROW) as f64;
        (
            crate::SETTINGS_WIDE_ORIGIN_X + column * crate::SETTINGS_WIDE_COL_PITCH,
            crate::SETTINGS_WIDE_COL_W,
        )
    } else {
        (0.0, f64::from(width))
    }
}

/// Whether a touch at screen `pos` on the Settings page lands on the Key
/// backlight row, which then belongs to its slider for the whole gesture.
/// Only while the base's LED exists (`render.rs` draws no row otherwise).
pub fn key_backlight_slider_hit(pos: (f64, f64), width: u32, height: u32, view: &ServiceView) -> bool {
    if view.key_backlight.is_none() {
        return false;
    }
    let (x, w) = key_backlight_slider_frame(width, height);
    let y = if crate::settings_wide(width, height) {
        if !(x..x + w).contains(&pos.0) {
            return false;
        }
        let column = crate::render::settings_row_column(SETTINGS_KEY_BACKLIGHT_ROW);
        pos.1 - crate::render::settings_wide_offset(column, true).1
    } else {
        pos.1
    } + view.settings_scroll;
    let top = settings_row_y(SETTINGS_KEY_BACKLIGHT_ROW);
    (top..top + settings_row_h(SETTINGS_KEY_BACKLIGHT_ROW)).contains(&y)
}

/// The level under screen `x` on the Key backlight slider: the track
/// (`slider::track_bounds`, the same as every slider here) split into four
/// detents, Off at the left end and High at the right.
pub fn key_backlight_level_at(x: f64, frame_x: f64, frame_w: f64) -> crate::keyboard_base::KeyBacklight {
    let (left, right) = slider::track_bounds(frame_w);
    let fraction = ((x - frame_x - left) / (right - left)).clamp(0.0, 1.0);
    crate::keyboard_base::KeyBacklight::from_index((fraction * 3.0).round() as u8)
}

/// Whether a Settings touch at screen `x` can reach the sliders and the
/// volume row at all: always, except in the wide layout, where only column 0
/// holds them (the same y band in columns 1 and 2 is Keyboard/Motion rows).
pub fn settings_slider_column_hit(route: Route, width: u32, height: u32, x: f64) -> bool {
    match route {
        Route::Settings => !crate::settings_wide(width, height) || settings_wide_column(x) == 0,
        // The wide Shade keeps its sliders in the left column; the same y
        // band on the right is the notification list.
        Route::Shade => x < shade_layout(width, height).controls_w,
        _ => true,
    }
}

/// Returns an intent only after the caller has paired a single real contact.
pub fn panel_intent(
    route: Route,
    start: (f64, f64),
    end: (f64, f64),
    width: u32,
    height: u32,
    view: &ServiceView,
) -> Option<PanelIntent> {
    let dx = end.0 - start.0;
    let dy = end.1 - start.1;
    let w = f64::from(width);
    match route {
        Route::Shade => {
            let layout = shade_layout(width, height);
            // The wide Shade's list starts at the panel's top, beside the
            // controls: an upward drag there scrolls the list, not Hide.
            if start.1 < OVERLAY_DISMISS_ZONE_Y && dy < OVERLAY_DISMISS_DY && !layout.in_list(start) {
                return Some(PanelIntent::Hide);
            }
            if let Some(index) = notification_index(start, width, height, view) {
                let event = &view.notifications.as_ref()?.events[index];
                if dy.abs() > 22.0 {
                    return Some(PanelIntent::ScrollNotifications(-dy));
                }
                // The painted row can be displaced or waiting for its dismiss
                // reply. A tap at its old slot must not activate that event.
                if view
                    .notification_swipe
                    .as_ref()
                    .is_some_and(|swipe| swipe.event_id == event.id)
                {
                    return None;
                }
                if dx.abs() <= 18.0 && event.action_available {
                    return Some(PanelIntent::Request(ServiceRequest::NotificationAction(
                        event.id,
                    )));
                }
                return None;
            }
            if dx.abs() > 18.0 || dy.abs() > 18.0 {
                return None;
            }
            if end.1 < SHADE_SETTINGS_BOTTOM && end.0 > layout.controls_w - shade_link_w(layout.controls_w) && end.0 < layout.controls_w {
                return Some(PanelIntent::OpenSettings);
            }
            if let Some(tile) = shade_tile_at(end, &layout, view) {
                return match tile {
                    ShadeTile::Wifi => Some(PanelIntent::OpenWifi),
                    ShadeTile::Keyboard => {
                        let keyboard = &view.settings.as_ref()?.keyboard;
                        (keyboard.state == ControlState::Action)
                            .then_some(PanelIntent::Request(ServiceRequest::KeyboardToggle))
                    }
                    ShadeTile::Location => Some(PanelIntent::ToggleLocation),
                    ShadeTile::Cellular => Some(PanelIntent::OpenCellular),
                };
            }
            // The wide Shade's "Dismiss all" heads the list column, beside
            // its "Notifications" heading.
            if layout.wide
                && end.1 < SHADE_SETTINGS_BOTTOM
                && end.0 > layout.list_x + layout.list_w - shade_link_w(layout.list_w)
                && view.notifications.as_ref().is_some_and(|items| !items.events.is_empty())
            {
                return Some(PanelIntent::Request(ServiceRequest::NotificationDismissAll));
            }
            if layout.wide {
                return None;
            }
            if (SHADE_TOGGLE_TOP..SHADE_TOGGLE_TOP + shade_toggle_h()).contains(&end.1)
                && end.0 >= 24.0
                && end.0 < layout.controls_w - 24.0
            {
                let keyboard = &view.settings.as_ref()?.keyboard;
                return (keyboard.state == ControlState::Action)
                    .then_some(PanelIntent::Request(ServiceRequest::KeyboardToggle));
            }
            if (SHADE_DISMISS_TOP..SHADE_DISMISS_BOTTOM).contains(&end.1)
                && end.0 > layout.controls_w - shade_link_w(layout.controls_w)
                && end.0 < layout.controls_w
                && view
                    .notifications
                    .as_ref()
                    .is_some_and(|items| !items.events.is_empty())
            {
                return Some(PanelIntent::Request(ServiceRequest::NotificationDismissAll));
            }
            None
        }
        Route::Help => crate::help::hit(start, end, width, height, view.navigation_aid, view.help_scroll)
            .map(PanelIntent::Help),
        Route::Power => {
            // An upward swipe closes the sheet, as on the Shade and
            // Settings; nothing on it scrolls.
            if dy < OVERLAY_DISMISS_DY && dx.abs() < dy.abs() {
                return Some(PanelIntent::Hide);
            }
            if dx.abs() > 18.0 || dy.abs() > 18.0 {
                return None;
            }
            if let Some(confirm) = &view.confirmation {
                if Instant::now() >= confirm.expires_at {
                    return None;
                }
                let band = POWER_CONFIRM_Y - POWER_CONFIRM_SLOP / 2.0..POWER_CONFIRM_Y + POWER_BUTTON_H + POWER_CONFIRM_SLOP;
                if band.contains(&end.1) {
                    return Some(PanelIntent::Request(if end.0 < w / 2.0 {
                        ServiceRequest::PowerCancel(confirm.token.clone())
                    } else {
                        ServiceRequest::PowerConfirm(confirm.token.clone())
                    }));
                }
                return None;
            }
            if (POWER_REBOOT_Y..POWER_REBOOT_Y + POWER_BUTTON_H).contains(&end.1) {
                return Some(PanelIntent::Request(ServiceRequest::PowerRequest(
                    PowerAction::Reboot,
                )));
            }
            if (POWER_OFF_Y..POWER_OFF_Y + POWER_BUTTON_H).contains(&end.1) {
                return Some(PanelIntent::Request(ServiceRequest::PowerRequest(
                    PowerAction::Poweroff,
                )));
            }
            if (POWER_CANCEL_Y..POWER_CANCEL_Y + POWER_BUTTON_H).contains(&end.1) {
                return Some(PanelIntent::Hide);
            }
            None
        }
        Route::Settings => {
            if start.1 < OVERLAY_DISMISS_ZONE_Y && dy < OVERLAY_DISMISS_DY {
                return Some(PanelIntent::Hide);
            }
            if dx.abs() > 18.0 || dy.abs() > 18.0 {
                return None;
            }
            let header = crate::render::settings_header(w);
            if end.1 < header.done_bottom && end.0 > header.done_x {
                return Some(PanelIntent::Hide);
            }
            // Everything below (the confirm dialog, the row/Power taps) is
            // `render.rs`'s scaled, centered content column
            // (`crate::settings_content_transform`, applied to the
            // identical `(width, height)`) -- map the real touch point back
            // into that column's own design-unit space before any of the
            // row-rhythm checks below, so a tap and its paint can never
            // drift apart. The "Done" check above stays in real coordinates
            // on purpose: that text paints outside the scaled column, in
            // the shared, unscaled header strip every other route uses too.
            let wide = crate::settings_wide(width, height);
            let (content_scale, content_x) = crate::settings_content_transform(width, height);
            // The body scrolls under the fixed header at a larger vision
            // step (`settings_max_scroll`); a touch above it is header.
            if end.1 < settings_body_top(width, height) {
                return None;
            }
            let end = (end.0, end.1 + view.settings_scroll);
            let end = if wide {
                settings_wide_design_point_for(end, view.key_backlight.is_some(), view.modem.is_some())?
            } else {
                ((end.0 - content_x) / content_scale, end.1 / content_scale)
            };
            let w = if wide { crate::SETTINGS_WIDE_COL_W } else { crate::DESIGN_WIDTH };
            if let Some(confirm) = &view.confirmation {
                if Instant::now() >= confirm.expires_at {
                    return None;
                }
                let card_y = settings_confirm_layout(settings_layout_for(view.key_backlight.is_some(), view.modem.is_some()).poweroff_bottom).card_y;
                if (card_y..card_y + 110.0).contains(&end.1) {
                    return Some(PanelIntent::Request(if end.0 < w / 2.0 {
                        ServiceRequest::PowerCancel(confirm.token.clone())
                    } else {
                        ServiceRequest::PowerConfirm(confirm.token.clone())
                    }));
                }
                return None;
            }
            let settings = view.settings.as_ref()?;
            // These ranges mirror the row rhythm `render.rs` paints the
            // Settings screen with (finding P0-4); call the same helpers
            // rather than repeating its literals, so the two cannot drift.
            let layout = settings_layout_for(view.key_backlight.is_some(), view.modem.is_some());
            if (settings_row_y(0)..settings_row_y(0) + settings_row_h(0)).contains(&end.1) {
                return Some(PanelIntent::OpenWifi);
            }
            {
                let key_backlight = view.key_backlight.is_some();
                let row_h = crate::render::settings_modem_row_h();
                let modem = view.modem.is_some();
                let mut intents = Vec::new();
                if modem {
                    intents.extend([PanelIntent::OpenCellular, PanelIntent::OpenLocation]);
                }
                intents.extend([PanelIntent::OpenDateTime, PanelIntent::OpenAbout]);
                for (index, intent) in intents.into_iter().enumerate() {
                    let y = crate::render::settings_modem_row_y(key_backlight, index as u32);
                    if (y..y + row_h).contains(&end.1) {
                        return Some(intent);
                    }
                }
            }
            // Brightness (row 1) is no longer a tap-classified stepper --
            // the slider band (`slider_band`) owns that row's touches
            // entirely, armed/finalized directly in `main.rs`'s
            // down/motion/up handlers rather than through this release-
            // only classification. A tap landing there without ever
            // arming a drag (brightness unavailable, say) simply falls
            // through to `None` below, same as any other dead zone.
            if (settings_row_y(3)..settings_row_y(3) + settings_row_h(3)).contains(&end.1)
                && settings.keyboard.state == ControlState::Action
            {
                return Some(PanelIntent::Request(ServiceRequest::KeyboardToggle));
            }
            // The Key backlight row belongs to its slider
            // (`key_backlight_slider_hit`), armed in `main.rs` like the
            // brightness and volume sliders.
            if (layout.reboot_y..layout.reboot_y + settings_power_card_h()).contains(&end.1)
                && view.settings.is_some()
            {
                return Some(PanelIntent::Request(ServiceRequest::PowerRequest(
                    PowerAction::Reboot,
                )));
            }
            if (layout.poweroff_y..layout.poweroff_y + settings_power_card_h()).contains(&end.1)
                && view.settings.is_some()
            {
                return Some(PanelIntent::Request(ServiceRequest::PowerRequest(
                    PowerAction::Poweroff,
                )));
            }
            None
        }
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::render::settings_layout;
    use crate::pipewire_ipc::Sink;
    use crate::service_data::{Control, ControlValue, NotificationEvent, Priority};
    use std::path::PathBuf;

    #[test]
    fn the_landscape_shade_reaches_its_first_notification_row() {
        assert_eq!(shade_panel_height(1232), 1232.0 * 0.65, "portrait is unchanged");
        let h = shade_panel_height(568);
        assert!(h <= 568.0);
        // The wide Shade's list sits beside the controls from the top.
        let layout = shade_layout(1232, 568);
        assert!(layout.list_bottom >= layout.list_top + NOTIFICATION_ROW, "one whole row fits: {h}");
        assert!(SHADE_TOGGLE_TOP + shade_toggle_h() <= h, "the controls column holds the quick toggle");
    }

    fn app(name: &str) -> AppEntry {
        AppEntry {
            id: format!("{name}.desktop"),
            name: name.into(),
            icon: None,
            path: PathBuf::new(),
        }
    }

    #[test]
    fn filter_app_indices_matches_case_insensitive_substrings() {
        let apps = vec![app("Camera"), app("Calculator"), app("Files"), app("Gallery")];
        assert_eq!(filter_app_indices(&apps, ""), vec![0, 1, 2, 3], "empty query matches all, in order");
        assert_eq!(filter_app_indices(&apps, "ca"), vec![0, 1], "prefix match, case-insensitive");
        assert_eq!(filter_app_indices(&apps, "CAM"), vec![0], "uppercase query still matches");
        assert_eq!(filter_app_indices(&apps, "ery"), vec![3], "substring, not just prefix");
        assert!(
            filter_app_indices(&apps, "zzz").is_empty(),
            "no match is an empty list, not a panic"
        );
    }

    #[test]
    fn drawer_search_key_focus_and_clear() {
        let mut search = DrawerSearch::default();
        assert!(!search.focused);
        assert!(search.query.is_empty());

        search.focus();
        assert!(search.focused);

        search.key_event('c' as u32, Some("c"));
        search.key_event('a' as u32, Some("a"));
        assert_eq!(search.query, "ca");

        search.key_event(0xff08, None);
        assert_eq!(search.query, "c", "backspace pops the last character");

        search.unfocus();
        assert!(!search.focused);
        assert_eq!(search.query, "c", "unfocus keeps the query, per its own doc");

        search.clear();
        assert!(search.query.is_empty());
    }

    #[test]
    fn normal_search_keys_correct_text_without_dismissing_the_drawer() {
        let mut search = DrawerSearch::default();
        assert!(!search.key_event('q' as u32, Some("q")));
        search.focus();
        assert!(search.key_event('A' as u32, Some("A")));
        assert!(search.key_event(0, Some(" café")));
        assert!(search.key_event(0xff08, Some("\u{8}")));
        assert_eq!(search.query, "A caf");
        assert!(search.focused, "correction retains focus and the open search");
        assert!(!search.key_event(0, Some("\n")));
        assert!(search.key_event(0xff0d, Some("\r")));
        assert!(!search.focused);
        assert_eq!(search.query, "A caf", "Enter only dismisses the keyboard");
        search.focus();
        assert!(search.key_event(0xff1b, None));
        assert!(!search.focused);
        assert!(!search.key_event('z' as u32, Some("z")), "late keys cannot edit a closed field");
    }

    #[test]
    fn a_key_focused_search_launches_on_enter_and_clears_then_closes_on_esc() {
        let mut search = DrawerSearch::default();
        search.focus_from_keys();
        assert_eq!(search.key_action(0xff0d, Some("\r")), SearchKey::Ignored, "Enter on an empty query does nothing");
        assert_eq!(search.key_action('t' as u32, Some("t")), SearchKey::Edited);
        assert_eq!(search.key_action('i' as u32, Some("i")), SearchKey::Edited);
        assert_eq!(search.key_action(0xff0d, Some("\r")), SearchKey::Launch);
        assert_eq!(search.query, "ti", "Enter leaves the query for the launch to read");
        assert_eq!(search.key_action(0xff1b, None), SearchKey::Edited);
        assert!(search.query.is_empty() && search.focused, "the first Esc clears");
        assert_eq!(search.key_action(0xff1b, None), SearchKey::Close, "the second Esc closes");
        // A tap on the field hands it to the on-screen keyboard as before.
        search.focus();
        assert!(!search.from_keys);
        search.query = "ti".into();
        assert_eq!(search.key_action(0xff0d, Some("\r")), SearchKey::Edited);
        assert!(!search.focused, "a tapped field's Enter still only dismisses the keyboard");
    }

    #[test]
    fn search_viewport_reserves_the_system_keyboard_and_recovers_on_dismiss() {
        let mut search = DrawerSearch::default();
        search.focus(); search.keyboard_inset = 420.0;
        assert_eq!(search.viewport_height(1232), 812);
        search.unfocus();
        assert_eq!(search.viewport_height(1232), 1232);
        search.keyboard_inset = f64::NAN;
        assert_eq!(search.viewport_height(1232), 1232);
    }

    #[test]
    fn power_sheet_requires_a_second_explicit_confirmation_tap() {
        let mut view = ServiceView::default();
        let reboot = (284.0, POWER_REBOOT_Y + 32.0);
        assert_eq!(
            panel_intent(Route::Power, reboot, reboot, 568, 1232, &view),
            Some(PanelIntent::Request(ServiceRequest::PowerRequest(PowerAction::Reboot)))
        );
        let dismiss = (284.0, POWER_CANCEL_Y + 32.0);
        assert_eq!(
            panel_intent(Route::Power, dismiss, dismiss, 568, 1232, &view),
            Some(PanelIntent::Hide)
        );
        assert!(backdrop_tap(
            Route::Power,
            (284.0, 850.0),
            (284.0, 850.0),
            402.0,
        ));
        view.confirmation = Some(Confirmation {
            token: "test-token".into(),
            action: PowerAction::Reboot,
            label: "Restart?".into(),
            expires_at: Instant::now() + std::time::Duration::from_secs(30),
        });
        assert_eq!(panel_intent(Route::Power, reboot, reboot, 568, 1232, &view), None);
        let cancel = (120.0, POWER_CONFIRM_Y + 32.0);
        let confirm = (430.0, POWER_CONFIRM_Y + 32.0);
        assert_eq!(
            panel_intent(Route::Power, cancel, cancel, 568, 1232, &view),
            Some(PanelIntent::Request(ServiceRequest::PowerCancel("test-token".into())))
        );
        assert_eq!(
            panel_intent(Route::Power, confirm, confirm, 568, 1232, &view),
            Some(PanelIntent::Request(ServiceRequest::PowerConfirm("test-token".into())))
        );
    }

    #[test]
    fn close_drag_progress_is_one_at_start_and_zero_at_full_travel() {
        let travel = 800.0;
        assert_eq!(close_drag_progress(Route::Shade, 0.0, travel), 1.0);
        assert_eq!(close_drag_progress(Route::Shade, -travel, travel), 0.0);
        assert_eq!(
            close_drag_progress(Route::Shade, -travel / 2.0, travel),
            0.5
        );
        // Overshooting past full travel clamps at 0, never negative.
        assert_eq!(close_drag_progress(Route::Shade, -travel * 2.0, travel), 0.0);
        // A downward move from the drag's own start only ever pushes back
        // toward 1.0, clamped there -- "a downward drag during a close
        // drag just moves the panel back down" falls out of the clamp.
        assert_eq!(close_drag_progress(Route::Shade, 120.0, travel), 1.0);
    }

    #[test]
    fn close_drag_progress_is_monotonic_in_upward_travel() {
        let travel = 800.0;
        let samples: Vec<f64> = (0..=20)
            .map(|step| close_drag_progress(Route::Shade, -travel * f64::from(step) / 20.0, travel))
            .collect();
        for pair in samples.windows(2) {
            assert!(
                pair[1] <= pair[0],
                "progress must only ever fall as upward travel grows: {samples:?}"
            );
        }
    }

    #[test]
    fn close_drag_progress_mirrors_direction_for_the_bottom_anchored_drawer() {
        // Drawer closes downward (positive dy), the exact mirror image of
        // Shade/Settings closing upward -- same shape, opposite sign.
        let travel = 800.0;
        assert_eq!(close_drag_progress(Route::Drawer, 0.0, travel), 1.0);
        assert_eq!(close_drag_progress(Route::Drawer, travel, travel), 0.0);
        assert_eq!(
            close_drag_progress(Route::Drawer, travel / 2.0, travel),
            0.5
        );
        // An upward move (the wrong direction for a Drawer close) only
        // ever pushes back toward 1.0, clamped there.
        assert_eq!(close_drag_progress(Route::Drawer, -120.0, travel), 1.0);
    }

    #[test]
    fn a_downward_drag_from_the_top_zone_leaves_settings_and_help_to_scroll() {
        for route in [Route::Settings, Route::Help] {
            assert!(close_drag_refused(route, 0.0, 30.0));
            assert!(!close_drag_refused(route, 0.0, 4.0), "under slop");
            assert!(!close_drag_refused(route, 0.0, -30.0), "upward closes");
            assert!(!close_drag_refused(route, 40.0, 30.0), "sideways");
        }
        assert!(!close_drag_refused(Route::Shade, 0.0, 30.0), "Shade keeps its gesture");
    }

    #[test]
    fn close_drag_engaged_needs_slop_and_vertical_dominance() {
        // Under slop: still a tap/wobble candidate.
        assert!(!close_drag_engaged(
            Route::Shade,
            0.0,
            -CLOSE_DRAG_SLOP + 1.0
        ));
        // Exactly at slop, upward, no sideways drift: engaged.
        assert!(close_drag_engaged(Route::Shade, 0.0, -CLOSE_DRAG_SLOP));
        // Downward motion never engages a Shade/Settings close drag.
        assert!(!close_drag_engaged(
            Route::Shade,
            0.0,
            CLOSE_DRAG_SLOP + 20.0
        ));
        // Past slop upward, but more sideways than vertical: not engaged
        // (this is a horizontal gesture, not a vertical close drag).
        assert!(!close_drag_engaged(Route::Shade, 40.0, -20.0));
        // Past slop, vertical-dominant: engaged even with a little drift.
        assert!(close_drag_engaged(Route::Shade, 4.0, -20.0));
    }

    #[test]
    fn close_drag_engaged_is_reversed_for_the_drawer() {
        // The Drawer closes on a downward drag -- the exact opposite of
        // Shade/Settings above, using the same slop/dominance shape.
        assert!(!close_drag_engaged(
            Route::Drawer,
            0.0,
            CLOSE_DRAG_SLOP - 1.0
        ));
        assert!(close_drag_engaged(Route::Drawer, 0.0, CLOSE_DRAG_SLOP));
        assert!(!close_drag_engaged(Route::Drawer, 0.0, -(CLOSE_DRAG_SLOP + 20.0)));
        assert!(!close_drag_engaged(Route::Drawer, 40.0, 20.0));
        assert!(close_drag_engaged(Route::Drawer, 4.0, 20.0));
    }

    #[test]
    fn close_drag_zone_is_the_top_band_and_the_backdrop_only() {
        let travel = 800.0;
        for route in [Route::Shade, Route::Settings] {
            assert!(close_drag_zone(route, 0.0, travel), "{route:?}: top edge");
            assert!(
                close_drag_zone(route, OVERLAY_DISMISS_ZONE_Y - 1.0, travel),
                "{route:?}: just inside the dismiss zone"
            );
            assert!(
                !close_drag_zone(route, OVERLAY_DISMISS_ZONE_Y, travel),
                "{route:?}: dismiss zone's own lower edge is exclusive"
            );
            assert!(
                !close_drag_zone(route, travel - 1.0, travel),
                "{route:?}: still inside scrollable/interactive panel content"
            );
            assert!(
                close_drag_zone(route, travel, travel),
                "{route:?}: the panel's own bottom edge is included"
            );
            assert!(
                close_drag_zone(route, travel + 400.0, travel),
                "{route:?}: anywhere on the backdrop below the panel"
            );
        }
        assert!(!close_drag_zone(Route::Drawer, 0.0, travel));
        assert!(!close_drag_zone(Route::Hide, 0.0, travel));
    }

    #[test]
    fn drawer_close_drag_zone_is_the_top_chrome_and_the_grid_only_at_top() {
        let height = 1232;
        let panel_y = navigation::panel_top(height);
        let header_bottom = list_top(height);
        let dock_top = f64::from(height) - GRID_BOTTOM_INSET; // 1208.0

        // The whole top chrome (handle + search field) is eligible
        // regardless of scroll -- scrolled deep into the list or not, it
        // is still there.
        for scroll in [0.0, 5_000.0] {
            assert!(
                drawer_close_drag_zone(panel_y, height, scroll),
                "top edge, scroll={scroll}"
            );
            assert!(
                drawer_close_drag_zone(header_bottom - 1.0, height, scroll),
                "still inside the top chrome, scroll={scroll}"
            );
        }
        // The grid itself: eligible only once scrolled to (approximately)
        // its own top -- the same "at the top" idea
        // `DrawerNavigation::up`'s own release check already used.
        assert!(
            drawer_close_drag_zone(header_bottom, height, 0.0),
            "grid start, scrolled to top"
        );
        assert!(
            !drawer_close_drag_zone(header_bottom, height, 50.0),
            "grid start, scrolled away from top must not hijack scrolling"
        );
        assert!(
            drawer_close_drag_zone(dock_top - 1.0, height, 0.0),
            "just above the dock, at top, is still the grid"
        );
        // The dock band (pinned tiles) is excluded regardless of scroll.
        assert!(!drawer_close_drag_zone(dock_top, height, 0.0));
        assert!(!drawer_close_drag_zone(
            f64::from(height) - 1.0,
            height,
            0.0
        ));
        // Above the panel entirely (Home showing through) is not a zone.
        assert!(!drawer_close_drag_zone(panel_y - 1.0, height, 0.0));
    }

    #[test]
    fn drawer_close_candidate_is_disqualified_once_scroll_leaves_the_top() {
        // A candidate stays a candidate while the grid is still at (or
        // very near) its own top...
        assert!(drawer_close_candidate_after_scroll(true, 0.0));
        assert!(drawer_close_candidate_after_scroll(true, 0.5));
        // ...but is permanently revoked the instant real scrolling has
        // carried it away, even by a little -- reversing back toward 0.0
        // later must never re-arm it (the caller never re-passes `true`
        // once this has returned `false`, only the *previous* candidate
        // value survives into the caller's own state).
        assert!(!drawer_close_candidate_after_scroll(true, 0.51));
        assert!(!drawer_close_candidate_after_scroll(true, 400.0));
        // A candidate that was never eligible in the first place (e.g. the
        // touch started mid-list) stays disqualified regardless of scroll.
        assert!(!drawer_close_candidate_after_scroll(false, 0.0));
    }

    #[test]
    fn close_drag_release_target_is_a_threshold_with_a_fling_override() {
        // Comfortably past the dismiss threshold, no notable velocity:
        // commits to closed on progress alone.
        assert_eq!(close_drag_release_target(0.2, 0.0), 0.0);
        // Comfortably below the threshold, no notable velocity: springs
        // back open.
        assert_eq!(close_drag_release_target(0.9, 0.0), 1.0);
        // Exactly at the threshold reads as "not yet past it" (open) --
        // the threshold is a floor on what still closes, not a ceiling.
        assert_eq!(close_drag_release_target(CLOSE_DISMISS_PROGRESS, 0.0), 1.0);
        // A fast upward flick commits to closing even from near the top
        // (high revealed progress) -- reversal: velocity overrides the
        // plain threshold.
        assert_eq!(close_drag_release_target(0.95, CLOSE_FLING_VELOCITY), 0.0);
        // A slow, reversed (downward) release well above the threshold
        // never closes.
        assert_eq!(close_drag_release_target(0.95, -1.5), 1.0);
    }

    #[test]
    fn panel_close_tracks_settles_and_reports_closed_exactly_once() {
        let mut close = PanelClose::default();
        assert!(!close.active());
        close.begin(7);
        assert!(close.tracking());
        assert_eq!(close.progress(), 1.0);
        assert!(close.update(7, 0.35));
        assert_eq!(close.progress(), 0.35);
        // A different contact id cannot move this one's progress.
        assert!(!close.update(9, 0.1));
        assert_eq!(close.progress(), 0.35);

        assert!(close.release(7, 0.0, 1_000, false));
        assert!(!close.tracking());
        assert!(close.settling());
        // Mid-settle: partway from 0.35 toward 0.0, not a jump.
        assert!(close.tick(1_080));
        assert!(close.progress() > 0.0 && close.progress() < 0.35);
        assert!(!close.take_settled_closed());
        // Settle finishes at the recorded duration (160ms, not reduced).
        assert!(close.tick(1_160));
        assert_eq!(close.progress(), 0.0);
        assert!(!close.settling());
        assert!(
            close.take_settled_closed(),
            "must report closed exactly once"
        );
        assert!(!close.take_settled_closed(), "and not again on a re-check");
    }

    #[test]
    fn panel_close_settle_to_open_never_reports_closed() {
        let mut close = PanelClose::default();
        close.begin(1);
        close.update(1, 0.5);
        close.release(1, 1.0, 0, false);
        close.tick(160);
        assert_eq!(close.progress(), 1.0);
        assert!(!close.take_settled_closed());
    }

    #[test]
    fn panel_close_begin_settle_animates_a_non_drag_close_from_fully_open() {
        let mut close = PanelClose::default();
        assert!(!close.active());
        close.begin_settle(1.0, 0.0, 0, false);
        assert!(close.settling());
        assert!(!close.tracking());
        assert_eq!(
            close.progress(),
            1.0,
            "settle starts from the current (open) progress"
        );
        close.tick(160);
        assert!(close.take_settled_closed());
    }

    #[test]
    fn an_open_shade_adopts_a_same_id_replacement_but_not_during_a_dismiss() {
        let snapshot = |summary: &str| NotificationSnapshot {
            count: 1,
            events: vec![NotificationEvent {
                id: 1,
                source: "System".into(),
                icon: None,
                summary: summary.into(),
                body: String::new(),
                priority: Priority::Ordinary,
                timestamp: 0,
                error: None,
                dismissible: true,
                action_available: false,
            }],
            preview: None,
        };
        let shown = snapshot("Battery critically low");
        let polled = snapshot("Charging");
        assert!(shade_adopts_poll(true, false, Some(&shown), &polled));
        assert!(shade_adopts_poll(true, false, None, &polled));
        assert!(!shade_adopts_poll(true, false, Some(&polled), &polled), "unchanged rows are not re-applied");
        assert!(!shade_adopts_poll(false, false, Some(&shown), &polled), "a closed shade refreshes when it opens");
        assert!(!shade_adopts_poll(true, true, Some(&shown), &polled), "a pending dismiss keeps its row removed");
    }

    #[test]
    fn a_drag_on_the_shade_panel_closes_unless_it_would_scroll_the_list() {
        let event = |id| NotificationEvent {
            id,
            source: "Terminal".into(),
            icon: None,
            summary: "Ready".into(),
            body: String::new(),
            priority: Priority::Ordinary,
            timestamp: 0,
            error: None,
            dismissible: true,
            action_available: false,
        };
        let empty = ServiceView::default();
        // Header, quick controls and an empty list area all close.
        assert!(shade_panel_close_zone((300.0, 60.0), 568, 1232, &empty));
        assert!(shade_panel_close_zone((300.0, 514.0), 568, 1232, &empty));
        // One notification: the list cannot scroll, so its row closes too.
        let one = ServiceView {
            notifications: Some(NotificationSnapshot {
                count: 1,
                events: vec![event(1)],
                preview: None,
            }),
            ..ServiceView::default()
        };
        assert!(shade_panel_close_zone((300.0, 514.0), 568, 1232, &one));
        // A long list that can still scroll keeps the drag as a scroll...
        let mut long = ServiceView {
            notifications: Some(NotificationSnapshot {
                count: 8,
                events: (1..=8).map(event).collect(),
                preview: None,
            }),
            ..ServiceView::default()
        };
        assert!(!shade_panel_close_zone((300.0, 514.0), 568, 1232, &long));
        // ...until it is scrolled to its end.
        long.notification_scroll = notification_max_scroll(8, 568, 1232);
        assert!(shade_panel_close_zone((300.0, 514.0), 568, 1232, &long));
        // The header above the list always closes.
        long.notification_scroll = 0.0;
        assert!(shade_panel_close_zone((300.0, 60.0), 568, 1232, &long));
    }

    fn writable_volume_view() -> ServiceView {
        ServiceView {
            audio: Some(GraphSnapshot {
                sinks: vec![Sink {
                    id: 50,
                    name: "alsa_output.inno".into(),
                    description: "K230 Inno codec line-out".into(),
                    linear_volume: 0.5,
                    muted: false,
                    is_default: true,
                    route: None,
                }],
                streams: Vec::new(),
            }),
            ..writable_brightness_view()
        }
    }

    /// Mirrors `slider_band_owns_its_row_and_is_excluded_from_the_close_
    /// drag_candidacy` above, for the second (volume) slider directly
    /// beneath the brightness one -- both bands must be excluded from
    /// close-drag candidacy at once, and ordinary close-drag must resume
    /// only below both.
    #[test]
    fn volume_slider_band_owns_its_row_and_is_excluded_from_the_close_drag_candidacy() {
        let view = writable_volume_view();
        let settings_top = settings_row_y(SETTINGS_VOLUME_ROW);
        assert!(volume_slider_band(Route::Settings, settings_top + 10.0, &view));
        assert!(!volume_slider_band(
            Route::Settings,
            settings_row_y(1) + 10.0,
            &view
        ));
        assert!(volume_slider_band(Route::Shade, SHADE_VOLUME_TOP + 10.0, &view));
        assert!(!shade_panel_close_zone((300.0, SHADE_VOLUME_TOP + 10.0), 568, 1232, &view));
        // The brightness band just above it is also still excluded, with
        // both sliders present at once.
        assert!(!shade_panel_close_zone((300.0, SHADE_SLIDER_TOP + 10.0), 568, 1232, &view));
        let below = SHADE_VOLUME_TOP + SHADE_VOLUME_H + 40.0;
        assert!(!volume_slider_band(Route::Shade, below, &view));
        assert!(shade_panel_close_zone((300.0, below), 568, 1232, &view));
        // No default sink reported yet: the band must not steal gestures
        // from the placeholder text `render.rs` draws there instead.
        let unavailable = writable_brightness_view();
        assert!(!volume_slider_band(
            Route::Shade,
            SHADE_VOLUME_TOP + 10.0,
            &unavailable
        ));
        assert!(shade_panel_close_zone((300.0, SHADE_VOLUME_TOP + 10.0), 568, 1232,
            &unavailable
        ));
    }

    #[test]
    fn settings_output_picker_hit_is_settings_only_and_needs_a_default_sink() {
        let view = writable_volume_view();
        let y = settings_row_y(SETTINGS_VOLUME_ROW) + crate::render::settings_output_detail_y();
        assert!(settings_output_picker_hit(y, Route::Settings, &view));
        // Shade's compact volume row shows no such text and has no
        // equivalent zone, even at the analogous offset.
        assert!(!settings_output_picker_hit(
            SHADE_VOLUME_TOP + 76.0,
            Route::Shade,
            &view
        ));
        // Above the label or on the slider track itself: not the picker
        // zone.
        assert!(!settings_output_picker_hit(
            settings_row_y(SETTINGS_VOLUME_ROW) + 15.0,
            Route::Settings,
            &view
        ));
        assert!(!settings_output_picker_hit(
            settings_row_y(SETTINGS_VOLUME_ROW) + crate::render::settings_row_lines(SETTINGS_VOLUME_ROW).3,
            Route::Settings,
            &view
        ));
        // No default sink reported yet: never steals the gesture.
        let unavailable = writable_brightness_view();
        assert!(!settings_output_picker_hit(y, Route::Settings, &unavailable));
    }

    #[test]
    fn volume_icon_tap_zone_is_left_of_the_track_and_distinct_from_it() {
        let width = 568.0;
        let (left, _right) = slider::track_bounds(width);
        assert!(volume_icon_tap_zone(left - 20.0, width));
        assert!(!volume_icon_tap_zone(left + 5.0, width));
        assert!(!volume_icon_tap_zone(left - 200.0, width));
    }

    fn writable_brightness_view() -> ServiceView {
        ServiceView {
            settings: Some(SettingsSnapshot {
                network: Control {
                    state: ControlState::ReadOnly,
                    value: None,
                    label: "Available".into(),
                    detail: None,
                    action: None,
                },
                brightness: Control {
                    state: ControlState::Writable,
                    value: Some(ControlValue::Percent(50)),
                    label: "Brightness".into(),
                    detail: None,
                    action: None,
                },
                keyboard: Control {
                    state: ControlState::Action,
                    value: None,
                    label: "Available".into(),
                    detail: None,
                    action: None,
                },
                motion: Control {
                    state: ControlState::ReadOnly,
                    value: None,
                    label: "Available".into(),
                    detail: None,
                    action: None,
                },
                volume: Control {
                    state: ControlState::Writable,
                    value: Some(ControlValue::Percent(50)),
                    label: "Volume".into(),
                    detail: None,
                    action: None,
                },
            }),
            ..ServiceView::default()
        }
    }

    /// Gesture disambiguation (task: "a horizontal drag on the slider
    /// must not start a close drag, and a vertical drag elsewhere still
    /// closes"). `main.rs` arms the slider drag itself at touch-down
    /// using `slider_band`, entirely independent of which way the touch
    /// later moves -- so the real guarantee to test here is that
    /// `shade_panel_close_zone` (the close-drag *candidacy* gate sampled
    /// at that same touch-down) excludes the slider's own band but
    /// leaves every other band's existing behavior untouched.
    #[test]
    fn slider_band_owns_its_row_and_is_excluded_from_the_close_drag_candidacy() {
        let view = writable_brightness_view();
        // Settings' own brightness row.
        assert!(slider_band(
            Route::Settings,
            settings_row_y(1) + 10.0,
            &view
        ));
        assert!(!slider_band(
            Route::Settings,
            settings_row_y(2) + 10.0,
            &view
        ));
        // The Shade's header band -- excluded from `shade_panel_close_
        // zone` (a drag starting here, horizontal or not, never becomes
        // a close drag)...
        assert!(slider_band(Route::Shade, SHADE_SLIDER_TOP + 10.0, &view));
        assert!(!shade_panel_close_zone((300.0, SHADE_SLIDER_TOP + 10.0), 568, 1232, &view));
        // ...while a drag starting just below it, on the ordinary
        // backdrop/list, is untouched and still closes exactly as
        // before.
        let below = SHADE_SLIDER_TOP + SHADE_SLIDER_H + 40.0;
        assert!(!slider_band(Route::Shade, below, &view));
        assert!(shade_panel_close_zone((300.0, below), 568, 1232, &view));
        assert!(close_drag_engaged(Route::Shade, 4.0, -CLOSE_DRAG_SLOP));
        // When brightness is not writable, no slider is drawn there
        // (`render.rs`), so the band must not silently steal gestures
        // from whatever plain text sits in its place instead.
        let unavailable = ServiceView::default();
        assert!(!slider_band(Route::Shade, SHADE_SLIDER_TOP + 10.0, &unavailable));
        assert!(shade_panel_close_zone((300.0, SHADE_SLIDER_TOP + 10.0), 568, 1232,
            &unavailable
        ));
    }

    #[test]
    fn the_key_backlight_slider_owns_its_row_only_when_the_led_exists() {
        let view = |key_backlight| ServiceView {
            settings: Some(crate::evidence_render::fixture_settings()),
            key_backlight,
            ..ServiceView::default()
        };
        let tap = (200.0, settings_row_y(SETTINGS_KEY_BACKLIGHT_ROW) + 20.0);
        let high = view(Some(crate::keyboard_base::KeyBacklight::High));
        assert!(key_backlight_slider_hit(tap, 568, 1232, &high));
        assert!(!key_backlight_slider_hit(tap, 568, 1232, &view(None)));
        // The slider owns the row, so a tap there is not a release intent.
        assert_eq!(panel_intent(Route::Settings, tap, tap, 568, 1232, &high), None);
    }

    #[test]
    fn the_key_backlight_slider_snaps_to_four_levels_along_its_track() {
        use crate::keyboard_base::KeyBacklight;
        for (width, height) in [(568, 1232), (1232, 568)] {
            let (x, w) = key_backlight_slider_frame(width, height);
            let (left, right) = slider::track_bounds(w);
            let at = |f: f64| key_backlight_level_at(x + left + f * (right - left), x, w);
            assert_eq!(at(-0.5), KeyBacklight::Off, "{width}x{height} before the track");
            assert_eq!(at(0.0), KeyBacklight::Off);
            assert_eq!(at(0.3), KeyBacklight::Low);
            assert_eq!(at(0.7), KeyBacklight::Medium);
            assert_eq!(at(1.0), KeyBacklight::High);
            assert_eq!(at(1.5), KeyBacklight::High, "{width}x{height} past the track");
        }
    }

    type Rect = (f64, f64, f64, f64);

    /// Every Settings item's painted rect on the 1232x568 panel, in real
    /// pixels: the wide layout's per-column offset applied to the design
    /// rows, exactly as `render.rs` paints them.
    #[test]
    fn the_power_sheet_confirmation_is_two_buttons_with_room_below_and_swipes_away() {
        // On the landscape board, 2026-10-14: the first real Confirm taps
        // landed at y=505..507, just under the old 432..500 band, and a
        // swipe up the sheet did nothing.
        let mut view = ServiceView {
            confirmation: Some(Confirmation {
                token: "t".into(),
                action: PowerAction::Reboot,
                label: "Restart device?".into(),
                expires_at: Instant::now() + std::time::Duration::from_secs(30),
            }),
            ..ServiceView::default()
        };
        let tap = |x: f64, y: f64, view: &ServiceView| panel_intent(Route::Power, (x, y), (x, y), 1232, 568, view);
        for y in [432.0, 486.5, 505.4, 507.5, 525.0] {
            assert_eq!(
                tap(685.8, y, &view),
                Some(PanelIntent::Request(ServiceRequest::PowerConfirm("t".into()))),
                "Confirm at y={y}"
            );
            assert_eq!(
                tap(51.8, y, &view),
                Some(PanelIntent::Request(ServiceRequest::PowerCancel("t".into()))),
                "Cancel at y={y}"
            );
        }
        // The board's own swipe, from the Cancel row nearly to the top.
        assert_eq!(panel_intent(Route::Power, (524.1, 328.2), (457.9, 5.8), 1232, 568, &view), Some(PanelIntent::Hide));
        view.confirmation = None;
        assert_eq!(panel_intent(Route::Power, (524.1, 328.2), (457.9, 5.8), 1232, 568, &view), Some(PanelIntent::Hide));
        // A short wobble is still a tap on the row it started on.
        assert_eq!(
            panel_intent(Route::Power, (100.0, 160.0), (104.0, 150.0), 1232, 568, &view),
            Some(PanelIntent::Request(ServiceRequest::PowerRequest(PowerAction::Reboot)))
        );
        assert_eq!(crate::render::power_confirm_label(PowerAction::Reboot), "Restart");
        assert_eq!(crate::render::power_confirm_label(PowerAction::Poweroff), "Power off");
    }

    fn wide_settings_items(key_backlight: bool) -> Vec<(&'static str, Rect)> {
        use crate::render::{settings_power_card_h, settings_row_column, settings_wide_offset};
        let layout = settings_layout(key_backlight);
        let row = |name, row| (name, row, settings_row_y(row), settings_row_h(row));
        let mut items = vec![
            row("wifi", 0),
            row("brightness", 1),
            row("volume", SETTINGS_VOLUME_ROW),
            row("keyboard", 3),
            row("motion", 4),
        ];
        if key_backlight {
            items.push(row("key-backlight", SETTINGS_KEY_BACKLIGHT_ROW));
        }
        let mut out: Vec<_> = items
            .into_iter()
            .map(|(name, row, y, h)| {
                let (dx, dy) = settings_wide_offset(settings_row_column(row), key_backlight);
                (name, (dx + 24.0, y + dy, crate::SETTINGS_WIDE_COL_W - 48.0, h))
            })
            .collect();
        let (dx, dy) = settings_wide_offset(2, key_backlight);
        for (name, y) in [("reboot", layout.reboot_y), ("poweroff", layout.poweroff_y)] {
            out.push((name, (dx + 24.0, y + dy, crate::SETTINGS_WIDE_COL_W - 48.0, settings_power_card_h())));
        }
        out
    }

    #[test]
    fn every_wide_settings_row_is_inside_the_landscape_panel_and_taps_at_its_centre() {
        for key_backlight in [false, true] {
            let view = ServiceView {
                settings: Some(crate::evidence_render::fixture_settings()),
                key_backlight: key_backlight.then_some(crate::keyboard_base::KeyBacklight::Off),
                ..ServiceView::default()
            };
            let mut view = view;
            let items = wide_settings_items(key_backlight);
            assert_eq!(items.len(), if key_backlight { 8 } else { 7 });
            // The body scrolls under the header; every row is inside the
            // panel's width and within the scroll range.
            let top = settings_body_top(1232, 568);
            let max = settings_max_scroll(1232, 568, &view);
            for (name, (x, y, w, h)) in &items {
                assert!(
                    *x >= 0.0 && *y >= top && x + w <= 1232.0 && y + h <= 568.0 + max,
                    "{name} ({x},{y},{w},{h}) leaves 1232x568 scrolled by {max} (key backlight {key_backlight})"
                );
            }
            // Scrolled just far enough to show a row whole.
            let reveal = |(_, y, _, h): Rect| (y + h - 568.0 + 8.0).clamp(0.0, max);
            for (i, a) in items.iter().enumerate() {
                for b in &items[i + 1..] {
                    let (ax, ay, aw, ah) = a.1;
                    let (bx, by, bw, bh) = b.1;
                    assert!(
                        ax + aw <= bx || bx + bw <= ax || ay + ah <= by || by + bh <= ay,
                        "{} overlaps {}",
                        a.0,
                        b.0
                    );
                }
            }
            for (name, (x, y, w, h)) in &items {
                view.settings_scroll = reveal((*x, *y, *w, *h));
                let tap = (x + w / 2.0, y + h / 2.0 - view.settings_scroll);
                assert!(tap.1 > top && tap.1 < 568.0, "{name} centre is on screen");
                let intent = panel_intent(Route::Settings, tap, tap, 1232, 568, &view);
                let expected = match *name {
                    "wifi" => Some(PanelIntent::OpenWifi),
                    "keyboard" => Some(PanelIntent::Request(ServiceRequest::KeyboardToggle)),
                    "reboot" => Some(PanelIntent::Request(ServiceRequest::PowerRequest(PowerAction::Reboot))),
                    "poweroff" => Some(PanelIntent::Request(ServiceRequest::PowerRequest(PowerAction::Poweroff))),
                    // The sliders (Key backlight's too) own their rows' touches
                // and Motion is read only.
                    _ => None,
                };
                assert_eq!(intent, expected, "tap at the centre of {name} (key backlight {key_backlight})");
            }
            if key_backlight {
                let row = items.iter().find(|i| i.0 == "key-backlight").unwrap().1;
                view.settings_scroll = reveal(row);
                let centre = (row.0 + row.2 / 2.0, row.1 + row.3 / 2.0 - view.settings_scroll);
                assert!(key_backlight_slider_hit(centre, 1232, 568, &view));
                // The same y in the first column is Volume, not this slider.
                assert!(!key_backlight_slider_hit((100.0, centre.1), 1232, 568, &view));
            }
            // The slider rows are owned by the sliders only inside column 0.
            let brightness = items.iter().find(|i| i.0 == "brightness").unwrap().1;
            let motion = items.iter().find(|i| i.0 == "motion").unwrap().1;
            view.settings_scroll = 0.0;
            let band_y = settings_slider_y(Route::Settings, brightness.1 + 10.0, 1232, 568);
            assert!(slider_band(Route::Settings, band_y, &writable_brightness_view()));
            assert!(settings_slider_column_hit(Route::Settings, 1232, 568, brightness.0 + 40.0));
            assert!(!settings_slider_column_hit(Route::Settings, 1232, 568, motion.0 + 40.0));
            assert!(settings_slider_column_hit(Route::Settings, 568, 1232, 400.0));
            // Dead space above a column's first row, or below its last,
            // never reaches another column's row.
            for x in [200.0, 600.0, 1000.0] {
                let tap = (x, settings_body_top(1232, 568) + 2.0);
                assert_eq!(panel_intent(Route::Settings, tap, tap, 1232, 568, &view), None);
            }
        }
    }

    #[test]
    fn the_wide_power_confirmation_sits_in_the_third_column_inside_the_panel() {
        for key_backlight in [false, true] {
            let view = ServiceView {
                settings: Some(crate::evidence_render::fixture_settings()),
                key_backlight: key_backlight.then_some(crate::keyboard_base::KeyBacklight::Off),
                confirmation: Some(Confirmation {
                    token: "t".into(),
                    action: PowerAction::Reboot,
                    label: "Reboot now?".into(),
                    expires_at: Instant::now() + std::time::Duration::from_secs(30),
                }),
                message: Some("Tap Confirm to reboot".into()),
                ..ServiceView::default()
            };
            let layout = settings_layout(key_backlight);
            let confirm = settings_confirm_layout(layout.poweroff_bottom);
            let (dx, dy) = crate::render::settings_wide_offset(2, key_backlight);
            // Scrolled to the end, the card and the message line below it
            // are on the panel.
            let mut view = view;
            view.settings_scroll = settings_max_scroll(1232, 568, &view);
            let scroll = view.settings_scroll;
            let (top, bottom) = (confirm.card_y + dy - scroll, confirm.bottom + dy - scroll);
            assert!(top > settings_body_top(1232, 568));
            let message = 14.0 + crate::render::TYPE_CAPTION * 1.25;
            assert!(bottom + message <= 568.0, "confirm + message end at {}", bottom + message);
            let y = (top + bottom) / 2.0;
            let cancel = (dx + 60.0, y);
            let ok = (dx + crate::SETTINGS_WIDE_COL_W - 60.0, y);
            assert_eq!(
                panel_intent(Route::Settings, cancel, cancel, 1232, 568, &view),
                Some(PanelIntent::Request(ServiceRequest::PowerCancel("t".into())))
            );
            assert_eq!(
                panel_intent(Route::Settings, ok, ok, 1232, 568, &view),
                Some(PanelIntent::Request(ServiceRequest::PowerConfirm("t".into())))
            );
        }
    }

    #[test]
    fn the_portrait_keyboard_row_taps_toggle_the_keyboard() {
        let view = ServiceView {
            settings: Some(crate::evidence_render::fixture_settings()),
            ..ServiceView::default()
        };
        let tap = (200.0, settings_row_y(3) + 20.0);
        assert_eq!(
            panel_intent(Route::Settings, tap, tap, 568, 1232, &view),
            Some(PanelIntent::Request(ServiceRequest::KeyboardToggle))
        );
    }

    fn shade_view_with_keyboard(state: ControlState, notifications: usize) -> ServiceView {
        let control = |state| Control { state, value: None, label: "Available".into(), detail: None, action: None };
        ServiceView {
            settings: Some(SettingsSnapshot {
                network: control(ControlState::ReadOnly),
                brightness: control(ControlState::ReadOnly),
                keyboard: control(state),
                motion: control(ControlState::ReadOnly),
                volume: control(ControlState::ReadOnly),
            }),
            notifications: Some(NotificationSnapshot {
                count: notifications,
                events: (1..=notifications as u64)
                    .map(|id| NotificationEvent {
                        id,
                        source: "System".into(),
                        icon: None,
                        summary: "Message".into(),
                        body: "Body".into(),
                        priority: Priority::Ordinary,
                        timestamp: 0,
                        error: None,
                        dismissible: true,
                        action_available: true,
                    })
                    .collect(),
                preview: None,
            }),
            ..ServiceView::default()
        }
    }

    #[test]
    fn the_shade_keyboard_toggle_sends_the_settings_request_only_when_available() {
        for (w, h) in [(568, 1232), (1232, 568), (1280, 800)] {
            let layout = shade_layout(w, h);
            // The wide Shade's keyboard toggle is its second tile.
            let tap = if layout.wide {
                let (x, y, tw, th) = shade_tile_rect(1, layout.controls_w);
                (x + tw / 2.0, y + th / 2.0)
            } else {
                (layout.controls_w / 2.0, SHADE_TOGGLE_TOP + shade_toggle_h() / 2.0)
            };
            let action = shade_view_with_keyboard(ControlState::Action, 1);
            assert_eq!(
                panel_intent(Route::Shade, tap, tap, w, h, &action),
                Some(PanelIntent::Request(ServiceRequest::KeyboardToggle)),
                "{w}x{h}"
            );
            // Unavailable or read-only: the same gate as the Settings row,
            // so the tap does nothing rather than send a request.
            for state in [ControlState::Unavailable, ControlState::ReadOnly] {
                let view = shade_view_with_keyboard(state, 1);
                assert_eq!(panel_intent(Route::Shade, tap, tap, w, h, &view), None, "{w}x{h} {state:?}");
            }
            // Both edges of the band still hit (the wide tile's are tested
            // with the other tiles).
            if layout.wide {
                continue;
            }
            for y in [SHADE_TOGGLE_TOP, SHADE_TOGGLE_TOP + shade_toggle_h() - 0.5] {
                assert!(panel_intent(Route::Shade, (tap.0, y), (tap.0, y), w, h, &action).is_some());
            }
        }
    }

    #[test]
    fn every_shade_tap_band_meets_the_floor_without_overlap() {
        // Settings entry, Dismiss all and the keyboard toggle are the
        // Shade's tap targets; notification rows are NOTIFICATION_ROW tall.
        let bands = [
            ("settings", 0.0, SHADE_SETTINGS_BOTTOM),
            ("dismiss all", SHADE_DISMISS_TOP, SHADE_DISMISS_BOTTOM),
            ("keyboard", SHADE_TOGGLE_TOP, SHADE_TOGGLE_TOP + shade_toggle_h()),
        ];
        for (name, top, bottom) in bands {
            assert!(bottom - top >= SHADE_TAP_MIN, "{name}: {} px", bottom - top);
        }
        assert!(NOTIFICATION_ROW >= SHADE_TAP_MIN);
        // Ordered top to bottom with the drag bands, never overlapping.
        let all = [
            (0.0, SHADE_SETTINGS_BOTTOM),
            (SHADE_DISMISS_TOP, SHADE_DISMISS_BOTTOM),
            (SHADE_SLIDER_TOP, SHADE_SLIDER_TOP + SHADE_SLIDER_H),
            (SHADE_VOLUME_TOP, SHADE_VOLUME_TOP + SHADE_VOLUME_H),
            (SHADE_TOGGLE_TOP, SHADE_TOGGLE_TOP + shade_toggle_h()),
            (notification_top(), notification_top() + NOTIFICATION_ROW),
        ];
        for pair in all.windows(2) {
            assert!(pair[0].1 <= pair[1].0, "{:?} overlaps {:?}", pair[0], pair[1]);
        }
        // "Dismiss all" now fires across its whole 99 px band, including
        // the 22 px above and 21 px below the old 116..190 zone.
        let view = shade_view_with_keyboard(ControlState::Action, 2);
        for y in [SHADE_DISMISS_TOP + 1.0, 150.0, 200.0, SHADE_DISMISS_BOTTOM - 1.0] {
            assert_eq!(
                panel_intent(Route::Shade, (500.0, y), (500.0, y), 568, 1232, &view),
                Some(PanelIntent::Request(ServiceRequest::NotificationDismissAll)),
                "y {y}"
            );
        }
        // The Settings entry keeps its band right above it.
        assert_eq!(panel_intent(Route::Shade, (500.0, 100.0), (500.0, 100.0), 568, 1232, &view), Some(PanelIntent::OpenSettings));
    }

    #[test]
    fn the_largest_text_step_scrolls_settings_and_keeps_every_row_reachable() {
        crate::set_layout_text_scale(2.0);
        let mut view = ServiceView {
            settings: Some(crate::evidence_render::fixture_settings()),
            ..ServiceView::default()
        };
        for (width, height) in [(568u32, 1232u32), (1232, 568)] {
            view.settings_scroll = 0.0;
            let max = settings_max_scroll(width, height, &view);
            assert!(max > 0.0, "200% rows overflow {width}x{height} and must scroll");
            // Each row's text lines (at 200%: line height = size x 2 x 1.25)
            // end inside its card, above the slider band where it has one.
            let line = |size: f64| size * 2.0 * 1.25;
            for row in [0, 3, 4] {
                let (_, value, caption, _) = crate::render::settings_row_lines(row);
                let captions = if row == 3 { 2.0 } else { 1.0 };
                assert!(value + line(crate::render::TYPE_BODY) <= caption);
                assert!(caption + captions * line(crate::render::TYPE_CAPTION) <= settings_row_h(row), "row {row} clips");
            }
            for row in [1, SETTINGS_KEY_BACKLIGHT_ROW] {
                let (_, value, _, slider) = crate::render::settings_row_lines(row);
                assert!(value + line(crate::render::TYPE_BODY) <= slider - 28.0 + 4.0, "row {row} text runs into its slider");
                assert!(slider + 28.0 <= settings_row_h(row));
            }
            // Rows stack without overlap, each at least the tap floor.
            for row in 0..SETTINGS_KEY_BACKLIGHT_ROW {
                assert!(settings_row_h(row) >= SHADE_TAP_MIN);
                assert!(settings_row_y(row) + settings_row_h(row) < settings_row_y(row + 1));
            }
            // The header bands do not overlap and the rows start below them.
            let head = crate::render::settings_header(f64::from(width));
            assert!(head.vision_x.1 <= head.themes_x.0 && head.vision_x.0 >= 0.0);
            // The links have their own row, or share the Title's row left of Done.
            assert!(head.links_y.0 >= head.done_bottom || head.themes_x.1 <= head.done_x);
            assert!(head.first_y > head.links_y.1);
            assert!(settings_body_top(width, height) >= head.links_y.1);
            if width == 568 {
                // Scrolled to the end, Power off is tappable where it is drawn.
                view.settings_scroll = max;
                let layout = settings_layout(false);
                let y = layout.poweroff_y + settings_power_card_h() / 2.0 - max;
                assert!(y < f64::from(height) && y > settings_body_top(width, height));
                assert_eq!(
                    panel_intent(Route::Settings, (200.0, y), (200.0, y), width, height, &view),
                    Some(PanelIntent::Request(ServiceRequest::PowerRequest(PowerAction::Poweroff)))
                );
                // A tap on the header strip never reaches a scrolled row.
                let header_y = settings_body_top(width, height) - 4.0;
                assert_eq!(panel_intent(Route::Settings, (60.0, header_y), (60.0, header_y), width, height, &view), None);
            }
        }
        let head_first_y_at_200 = crate::render::settings_header(568.0).first_y;
        crate::set_layout_text_scale(1.0);
        // At 100% the portrait rows and Power section nearly fit; the
        // header and rows use the same type roles at every step.
        // The two always-present rows (Date & time, About) may push the
        // portrait page past the panel, by no more than their own height
        // plus 100 px of slack for the overflow it had before them.
        let added = f64::from(crate::render::SETTINGS_INFO_ROWS)
            * (crate::render::settings_modem_row_h() + crate::render::SETTINGS_ROW_GAP);
        assert!(settings_max_scroll(568, 1232, &view) <= added + 100.0, "{}", settings_max_scroll(568, 1232, &view));
        assert!(crate::render::settings_header(568.0).first_y < head_first_y_at_200);
    }

    #[test]
    fn the_largest_text_step_grows_notification_rows_and_header_links() {
        crate::set_layout_text_scale(2.0);
        // Source, summary and body at 200%, stacked with their gaps, fit
        // inside the card (row minus its 8 px gutter).
        use crate::render::{TYPE_BODY, TYPE_CAPTION, TYPE_LABEL};
        let lines = 13.0 + (TYPE_LABEL + TYPE_BODY + TYPE_CAPTION) * 2.0 * 1.25 + 8.0;
        assert!(notification_row() - 8.0 >= lines);
        for width in [568.0, SHADE_WIDE_CONTROLS_W] {
            assert_eq!(shade_link_w(width), 360.0_f64.min(width * 0.5));
        }
        let layout = shade_layout(568, 1232);
        assert!(layout.list_bottom - layout.list_top >= notification_row(), "one whole row fits");
        crate::set_layout_text_scale(1.0);
        let lines = 13.0 + (TYPE_LABEL + TYPE_BODY + TYPE_CAPTION) * 1.25 + 8.0;
        assert!(notification_row() - 8.0 >= lines && notification_row() >= NOTIFICATION_ROW);
        assert_eq!(shade_link_w(568.0), 180.0);
    }

    #[test]
    fn shade_and_settings_hits_are_bounded_and_cancel_scroll_taps() {
        let view = ServiceView {
            notifications: Some(NotificationSnapshot {
                count: 1,
                events: vec![NotificationEvent {
                    id: 7,
                    source: "Terminal".into(),
                    icon: Some("foot".into()),
                    summary: "Ready".into(),
                    body: "Action available".into(),
                    priority: Priority::Ordinary,
                    timestamp: 0,
                    error: None,
                    dismissible: true,
                    action_available: true,
                }],
                preview: None,
            }),
            ..ServiceView::default()
        };
        assert_eq!(
            panel_intent(
                Route::Shade,
                (300.0, 514.0),
                (400.0, 519.0),
                568,
                1232,
                &view
            ),
            None // release alone cannot dismiss without a tracked drag
        );
        assert_eq!(
            notification_swipe_start((300.0, 514.0), (400.0, 519.0), 568, 1232, &view)
                .map(|swipe| swipe.event_id),
            Some(7),
        );
        assert_eq!(
            panel_intent(
                Route::Shade,
                (300.0, 514.0),
                (300.0, 604.0),
                568,
                1232,
                &view
            ),
            Some(PanelIntent::ScrollNotifications(-90.0))
        );
        assert_eq!(
            panel_intent(
                Route::Shade,
                (300.0, 514.0),
                (300.0, 514.0),
                568,
                1232,
                &view
            ),
            Some(PanelIntent::Request(ServiceRequest::NotificationAction(7)))
        );
        assert_eq!(
            panel_intent(Route::Shade, (510.0, 60.0), (510.0, 60.0), 568, 1232, &view),
            Some(PanelIntent::OpenSettings)
        );
    }

    /// Shade and Settings are both top-anchored overlay sheets (Settings
    /// opens from within the shade's own downward pull -- design.md
    /// decision 3), so `docs/design/shell-ux-critique.md` S2's "three
    /// direction-inconsistent dismiss gestures" finding is fixed by giving
    /// them one shared rule: drag back up, toward their shared top anchor,
    /// to dismiss. A downward drag near the top -- Settings' old direction
    /// -- must no longer dismiss either route, and an upward drag must
    /// dismiss both identically.
    #[test]
    fn shade_and_settings_share_one_upward_dismiss_direction() {
        let settings_view = ServiceView {
            settings: Some(SettingsSnapshot {
                network: Control {
                    state: ControlState::ReadOnly,
                    value: None,
                    label: "Available".into(),
                    detail: None,
                    action: None,
                },
                brightness: Control {
                    state: ControlState::Writable,
                    value: Some(ControlValue::Percent(50)),
                    label: "Available".into(),
                    detail: None,
                    action: None,
                },
                keyboard: Control {
                    state: ControlState::Action,
                    value: None,
                    label: "Available".into(),
                    detail: None,
                    action: None,
                },
                motion: Control {
                    state: ControlState::ReadOnly,
                    value: None,
                    label: "Available".into(),
                    detail: None,
                    action: None,
                },
                volume: Control {
                    state: ControlState::Writable,
                    value: Some(ControlValue::Percent(50)),
                    label: "Available".into(),
                    detail: None,
                    action: None,
                },
            }),
            ..ServiceView::default()
        };
        let shade_view = ServiceView::default();
        for (route, view) in [(Route::Shade, &shade_view), (Route::Settings, &settings_view)] {
            // Same start zone, same upward threshold, same result: Hide.
            assert_eq!(
                panel_intent(route, (200.0, 150.0), (200.0, 40.0), 568, 1232, view),
                Some(PanelIntent::Hide),
                "{route:?} must dismiss on an upward swipe near the top"
            );
            // The old, now-retired downward direction must not dismiss
            // either route anymore.
            assert_ne!(
                panel_intent(route, (200.0, 40.0), (200.0, 150.0), 568, 1232, view),
                Some(PanelIntent::Hide),
                "{route:?} must not still dismiss on a downward swipe"
            );
            // Starting below the shared dismiss zone never dismisses,
            // regardless of direction.
            assert_ne!(
                panel_intent(route, (200.0, 400.0), (200.0, 290.0), 568, 1232, view),
                Some(PanelIntent::Hide)
            );
        }
    }

    #[test]
    fn notification_swipe_tracks_reversal_and_refuses_critical_or_changed_rows() {
        let event = NotificationEvent {
            id: 7,
            source: "System".into(),
            icon: None,
            summary: "Message".into(),
            body: "Body".into(),
            priority: Priority::Ordinary,
            timestamp: 0,
            error: None,
            dismissible: true,
            action_available: true,
        };
        let mut view = ServiceView {
            notifications: Some(NotificationSnapshot {
                count: 1,
                events: vec![event],
                preview: None,
            }),
            ..ServiceView::default()
        };
        let start = (300.0, 514.0);
        assert_eq!(
            notification_swipe_start(start, (320.0, 519.0), 568, 1232, &view)
                .map(|swipe| swipe.event_id),
            Some(7),
        );
        assert_eq!(notification_swipe_offset(300.0, 410.0), 110.0);
        assert_eq!(notification_swipe_offset(300.0, 312.0), 12.0);
        assert_eq!(notification_swipe_offset(300.0, 1000.0), 160.0);
        let swipe = NotificationSwipe {
            event_id: 7,
            row_index: 0,
            offset: 110.0,
        };
        assert_eq!(
            notification_swipe_release(&view, &swipe, 0.0),
            Some(ServiceRequest::NotificationDismiss(7))
        );
        assert_eq!(
            notification_swipe_release(
                &view,
                &NotificationSwipe {
                    offset: 12.0,
                    ..swipe.clone()
                },
                0.0,
            ),
            None
        );
        assert_eq!(notification_swipe_release(&view, &swipe, 220.0), None);
        assert_eq!(
            notification_swipe_start(start, (320.0, 426.0), 568, 1232, &view),
            None
        );
        view.notifications.as_mut().unwrap().events[0].dismissible = false;
        assert_eq!(
            notification_swipe_start(start, (400.0, 514.0), 568, 1232, &view),
            None
        );
        assert!(!notification_swipe_valid(&view, &swipe));
        assert_eq!(notification_swipe_release(&view, &swipe, 0.0), None);
        view.notifications.as_mut().unwrap().events[0].dismissible = true;
        view.notifications.as_mut().unwrap().events[0].priority = Priority::Critical;
        assert_eq!(
            notification_swipe_start(start, (400.0, 514.0), 568, 1232, &view),
            None
        );
        assert_eq!(notification_swipe_release(&view, &swipe, 0.0), None);
        view.notifications.as_mut().unwrap().events[0].id = 8;
        assert!(!notification_swipe_valid(&view, &swipe));
        view.notifications.as_mut().unwrap().events[0].id = 7;
        view.notifications.as_mut().unwrap().events[0].priority = Priority::Ordinary;
        assert!(notification_swipe_valid(&view, &swipe));
        view.notification_swipe = Some(swipe.clone());
        assert_eq!(panel_intent(Route::Shade, start, start, 568, 1232, &view), None);
        view.notification_swipe = None;
        assert_eq!(
            panel_intent(Route::Shade, start, start, 568, 1232, &view),
            Some(PanelIntent::Request(ServiceRequest::NotificationAction(7)))
        );
        let mut newer = view.notifications.as_ref().unwrap().events[0].clone();
        newer.id = 8;
        view.notifications.as_mut().unwrap().events.insert(0, newer);
        assert!(!notification_swipe_valid(&view, &swipe));
    }

    #[test]
    fn notification_release_settles_from_current_pixels_and_can_be_interrupted() {
        let mut offset = 110.0;
        let mut settle = NotificationSwipeSettle::new(offset, 0.0, None, false);
        assert_eq!(offset, 110.0); // no release-time jump
        assert!(settle.tick(&mut offset, 16));
        assert!(offset < 110.0 && offset > 0.0);
        let interrupted = offset;
        // A new finger can take the exact displayed offset as its next anchor.
        offset = interrupted + 24.0;
        assert_eq!(offset, interrupted + 24.0);
        let mut exit = NotificationSwipeSettle::new(offset, 568.0, Some(7), false);
        assert_eq!(offset, interrupted + 24.0);
        for _ in 0..20 {
            exit.tick(&mut offset, 16);
        }
        assert!(exit.finished());
        assert_eq!(offset, 568.0);
        assert_eq!(exit.dismiss_id, Some(7));
    }

    #[test]
    fn notification_scroll_coast_is_bounded_and_tap_stops_without_jump() {
        let mut coast = NotificationCoast::default();
        let mut scroll = 120.0;
        coast.start(1.2);
        assert!(coast.tick(&mut scroll, 400.0, 16));
        assert!(scroll > 120.0 && scroll < 400.0);
        let held = scroll;
        assert!(coast.stop());
        assert!(!coast.tick(&mut scroll, 400.0, 16));
        assert_eq!(scroll, held);
        coast.start(2.0);
        for _ in 0..60 {
            coast.tick(&mut scroll, 400.0, 16);
        }
        assert!(scroll <= 400.0);
        assert!(!coast.moving());
        coast.start(-2.0);
        for _ in 0..60 {
            coast.tick(&mut scroll, 400.0, 16);
        }
        assert!(scroll >= 0.0);
        assert!(!coast.moving());
    }

    #[test]
    fn power_needs_loaded_settings_and_token_confirmation() {
        let mut view = ServiceView::default();
        assert_eq!(
            panel_intent(
                Route::Settings,
                (60.0, 730.0),
                (60.0, 730.0),
                568,
                1232,
                &view
            ),
            None
        );
        let unavailable = Control {
            state: ControlState::Unavailable,
            value: None,
            label: "Unavailable".into(),
            detail: None,
            action: None,
        };
        view.settings = Some(SettingsSnapshot {
            network: unavailable.clone(),
            brightness: unavailable.clone(),
            keyboard: unavailable.clone(),
            motion: unavailable.clone(),
            volume: unavailable,
        });
        // The Reboot card's centre, from the row rhythm.
        let reboot = settings_layout(false).reboot_y + crate::render::settings_power_card_h() / 2.0;
        assert_eq!(
            panel_intent(
                Route::Settings,
                (60.0, reboot),
                (60.0, reboot),
                568,
                1232,
                &view
            ),
            Some(PanelIntent::Request(ServiceRequest::PowerRequest(
                PowerAction::Reboot
            )))
        );
        view.confirmation = Some(Confirmation {
            token: "opaque-token".into(),
            action: PowerAction::Reboot,
            label: "Restart device?".into(),
            expires_at: Instant::now() + std::time::Duration::from_secs(30),
        });
        // The dialog is below the Power section; scrolled to the end it is
        // on screen.
        view.settings_scroll = settings_max_scroll(568, 1232, &view);
        let confirm = settings_confirm_layout(settings_layout(false).poweroff_bottom);
        let buttons = (confirm.card_y + confirm.bottom) / 2.0 - view.settings_scroll;
        assert!(buttons < 1232.0);
        let reboot = reboot - view.settings_scroll;
        assert_eq!(
            panel_intent(
                Route::Settings,
                (60.0, reboot),
                (60.0, reboot),
                568,
                1232,
                &view
            ),
            None
        );
        assert_eq!(
            panel_intent(
                Route::Settings,
                (80.0, buttons),
                (80.0, buttons),
                568,
                1232,
                &view
            ),
            Some(PanelIntent::Request(ServiceRequest::PowerCancel(
                "opaque-token".into()
            )))
        );
        assert_eq!(
            panel_intent(
                Route::Settings,
                (440.0, buttons),
                (440.0, buttons),
                568,
                1232,
                &view
            ),
            Some(PanelIntent::Request(ServiceRequest::PowerConfirm(
                "opaque-token".into()
            )))
        );
        view.confirmation.as_mut().unwrap().expires_at = Instant::now();
        assert_eq!(
            panel_intent(
                Route::Settings,
                (440.0, buttons),
                (440.0, buttons),
                568,
                1232,
                &view
            ),
            None
        );
        view.confirmation.as_mut().unwrap().expires_at =
            Instant::now() + std::time::Duration::from_secs(30);
        let request = ServiceRequest::PowerConfirm("opaque-token".into());
        assert!(!view.request_queued(&request, false));
        assert!(view.confirmation.is_some());
        assert!(view.request_queued(&request, true));
        assert!(view.confirmation.is_none());
    }

    #[test]
    fn settings_row_taps_follow_the_scaled_centered_content_column_on_hdmi() {
        // Same fixture/tap `power_needs_loaded_settings_and_token_
        // confirmation` uses at the native 568x1232 (the reboot row after
        // settings loads, at design-space (60.0, 856.0)) -- but the touch
        // point is now real-pixel coordinates on a wide *and* a tall HDMI
        // output, mapped through `crate::settings_content_transform` (the
        // exact function `render.rs`'s `scene` uses to paint that same row)
        // rather than hand-picked literals, so this stays correct if that
        // transform's own formula ever changes.
        let unavailable = Control {
            state: ControlState::Unavailable,
            value: None,
            label: "Unavailable".into(),
            detail: None,
            action: None,
        };
        let mut view = ServiceView {
            settings: Some(SettingsSnapshot {
                network: unavailable.clone(),
                brightness: unavailable.clone(),
                keyboard: unavailable.clone(),
                motion: unavailable.clone(),
                volume: unavailable,
            }),
            ..ServiceView::default()
        };
        let design_point = (60.0, settings_layout(false).reboot_y + crate::render::settings_power_card_h() / 2.0);
        for (width, height) in [(1280u32, 1024u32), (1080u32, 1920u32)] {
            let (scale, x) = crate::settings_content_transform(width, height);
            // Scrolled to the end, where the Power section is on screen.
            view.settings_scroll = settings_max_scroll(width, height, &view);
            let real_point = (design_point.0 * scale + x, design_point.1 * scale - view.settings_scroll);
            assert!(real_point.1 > settings_body_top(width, height) && real_point.1 < f64::from(height));
            assert_eq!(
                panel_intent(Route::Settings, real_point, real_point, width, height, &view),
                Some(PanelIntent::Request(ServiceRequest::PowerRequest(PowerAction::Reboot))),
                "the reboot row's real on-screen position at {width}x{height} must still resolve"
            );
            // A point just past the row, in the same real coordinate space,
            // must still miss -- confirms this isn't accidentally hitting
            // on every tap regardless of position.
            let miss_point = (real_point.0, real_point.1 + 400.0 * scale);
            assert_eq!(
                panel_intent(Route::Settings, miss_point, miss_point, width, height, &view),
                None,
                "well past the row, at {width}x{height}, must still miss"
            );
        }
    }

    #[test]
    fn failed_action_hides_backend_code_and_names_recovery() {
        let outcome = ActionOutcome {
            state: "failed".into(),
            error: Some("target-unavailable".into()),
            token: None,
            label: None,
            power_action: None,
            expires_in_seconds: None,
            requested_percent: None,
            brightness: None,
            retry: true,
            remaining: None,
        };
        assert_eq!(action_message(&outcome, "Done"), "That didn't work · Retry");
        let denied = ActionOutcome {
            error: Some("action-denied".into()),
            retry: false,
            ..outcome
        };
        let message = action_message(&denied, "Cancel");
        assert_eq!(message, "That action isn't allowed · Cancel");
        assert!(crate::recovery::person_safe(&message));
    }

    #[test]
    fn keyboard_gesture_hint_requires_integrated_session_flag() {
        assert!(!ServiceView::default().keyboard_gesture_hint);
    }

    #[test]
    fn a_tap_on_the_backdrop_closes_but_a_tap_on_the_sheet_does_not() {
        let travel = 800.0;
        assert!(backdrop_tap(Route::Shade, (284.0, 1000.0), (286.0, 1004.0), travel));
        assert!(backdrop_tap(Route::Settings, (100.0, 900.0), (100.0, 900.0), travel));
        assert!(!backdrop_tap(Route::Shade, (284.0, 500.0), (284.0, 500.0), travel));
        assert!(!backdrop_tap(Route::Shade, (284.0, 1000.0), (284.0, 900.0), travel));
        assert!(!backdrop_tap(Route::Drawer, (284.0, 1000.0), (284.0, 1000.0), travel));
    }


    fn wide_shade_view(count: usize, with_audio: bool) -> ServiceView {
        ServiceView {
            settings: Some(crate::evidence_render::fixture_settings()),
            notifications: Some(crate::service_data::NotificationSnapshot {
                count,
                events: crate::evidence_render::fixture_notification_events(count),
                preview: None,
            }),
            audio: with_audio.then(|| crate::pipewire_ipc::GraphSnapshot {
                sinks: vec![crate::pipewire_ipc::Sink {
                    id: 1,
                    name: "speaker".into(),
                    description: "Speaker".into(),
                    linear_volume: 0.5,
                    muted: false,
                    is_default: true,
                    route: None,
                }],
                streams: vec![],
            }),
            ..ServiceView::default()
        }
    }

    #[test]
    fn the_wide_shade_puts_controls_left_and_a_full_height_list_right() {
        let wide = shade_layout(1232, 568);
        assert!(wide.wide);
        assert!(wide.controls_w <= wide.list_x, "controls do not run under the list");
        assert!(wide.list_x + wide.list_w <= 1232.0);
        assert!(wide.list_top >= 0.0 && wide.list_bottom <= 568.0);
        assert!(
            wide.list_bottom - wide.list_top >= 3.0 * NOTIFICATION_ROW,
            "at least three rows are visible at once"
        );
        // The sliders sit entirely in the left column.
        assert!(SHADE_VOLUME_TOP + SHADE_VOLUME_H <= wide.list_bottom);
        // Portrait outputs and a 5:4 monitor keep the single column exactly.
        for (w, h) in [(568, 1232), (768, 1024), (1080, 1920), (1280, 1024)] {
            let layout = shade_layout(w, h);
            assert!(!layout.wide);
            assert_eq!((layout.list_x, layout.list_top, layout.controls_w), (0.0, notification_top(), f64::from(w)));
        }
    }

    #[test]
    fn every_wide_shade_control_is_inside_the_panel_and_taps_at_its_centre() {
        let layout = shade_layout(1232, 568);
        let view = wide_shade_view(6, true);
        // Settings heads the controls column; Dismiss all heads the list.
        for (name, point, expected) in [
            ("settings", (layout.controls_w - 80.0, 50.0), PanelIntent::OpenSettings),
            (
                "dismiss-all",
                (layout.list_x + layout.list_w - 100.0, 50.0),
                PanelIntent::Request(ServiceRequest::NotificationDismissAll),
            ),
        ] {
            assert!(point.0 < 1232.0 && point.1 < 568.0, "{name} on the panel");
            assert_eq!(panel_intent(Route::Shade, point, point, 1232, 568, &view), Some(expected), "{name}");
        }
        // Both sliders own their bands, only in the left column; the same
        // y on the list side is a notification row, not a slider.
        let shift = shade_slider_shift(true);
        for top in [SHADE_SLIDER_TOP, SHADE_VOLUME_TOP] {
            let y = shift + top + 20.0;
            assert!(settings_slider_column_hit(Route::Shade, 1232, 568, 200.0));
            assert!(!settings_slider_column_hit(Route::Shade, 1232, 568, layout.list_x + 100.0));
            assert!(!shade_panel_close_zone((200.0, y), 1232, 568, &view), "slider at y {y} owns its gesture");
            assert!(
                notification_index((layout.list_x + 100.0, y), 1232, 568, &view).is_some(),
                "the list is reachable at the sliders' y"
            );
        }
        assert_eq!(settings_slider_frame(Route::Shade, 1232, 568), (0.0, layout.controls_w));
        // Each visible notification row: its card rect is inside the panel
        // and a tap at its centre activates that row's event.
        let events = &view.notifications.as_ref().unwrap().events;
        let mut seen = 0;
        for (index, event) in events.iter().enumerate() {
            let top = layout.list_top + index as f64 * notification_row();
            let card = (layout.list_x + 24.0, top, layout.list_w - 48.0, notification_row() - 8.0);
            if card.1 + card.3 > layout.list_bottom {
                continue;
            }
            seen += 1;
            assert!(card.0 >= layout.controls_w && card.0 + card.2 <= 1232.0 && card.1 >= 0.0 && card.1 + card.3 <= 568.0);
            let tap = (card.0 + card.2 / 2.0, card.1 + card.3 / 2.0);
            let intent = panel_intent(Route::Shade, tap, tap, 1232, 568, &view);
            let expected = event
                .action_available
                .then_some(PanelIntent::Request(ServiceRequest::NotificationAction(event.id)));
            assert_eq!(intent, expected, "tap at the centre of row {index}");
        }
        assert!(seen >= 3, "several rows are visible without scrolling: {seen}");
    }

    #[test]
    fn the_wide_shade_scrolls_to_its_last_notification_and_swipes_dismiss_inside_the_list() {
        let layout = shade_layout(1232, 568);
        let mut view = wide_shade_view(6, false);
        let max = notification_max_scroll(6, 1232, 568);
        assert!(max > 0.0, "six rows overflow the list");
        view.notification_scroll = max;
        // The last row now ends at the list's bottom: reachable.
        let last_top = layout.list_top + 5.0 * notification_row() - max;
        assert!(last_top >= layout.list_top && last_top + notification_row() - 8.0 <= layout.list_bottom + 1.0);
        let tap = (layout.list_x + layout.list_w / 2.0, last_top + 40.0);
        assert_eq!(notification_index(tap, 1232, 568, &view), Some(5));
        // A horizontal drag that starts in the list dismisses a dismissible
        // row; the same drag in the controls column starts no swipe.
        view.notification_scroll = 0.0;
        let row = (layout.list_x + 200.0, layout.list_top + 30.0);
        let swipe = notification_swipe_start(row, (row.0 + 60.0, row.1 + 2.0), 1232, 568, &view);
        assert!(swipe.is_some(), "swipe starts on the first (dismissible) row");
        let left = (200.0, layout.list_top + 30.0);
        assert!(notification_swipe_start(left, (left.0 + 60.0, left.1), 1232, 568, &view).is_none());
        let hit = notification_swipe_hit(&view, swipe.as_ref().unwrap(), (row.0 + 60.0, row.1), 1232, 568);
        assert!(hit);
        // An upward drag that starts in the list near the top scrolls it; it
        // does not hide the Shade.
        let start = (layout.list_x + 200.0, 150.0);
        let end = (start.0, start.1 - 120.0);
        assert!(!matches!(
            panel_intent(Route::Shade, start, end, 1232, 568, &view),
            Some(PanelIntent::Hide)
        ));
        // In the controls column the same drag still hides it.
        let start = (200.0, 150.0);
        assert_eq!(
            panel_intent(Route::Shade, start, (start.0, start.1 - 120.0), 1232, 568, &view),
            Some(PanelIntent::Hide)
        );
        // Closing from the left column is allowed; from the list only at its end.
        assert!(shade_panel_close_zone((200.0, 140.0), 1232, 568, &view));
        assert!(!shade_panel_close_zone((layout.list_x + 100.0, 300.0), 1232, 568, &view));
    }

    #[test]
    fn the_wide_shade_tiles_meet_the_tap_floor_and_open_their_pages() {
        let layout = shade_layout(1232, 568);
        let mut view = wide_shade_view(2, true);
        assert_eq!(shade_tiles(&view), vec![ShadeTile::Wifi, ShadeTile::Keyboard], "no modem, no modem tiles");
        view.modem = Some(present_modem());
        let tiles = shade_tiles(&view);
        assert_eq!(tiles.len(), 4);
        let slider_top = shade_wide_slider_top();
        let slider_bottom = slider_top + SHADE_VOLUME_TOP + SHADE_VOLUME_H - SHADE_SLIDER_TOP;
        assert!(slider_bottom <= layout.list_bottom, "the sliders fit the column: {slider_bottom}");
        for (index, tile) in tiles.iter().enumerate() {
            let (x, y, w, h) = shade_tile_rect(index, layout.controls_w);
            assert!(h >= SHADE_TAP_MIN && w >= SHADE_TAP_MIN, "{tile:?}: {w}x{h}");
            assert!(x >= 24.0 && x + w <= layout.controls_w - 24.0 + 0.5, "{tile:?} inside the column");
            assert!(y >= SHADE_SETTINGS_BOTTOM && y + h <= slider_top, "{tile:?} between the header and sliders");
            let centre = (x + w / 2.0, y + h / 2.0);
            assert!(!slider_band(Route::Shade, settings_slider_y(Route::Shade, centre.1, 1232, 568), &view));
            let expected = match tile {
                ShadeTile::Wifi => Some(PanelIntent::OpenWifi),
                ShadeTile::Keyboard => Some(PanelIntent::Request(ServiceRequest::KeyboardToggle)),
                ShadeTile::Location => Some(PanelIntent::ToggleLocation),
                ShadeTile::Cellular => Some(PanelIntent::OpenCellular),
            };
            assert_eq!(panel_intent(Route::Shade, centre, centre, 1232, 568, &view), expected, "{tile:?}");
        }
        // Portrait has no tiles; its keyboard toggle stays a row.
        let portrait = shade_layout(568, 1232);
        assert_eq!(shade_tile_at((100.0, 200.0), &portrait, &view), None);
        assert_eq!(shade_slider_shift(false), 0.0);
    }

    fn present_modem() -> crate::modem::ModemStatus {
        crate::modem::parse_status(
            br#"{"schema":1,"present":true,"power":"on","cellular":true,"sim":"ready","registration":"registered_home","bars":3}"#,
        )
        .unwrap()
    }

    #[test]
    fn settings_offers_cellular_and_location_only_once_the_modem_has_answered() {
        use crate::render::{settings_modem_row_h, settings_modem_row_y, settings_wide_offset_for};
        for key_backlight in [false, true] {
            let kb = key_backlight.then_some(crate::keyboard_base::KeyBacklight::Off);
            let hidden = ServiceView {
                settings: Some(crate::evidence_render::fixture_settings()),
                key_backlight: kb,
                ..ServiceView::default()
            };
            let shown = ServiceView { modem: Some(present_modem()), ..hidden.clone() };
            // Wide: the rows lead column 2, above Power; scrolled to show them.
            let (dx, dy) = settings_wide_offset_for(2, key_backlight, true);
            for (index, expected) in [PanelIntent::OpenCellular, PanelIntent::OpenLocation].into_iter().enumerate() {
                let y = settings_modem_row_y(key_backlight, index as u32);
                let tap = (dx + 24.0 + 100.0, y + dy + settings_modem_row_h() / 2.0);
                assert!(tap.1 > settings_body_top(1232, 568) && tap.1 < 568.0, "row {index} is on screen unscrolled");
                assert_eq!(panel_intent(Route::Settings, tap, tap, 1232, 568, &shown), Some(expected.clone()), "wide row {index}");
                assert_ne!(panel_intent(Route::Settings, tap, tap, 1232, 568, &hidden), Some(expected), "wide row {index} hidden");
                // Portrait: the same rows in the single column.
                let (scale, x) = crate::settings_content_transform(568, 1232);
                let tap = (x + 200.0 * scale, y * scale + settings_modem_row_h() * scale / 2.0);
                let expected = [PanelIntent::OpenCellular, PanelIntent::OpenLocation][index].clone();
                assert_eq!(panel_intent(Route::Settings, tap, tap, 568, 1232, &shown), Some(expected.clone()), "portrait row {index}");
                assert_ne!(panel_intent(Route::Settings, tap, tap, 568, 1232, &hidden), Some(expected), "portrait row {index} hidden");
            }
            // Power still answers where the rows pushed it.
            let layout = crate::render::settings_layout_for(key_backlight, true);            let tap = (dx + 24.0 + 100.0, layout.reboot_y + dy + 20.0);
            let mut view = shown.clone();
            view.settings_scroll = (tap.1 - 568.0 + 40.0).max(0.0).min(settings_max_scroll(1232, 568, &view));
            let tap = (tap.0, tap.1 - view.settings_scroll);
            assert_eq!(
                panel_intent(Route::Settings, tap, tap, 1232, 568, &view),
                Some(PanelIntent::Request(ServiceRequest::PowerRequest(PowerAction::Reboot))),
                "reboot with the modem rows present (key backlight {key_backlight})"
            );
        }
    }

    #[test]
    fn settings_ends_its_rows_with_date_and_time_then_about() {
        use crate::render::{
            settings_info_row_index, settings_modem_row_h, settings_modem_row_y, settings_wide_offset_for,
        };
        for step in [1.0, 2.0] {
            crate::set_layout_text_scale(step);
            for (modem, key_backlight) in [(false, false), (false, true), (true, false), (true, true)] {
                let view = ServiceView {
                    settings: Some(crate::evidence_render::fixture_settings()),
                    key_backlight: key_backlight.then_some(crate::keyboard_base::KeyBacklight::Off),
                    modem: modem.then(present_modem),
                    ..ServiceView::default()
                };
                let row_h = settings_modem_row_h();
                assert!(row_h >= SHADE_TAP_MIN, "rows meet the 99 px touch floor");
                for (info, expected) in [(0u32, PanelIntent::OpenDateTime), (1, PanelIntent::OpenAbout)] {
                    let index = settings_info_row_index(modem, info);
                    let y = settings_modem_row_y(key_backlight, index);
                    // Wide: scroll the third column so the row is on screen.
                    let (dx, dy) = settings_wide_offset_for(2, key_backlight, modem);
                    let mut wide = view.clone();
                    let max = settings_max_scroll(1232, 568, &wide);
                    wide.settings_scroll = (y + dy + row_h / 2.0 - 400.0).clamp(0.0, max);
                    let tap = (dx + 24.0 + 100.0, y + dy + row_h / 2.0 - wide.settings_scroll);
                    assert!(tap.1 > settings_body_top(1232, 568) && tap.1 < 568.0, "wide {tap:?} step {step}");
                    assert_eq!(
                        panel_intent(Route::Settings, tap, tap, 1232, 568, &wide),
                        Some(expected.clone()),
                        "wide {expected:?} modem {modem} kb {key_backlight} step {step}"
                    );
                    // Portrait: the single column, scrolled the same way.
                    let (scale, x) = crate::settings_content_transform(568, 1232);
                    let mut tall = view.clone();
                    let max = settings_max_scroll(568, 1232, &tall);
                    tall.settings_scroll = (y * scale + row_h * scale / 2.0 - 800.0).clamp(0.0, max);
                    let tap = (x + 200.0 * scale, y * scale + row_h * scale / 2.0 - tall.settings_scroll);
                    assert!(tap.1 > settings_body_top(568, 1232) && tap.1 < 1232.0, "tall {tap:?} step {step}");
                    assert_eq!(
                        panel_intent(Route::Settings, tap, tap, 568, 1232, &tall),
                        Some(expected.clone()),
                        "portrait {expected:?} modem {modem} kb {key_backlight} step {step}"
                    );
                }
                // About is the last row: Power follows it.
                let about = settings_modem_row_y(key_backlight, settings_info_row_index(modem, 1));
                assert!(crate::render::settings_layout_for(key_backlight, modem).power_heading_y > about + row_h);
            }
        }
        crate::set_layout_text_scale(1.0);
    }
}
