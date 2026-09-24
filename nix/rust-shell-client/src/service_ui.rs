//! Touch hit regions and visible data for the transient Settings/shade panels.
//! Service I/O remains in `service_data::ServiceWorker` off the Wayland loop.

use crate::{
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

pub fn notification_swipe_release(
    view: &ServiceView,
    swipe: &NotificationSwipe,
) -> Option<ServiceRequest> {
    (swipe.offset.abs() >= SWIPE_COMMIT && notification_swipe_valid(view, swipe))
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
            if start.1 < 180.0 && dy < -90.0 {
                return Some(PanelIntent::Hide);
            }
            if let Some(index) = notification_index(start.1, height, view) {
                let event = &view.notifications.as_ref()?.events[index];
                if dy.abs() > 22.0 {
                    return Some(PanelIntent::ScrollNotifications(-dy));
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
            if start.1 < 130.0 && dy > 90.0 {
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
                if (940.0..1050.0).contains(&end.1) {
                    return Some(PanelIntent::Request(if end.0 < w / 2.0 {
                        ServiceRequest::PowerCancel(confirm.token.clone())
                    } else {
                        ServiceRequest::PowerConfirm(confirm.token.clone())
                    }));
                }
                return None;
            }
            let settings = view.settings.as_ref()?;
            if (162.0..272.0).contains(&end.1) {
                return Some(PanelIntent::OpenWifi);
            }
            if (326.0..420.0).contains(&end.1)
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
            if (452.0..562.0).contains(&end.1) && settings.keyboard.state == ControlState::Action {
                return Some(PanelIntent::Request(ServiceRequest::KeyboardToggle));
            }
            if (750.0..820.0).contains(&end.1) && view.settings.is_some() {
                return Some(PanelIntent::Request(ServiceRequest::PowerRequest(
                    PowerAction::Reboot,
                )));
            }
            if (828.0..898.0).contains(&end.1) && view.settings.is_some() {
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
            notification_swipe_release(&view, &swipe),
            Some(ServiceRequest::NotificationDismiss(7))
        );
        assert_eq!(
            notification_swipe_release(
                &view,
                &NotificationSwipe {
                    offset: 12.0,
                    ..swipe.clone()
                }
            ),
            None
        );
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
        assert_eq!(notification_swipe_release(&view, &swipe), None);
        view.notifications.as_mut().unwrap().events[0].dismissible = true;
        view.notifications.as_mut().unwrap().events[0].priority = Priority::Critical;
        assert_eq!(
            notification_swipe_start(start, (400.0, 300.0), 568, 1232, &view),
            None
        );
        assert_eq!(notification_swipe_release(&view, &swipe), None);
        view.notifications.as_mut().unwrap().events[0].id = 8;
        assert!(!notification_swipe_valid(&view, &swipe));
        view.notifications.as_mut().unwrap().events[0].id = 7;
        view.notifications.as_mut().unwrap().events[0].priority = Priority::Ordinary;
        assert!(notification_swipe_valid(&view, &swipe));
        let mut newer = view.notifications.as_ref().unwrap().events[0].clone();
        newer.id = 8;
        view.notifications.as_mut().unwrap().events.insert(0, newer);
        assert!(!notification_swipe_valid(&view, &swipe));
    }

    #[test]
    fn power_needs_loaded_settings_and_token_confirmation() {
        let mut view = ServiceView::default();
        assert_eq!(
            panel_intent(
                Route::Settings,
                (60.0, 780.0),
                (60.0, 780.0),
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
                (60.0, 780.0),
                (60.0, 780.0),
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
                (60.0, 780.0),
                (60.0, 780.0),
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
