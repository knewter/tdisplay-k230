#[path = "../src/service_data.rs"]
mod service_data;

use serde_json::json;
use service_data::{
    parse_history, parse_settings, ControlState, ControlValue, Priority, ServiceRequest,
    ServiceResponse, ServiceWorker,
};
use std::{
    fs,
    os::unix::{fs::PermissionsExt, net::UnixListener},
    path::PathBuf,
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};

fn settings() -> serde_json::Value {
    json!({"schema":1,"controls":{
        "network":{"state":"read-only","value":"link-up","label":"Network link available"},
        "brightness":{"state":"writable","value":45,"label":"Brightness","unit":"percent"},
        "keyboard":{"state":"action","value":null,"label":"Toggle keyboard","action":"keyboard-toggle"},
        "motion":{"state":"unavailable","value":null,"label":"Reduced motion","detail":"Session preference"}
    }})
}

fn history() -> serde_json::Value {
    json!({"schema":1,"count":1,"events":[{
        "id":1,"source":"Terminal","icon":"foot","summary":"Private title","body":"Private body",
        "priority":"important","timestamp":1700000000,"error":null,
        "dismissible":true,"action_available":false
    }],"preview":{"id":1,"source":"Notification","icon":null,
        "summary":"New notification","priority":"important","focus":false,"ongoing":false}})
}

#[test]
fn settings_preserves_capability_and_unavailable_states() {
    let snapshot = parse_settings(&serde_json::to_vec(&settings()).unwrap()).unwrap();
    assert_eq!(
        snapshot.network.value,
        Some(ControlValue::Text("link-up".into()))
    );
    assert_eq!(snapshot.brightness.value, Some(ControlValue::Percent(45)));
    assert_eq!(snapshot.keyboard.state, ControlState::Action);
    assert_eq!(snapshot.keyboard.action.as_deref(), Some("keyboard-toggle"));
    assert_eq!(snapshot.motion.state, ControlState::Unavailable);
    assert_eq!(snapshot.motion.value, None);
}

#[test]
fn settings_rejects_invalid_schema_state_value_and_action() {
    let mut value = settings();
    value["schema"] = json!(2);
    assert!(parse_settings(&serde_json::to_vec(&value).unwrap()).is_err());
    value = settings();
    value["controls"]["brightness"]["value"] = json!(101);
    assert!(parse_settings(&serde_json::to_vec(&value).unwrap()).is_err());
    value = settings();
    value["controls"]["network"]["state"] = json!("internet-ok");
    assert!(parse_settings(&serde_json::to_vec(&value).unwrap()).is_err());
    value = settings();
    value["controls"]["keyboard"]["action"] = json!("shell-command");
    assert!(parse_settings(&serde_json::to_vec(&value).unwrap()).is_err());
}

#[test]
fn history_keeps_private_preview_redaction_distinct_from_history() {
    let snapshot = parse_history(&serde_json::to_vec(&history()).unwrap()).unwrap();
    assert_eq!(snapshot.count, 1);
    assert_eq!(snapshot.events[0].body, "Private body");
    let preview = snapshot.preview.unwrap();
    assert_eq!(preview.source, "Notification");
    assert_eq!(preview.summary, "New notification");
    assert_eq!(preview.priority, Priority::Important);
    assert_eq!(preview.icon, None);
}

#[test]
fn history_rejects_focus_count_priority_and_unbounded_input() {
    let mut value = history();
    value["preview"]["focus"] = json!(true);
    assert!(parse_history(&serde_json::to_vec(&value).unwrap()).is_err());
    value = history();
    value["count"] = json!(2);
    assert!(parse_history(&serde_json::to_vec(&value).unwrap()).is_err());
    value = history();
    value["events"][0]["priority"] = json!("emergency");
    assert!(parse_history(&serde_json::to_vec(&value).unwrap()).is_err());
    assert!(parse_history(&vec![b' '; 128 * 1024 + 1]).is_err());
    assert!(parse_settings(&vec![b' '; 16 * 1024 + 1]).is_err());
}

#[test]
fn broker_character_limits_accept_multibyte_unicode() {
    let mut value = history();
    value["events"][0]["summary"] = json!("界".repeat(160));
    value["events"][0]["body"] = json!("🙂".repeat(512));
    value["preview"]["summary"] = json!("界".repeat(160));
    let parsed = parse_history(&serde_json::to_vec(&value).unwrap()).unwrap();
    assert_eq!(parsed.events[0].summary.chars().count(), 160);
    assert_eq!(parsed.events[0].body.chars().count(), 512);
    value["events"][0]["summary"] = json!("界".repeat(161));
    assert!(parse_history(&serde_json::to_vec(&value).unwrap()).is_err());
}

struct WorkerFixture {
    root: PathBuf,
    settings: PathBuf,
    socket: PathBuf,
}

