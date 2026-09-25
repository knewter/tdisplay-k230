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
}
