//! Real typed preview parser, including old immutable reports without adapted.
use k230_shell_rust::theme_catalog::{parse_response, ThemeRequest, ThemeResponse};
use serde_json::json;

#[test]
fn adapted_system_roles_are_preserved_and_bounded_with_legacy_compatibility() {
    let theme = "111111111111111111111111";
    let generation = "222222222222222222222222";
    let request = ThemeRequest::Preview {theme_id: theme.into(), background_id: None};
    let mut value = json!({"schema":1,
        "theme":{"id":theme,"name":"fixture","label":"Fixture","origin":"user"},
        "generation":generation,
        "appearance_path":format!("/tmp/state/generations/{generation}/appearance.json"),
        "palette":{"background":"#102030","foreground":"#ffffff"},
        "icon_theme":null, "backgrounds":[], "activated":false,
        "compatibility":{"applied":[],"unavailable":[],"unknown":[],
            "adapted":["notifications.text: solid swatch"]}});
    let ThemeResponse::Preview(parsed) = parse_response(&request, value.to_string().as_bytes()).unwrap()
        else { panic!("preview expected") };
    assert_eq!(parsed.compatibility.adapted, ["notifications.text: solid swatch"]);
    value["compatibility"]["adapted"] = json!(["x".repeat(513)]);
    assert!(parse_response(&request, value.to_string().as_bytes()).is_err());
    value["compatibility"].as_object_mut().unwrap().remove("adapted");
    let ThemeResponse::Preview(legacy) = parse_response(&request, value.to_string().as_bytes()).unwrap()
        else { panic!("legacy preview expected") };
    assert!(legacy.compatibility.adapted.is_empty());
}