impl WorkerFixture {
    fn new(script: &str) -> Self {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let root =
            std::env::temp_dir().join(format!("k230-service-{}-{nonce}", std::process::id()));
        fs::create_dir(&root).unwrap();
        fs::set_permissions(&root, fs::Permissions::from_mode(0o700)).unwrap();
        let settings = root.join("settings");
        fs::write(&settings, script).unwrap();
        fs::set_permissions(&settings, fs::Permissions::from_mode(0o700)).unwrap();
        let socket = root.join("notifications.sock");
        Self {
            root,
            settings,
            socket,
        }
    }
}
impl Drop for WorkerFixture {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.root);
    }
}

fn next(worker: &ServiceWorker, deadline: Duration) -> service_data::ServiceReply {
    let end = Instant::now() + deadline;
    loop {
        if let Some(reply) = worker.try_recv() {
            return reply;
        }
        assert!(Instant::now() < end, "service worker did not answer");
        std::thread::sleep(Duration::from_millis(5));
    }
}

#[test]
fn worker_coalesces_refresh_and_returns_settings_action_without_ui_block() {
    let fixture = WorkerFixture::new(concat!("#!/bin/sh\n",
        "if [ \"$1\" = status ]; then printf '%s\\n' '",
        "{\"schema\":1,\"controls\":{\"network\":{\"state\":\"unavailable\",\"value\":null,\"label\":\"Network state unavailable\"},",
        "\"brightness\":{\"state\":\"unavailable\",\"value\":null,\"label\":\"Brightness control unavailable\"},",
        "\"keyboard\":{\"state\":\"unavailable\",\"value\":null,\"label\":\"Toggle keyboard\"},",
        "\"motion\":{\"state\":\"unavailable\",\"value\":null,\"label\":\"Reduced motion\"}}}'",
        "; else printf '%s\\n' '{\"state\":\"requested\"}'; fi\n"));
    let worker = ServiceWorker::spawn(fixture.settings.clone(), fixture.socket.clone());
    let start = Instant::now();
    worker.try_submit(ServiceRequest::RefreshSettings).unwrap();
    worker.try_submit(ServiceRequest::RefreshSettings).unwrap();
    worker.try_submit(ServiceRequest::KeyboardToggle).unwrap();
    assert!(start.elapsed() < Duration::from_millis(100));
    assert!(matches!(
        next(&worker, Duration::from_secs(2)).result,
        Ok(ServiceResponse::Settings(_))
    ));
    assert!(matches!(
        next(&worker, Duration::from_secs(2)).result,
        Ok(ServiceResponse::Action(_))
    ));
    assert!(worker.try_recv().is_none());
}

#[test]
fn worker_reads_private_notification_socket_and_times_out_slow_peer() {
    let fixture = WorkerFixture::new("#!/bin/sh\nexit 0\n");
    let listener = UnixListener::bind(&fixture.socket).unwrap();
    fs::set_permissions(&fixture.socket, fs::Permissions::from_mode(0o600)).unwrap();
    let server = std::thread::spawn(move || {
        use std::io::{Read, Write};
        let (mut connection, _) = listener.accept().unwrap();
        let mut request = [0u8; 4096];
        let count = connection.read(&mut request).unwrap();
        assert!(std::str::from_utf8(&request[..count])
            .unwrap()
            .contains("history"));
        connection
            .write_all(format!("{}\n", history()).as_bytes())
            .unwrap();
    });
    let worker = ServiceWorker::spawn(fixture.settings.clone(), fixture.socket.clone());
    worker
        .try_submit(ServiceRequest::RefreshNotifications)
        .unwrap();
    let reply = next(&worker, Duration::from_secs(2));
    assert!(matches!(
        reply.result,
        Ok(ServiceResponse::Notifications(_))
    ));
    server.join().unwrap();

    let listener = UnixListener::bind(fixture.root.join("slow.sock")).unwrap();
    let slow_path = fixture.root.join("slow.sock");
    fs::set_permissions(&slow_path, fs::Permissions::from_mode(0o600)).unwrap();
    let slow = std::thread::spawn(move || {
        let (_connection, _) = listener.accept().unwrap();
        std::thread::sleep(Duration::from_secs(5));
    });
    let slow_worker = ServiceWorker::spawn(fixture.settings.clone(), slow_path);
    let start = Instant::now();
    slow_worker
        .try_submit(ServiceRequest::RefreshNotifications)
        .unwrap();
    assert!(next(&slow_worker, Duration::from_secs(5)).result.is_err());
    assert!(start.elapsed() < Duration::from_secs(5));
    slow.join().unwrap();
}

#[test]
fn worker_rejects_invalid_action_without_contacting_service() {
    let fixture = WorkerFixture::new("#!/bin/sh\nexit 99\n");
    let worker = ServiceWorker::spawn(fixture.settings.clone(), fixture.socket.clone());
    worker.try_submit(ServiceRequest::Brightness(101)).unwrap();
    assert!(next(&worker, Duration::from_secs(1)).result.is_err());
    worker
        .try_submit(ServiceRequest::PowerConfirm("bad token".into()))
        .unwrap();
    assert!(next(&worker, Duration::from_secs(1)).result.is_err());
    worker
        .try_submit(ServiceRequest::NotificationDismiss(0))
        .unwrap();
    assert!(next(&worker, Duration::from_secs(1)).result.is_err());
}
