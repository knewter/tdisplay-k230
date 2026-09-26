//! Touch hit regions and visible data for the transient Settings/shade panels.
//! Service I/O remains in `service_data::ServiceWorker` off the Wayland loop.

use crate::{
    render::{settings_confirm_layout, settings_layout, settings_row_y, SETTINGS_POWER_CARD_H},
    service_data::{
        ActionOutcome, ControlState, ControlValue, NotificationSnapshot, PowerAction, Priority,
        ServiceRequest, SettingsSnapshot,
    },
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
    /// Active, single-contact history drag. Never used for a critical row.
    pub notification_swipe: Option<NotificationSwipe>,
    pub wifi: Option<WifiPublic>,
    /// Set only by an image that includes the compositor keyboard gestures.
    pub keyboard_gesture_hint: bool,
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

pub fn action_message(outcome: &ActionOutcome) -> String {
    let explanation = outcome
        .error
        .as_deref()
        .or(outcome.label.as_deref())
        .unwrap_or(&outcome.state);
    if outcome.retry {
        format!("{explanation} · try again")
    } else {
        explanation.into()
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum PanelIntent {
    Hide,
    OpenSettings,
    OpenWifi,
    Request(ServiceRequest),
    ScrollNotifications(f64),
}

pub const NOTIFICATION_TOP: f64 = 266.0;
pub const NOTIFICATION_ROW: f64 = 116.0;
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

/// Live progress for an in-flight close drag: 1.0 where the drag began
/// (fully open) down to 0.0 once the finger has pulled the panel entirely
/// away (`-dy >= panel_travel`). `dy` is `current.1 - start.1`, so a
/// downward move (`dy > 0`) only ever pushes progress back *toward* 1.0
/// (clamped there, never past it) -- "a downward drag during a close drag
/// just moves the panel back down" falls out of the clamp, not a special
/// case.
pub fn close_drag_progress(dy: f64, panel_travel: f64) -> f64 {
    (1.0 - (-dy) / panel_travel.max(1.0)).clamp(0.0, 1.0)
}

/// The small-slop + direction lock that turns a touch already in
/// `close_drag_zone` into a *live* close drag, mirrored from the same
/// tap-vs-drag convention `DrawerNavigation`/`notification_swipe_start` use
/// (a minimum travel before committing, dominant along the axis that
/// matters) rather than reacting to the very first pixel of motion. A
/// touch that never clears this must still resolve as an ordinary tap at
/// release (`panel_intent`), not a partial drag.
pub fn close_drag_engaged(dx: f64, dy: f64) -> bool {
    dy <= -CLOSE_DRAG_SLOP && dy.abs() > dx.abs()
}

/// Where a close drag may originate: the existing top dismiss zone, or at
/// or after the panel's own bottom edge -- the dim backdrop below it,
/// which also covers grabbing right at ("the panel's bottom edge/handle").
/// Both zones sit outside every scrollable/interactive region either route
/// paints (the notification list starts at `NOTIFICATION_TOP`, well below
/// the dismiss zone, and `panel_intent`'s own fall-through already shows
/// nothing is hit-tested at or below `panel_travel` today), so a drag
/// starting here can never race a list scroll or a Settings control.
pub fn close_drag_zone(route: Route, y: f64, panel_travel: f64) -> bool {
    matches!(route, Route::Shade | Route::Settings)
        && (y < OVERLAY_DISMISS_ZONE_Y || y >= panel_travel)
}

/// A tap (no drag past the tap slop) that starts and ends on the dim
/// backdrop below a Shade/Settings sheet: the sheet closes, as tapping
/// outside a sheet does everywhere else.
pub fn backdrop_tap(route: Route, start: (f64, f64), end: (f64, f64), panel_travel: f64) -> bool {
    matches!(route, Route::Shade | Route::Settings)
        && start.1 >= panel_travel
        && end.1 >= panel_travel
        && (end.0 - start.0).abs() <= 18.0
        && (end.1 - start.1).abs() <= 18.0
}

/// Where a released close drag settles: fully closed (`0.0`) or back open
/// (`1.0`). A fast upward flick commits to closing outright; otherwise it
/// is a plain threshold on how much of the panel was already pulled away.
pub fn close_drag_release_target(progress: f64, upward_velocity: f64) -> f64 {
    if upward_velocity >= CLOSE_FLING_VELOCITY || progress < CLOSE_DISMISS_PROGRESS {
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

pub fn notification_max_scroll(count: usize, height: u32) -> f64 {
    let bottom = f64::from(height) * 0.65 - 24.0;
    (NOTIFICATION_TOP + count as f64 * NOTIFICATION_ROW - bottom).max(0.0)
}

fn notification_index(y: f64, height: u32, view: &ServiceView) -> Option<usize> {
    if y < NOTIFICATION_TOP || y >= f64::from(height) * 0.65 - 24.0 {
        return None;
    }
    let index =
        ((y - NOTIFICATION_TOP + view.notification_scroll) / NOTIFICATION_ROW).floor() as usize;
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
    if start.0 < 24.0
        || start.0 >= f64::from(width) - 24.0
        || dx.abs() <= SWIPE_START
        || dx.abs() <= dy.abs()
    {
        return None;
    }
    let row_y =
        (start.1 - NOTIFICATION_TOP + view.notification_scroll).rem_euclid(NOTIFICATION_ROW);
    if row_y >= NOTIFICATION_ROW - 8.0 {
        return None;
    }
    let row_index = notification_index(start.1, height, view)?;
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
    let y = NOTIFICATION_TOP + swipe.row_index as f64 * NOTIFICATION_ROW - view.notification_scroll;
    let bottom = f64::from(height) * 0.65 - 24.0;
    pos.1 >= y.max(NOTIFICATION_TOP)
        && pos.1 < (y + NOTIFICATION_ROW - 8.0).min(bottom)
        && pos.0 >= 24.0 + swipe.offset
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
            if start.1 < OVERLAY_DISMISS_ZONE_Y && dy < OVERLAY_DISMISS_DY {
                return Some(PanelIntent::Hide);
            }
            if let Some(index) = notification_index(start.1, height, view) {
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
            if end.1 < 112.0 && end.0 > w - 180.0 {
                return Some(PanelIntent::OpenSettings);
            }
            if (116.0..190.0).contains(&end.1)
                && end.0 > w - 180.0
                && view
                    .notifications
                    .as_ref()
                    .is_some_and(|items| !items.events.is_empty())
            {
                return Some(PanelIntent::Request(ServiceRequest::NotificationDismissAll));
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
            if end.1 < 108.0 && end.0 > w - 150.0 {
                return Some(PanelIntent::Hide);
            }
            if let Some(confirm) = &view.confirmation {
                if Instant::now() >= confirm.expires_at {
                    return None;
                }
                let card_y = settings_confirm_layout(settings_layout().poweroff_bottom).card_y;
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
            let layout = settings_layout();
            if (settings_row_y(0)..settings_row_y(0) + 110.0).contains(&end.1) {
                return Some(PanelIntent::OpenWifi);
            }
            if (settings_row_y(1)..settings_row_y(1) + 94.0).contains(&end.1)
                && end.0 > w - 210.0
                && settings.brightness.state == ControlState::Writable
            {
                let ControlValue::Percent(value) = settings.brightness.value.as_ref()? else {
                    return None;
                };
                let next = if end.0 < w - 105.0 {
                    value.saturating_sub(10)
                } else {
                    value.saturating_add(10).min(100)
                };
                return Some(PanelIntent::Request(ServiceRequest::Brightness(next)));
            }
            if (settings_row_y(2)..settings_row_y(2) + 110.0).contains(&end.1)
                && settings.keyboard.state == ControlState::Action
            {
                return Some(PanelIntent::Request(ServiceRequest::KeyboardToggle));
            }
            if (layout.reboot_y..layout.reboot_y + SETTINGS_POWER_CARD_H).contains(&end.1)
                && view.settings.is_some()
            {
                return Some(PanelIntent::Request(ServiceRequest::PowerRequest(
                    PowerAction::Reboot,
                )));
            }
            if (layout.poweroff_y..layout.poweroff_y + SETTINGS_POWER_CARD_H).contains(&end.1)
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
    use crate::service_data::{Control, NotificationEvent, Priority};

    #[test]
    fn close_drag_progress_is_one_at_start_and_zero_at_full_travel() {
        let travel = 800.0;
        assert_eq!(close_drag_progress(0.0, travel), 1.0);
        assert_eq!(close_drag_progress(-travel, travel), 0.0);
        assert_eq!(close_drag_progress(-travel / 2.0, travel), 0.5);
        // Overshooting past full travel clamps at 0, never negative.
        assert_eq!(close_drag_progress(-travel * 2.0, travel), 0.0);
        // A downward move from the drag's own start only ever pushes back
        // toward 1.0, clamped there -- "a downward drag during a close
        // drag just moves the panel back down" falls out of the clamp.
        assert_eq!(close_drag_progress(120.0, travel), 1.0);
    }

    #[test]
    fn close_drag_progress_is_monotonic_in_upward_travel() {
        let travel = 800.0;
        let samples: Vec<f64> = (0..=20)
            .map(|step| close_drag_progress(-travel * f64::from(step) / 20.0, travel))
            .collect();
        for pair in samples.windows(2) {
            assert!(
                pair[1] <= pair[0],
                "progress must only ever fall as upward travel grows: {samples:?}"
            );
        }
    }

    #[test]
    fn close_drag_engaged_needs_slop_and_vertical_dominance() {
        // Under slop: still a tap/wobble candidate.
        assert!(!close_drag_engaged(0.0, -CLOSE_DRAG_SLOP + 1.0));
        // Exactly at slop, upward, no sideways drift: engaged.
        assert!(close_drag_engaged(0.0, -CLOSE_DRAG_SLOP));
        // Downward motion never engages a close drag.
        assert!(!close_drag_engaged(0.0, CLOSE_DRAG_SLOP + 20.0));
        // Past slop upward, but more sideways than vertical: not engaged
        // (this is a horizontal gesture, not a vertical close drag).
        assert!(!close_drag_engaged(40.0, -20.0));
        // Past slop, vertical-dominant: engaged even with a little drift.
        assert!(close_drag_engaged(4.0, -20.0));
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
    fn shade_and_settings_hits_are_bounded_and_cancel_scroll_taps() {
        let mut view = ServiceView {
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
                (300.0, 300.0),
                (400.0, 305.0),
                568,
                1232,
                &view
            ),
            None // release alone cannot dismiss without a tracked drag
        );
        assert_eq!(
            notification_swipe_start((300.0, 300.0), (400.0, 305.0), 568, 1232, &view)
                .map(|swipe| swipe.event_id),
            Some(7),
        );
        assert_eq!(
            panel_intent(
                Route::Shade,
                (300.0, 300.0),
                (300.0, 390.0),
                568,
                1232,
                &view
            ),
            Some(PanelIntent::ScrollNotifications(-90.0))
        );
        assert_eq!(
            panel_intent(
                Route::Shade,
                (300.0, 300.0),
                (300.0, 300.0),
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
        let control = |state, value| Control {
            state,
            value,
            label: "Available".into(),
            detail: None,
            action: None,
        };
        view.settings = Some(SettingsSnapshot {
            network: control(ControlState::ReadOnly, None),
            brightness: control(ControlState::Writable, Some(ControlValue::Percent(55))),
            keyboard: control(ControlState::Action, None),
            motion: control(ControlState::ReadOnly, None),
        });
        assert_eq!(
            panel_intent(
                Route::Settings,
                (480.0, 365.0),
                (480.0, 365.0),
                568,
                1232,
                &view
            ),
            Some(PanelIntent::Request(ServiceRequest::Brightness(65)))
        );
        assert_eq!(
            panel_intent(
                Route::Settings,
                (480.0, 365.0),
                (480.0, 410.0),
                568,
                1232,
                &view
            ),
            None
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
        let start = (300.0, 300.0);
        assert_eq!(
            notification_swipe_start(start, (320.0, 305.0), 568, 1232, &view)
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
            notification_swipe_start(start, (320.0, 350.0), 568, 1232, &view),
            None
        );
        view.notifications.as_mut().unwrap().events[0].dismissible = false;
        assert_eq!(
            notification_swipe_start(start, (400.0, 300.0), 568, 1232, &view),
            None
        );
        assert!(!notification_swipe_valid(&view, &swipe));
        assert_eq!(notification_swipe_release(&view, &swipe, 0.0), None);
        view.notifications.as_mut().unwrap().events[0].dismissible = true;
        view.notifications.as_mut().unwrap().events[0].priority = Priority::Critical;
        assert_eq!(
            notification_swipe_start(start, (400.0, 300.0), 568, 1232, &view),
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
            motion: unavailable,
        });
        assert_eq!(
            panel_intent(
                Route::Settings,
                (60.0, 730.0),
                (60.0, 730.0),
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
        assert_eq!(
            panel_intent(
                Route::Settings,
                (80.0, 985.0),
                (80.0, 985.0),
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
                (440.0, 985.0),
                (440.0, 985.0),
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
                (440.0, 985.0),
                (440.0, 985.0),
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
    fn failed_action_exposes_backend_error_and_retry() {
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
        assert_eq!(action_message(&outcome), "target-unavailable · try again");
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

}
