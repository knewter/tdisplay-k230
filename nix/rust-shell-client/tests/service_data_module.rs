#[path = "../src/service_data.rs"]
mod service_data;

use serde_json::json;
use service_data::{parse_history, parse_settings, ControlState, ControlValue, Priority};

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
