use k230_theme_catalog_bridge_host::theme_catalog::{
    parse_response, BackgroundKind, ThemeRequest, ThemeResponse, ThemeWorker,
};
use serde_json::json;
use std::{
    fs,
    os::unix::fs::PermissionsExt,
    path::{Path, PathBuf},
    thread,
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};

const THEME: &str = "111111111111111111111111";
const GENERATION: &str = "222222222222222222222222";
const BACKGROUND: &str = "333333333333333333333333";

fn preview(activated: bool) -> serde_json::Value {
    let mut value = json!({
        "schema":1,
        "theme":{"id":THEME,"name":"public-fixture","label":"Public Fixture","origin":"user"},
        "generation":GENERATION,
        "appearance_path":format!("/tmp/state/generations/{GENERATION}/appearance.json"),
        "palette":{"background":"#102030","foreground":"#ffffff"},
        "icon_theme":null,
        "backgrounds":[{"id":BACKGROUND,"label":"still.png","kind":"image",
            "path":format!("/tmp/state/generations/{GENERATION}/theme/backgrounds/still.png"),
            "selected":true,"decode_status":"unverified"}],
        "compatibility":{"applied":[],"unavailable":[],"unknown":[]},
        "activated":activated,
    });
    if activated {
        value["app_appearance"] =
            json!({"state":"failed","error":"app-sync-failed","kind":"RuntimeError"});
    }
    value
}

#[test]
fn typed_catalog_and_preview_preserve_identity_background_and_app_status() {
    let list = ThemeRequest::List;
    let data = json!({"schema":1,"themes":[
        {"id":THEME,"name":"public-fixture","label":"Public Fixture","origin":"user",
         "preview_path":"/tmp/state/themes/public-fixture/preview.png"}],
        "active":{"id":null,"generation":GENERATION}});
    let ThemeResponse::List(listed) = parse_response(&list, data.to_string().as_bytes()).unwrap()
    else {
        panic!("list expected");
    };
    assert_eq!(listed.themes[0].label, "Public Fixture");
    assert_eq!(listed.active.generation.as_deref(), Some(GENERATION));
    assert_eq!(
        listed.themes[0].preview_path,
        Some(PathBuf::from("/tmp/state/themes/public-fixture/preview.png"))
    );
    let request = ThemeRequest::Preview {
        theme_id: THEME.into(),
        background_id: Some(BACKGROUND.into()),
    };
    let ThemeResponse::Preview(staged) =
        parse_response(&request, preview(false).to_string().as_bytes()).unwrap()
    else {
        panic!("preview expected");
    };
    assert!(!staged.activated);
    assert_eq!(staged.backgrounds[0].kind, BackgroundKind::Image);
    assert!(staged.backgrounds[0].selected);
    assert_eq!(staged.generation, GENERATION);
    let apply = ThemeRequest::Activate {
        theme_id: THEME.into(),
        expected_generation: GENERATION.into(),
        background_id: Some(BACKGROUND.into()),
    };
    let ThemeResponse::Preview(applied) =
        parse_response(&apply, preview(true).to_string().as_bytes()).unwrap()
    else {
        panic!("activation expected");
    };
    assert!(applied.activated);
    assert_eq!(applied.app_appearance.unwrap().state, "failed");
}

#[test]
fn stale_generation_escape_and_oversized_list_are_rejected() {
    let request = ThemeRequest::Activate {
        theme_id: THEME.into(),
        expected_generation: "aaaaaaaaaaaaaaaaaaaaaaaa".into(),
        background_id: None,
    };
    assert!(
        parse_response(&request, preview(true).to_string().as_bytes())
            .unwrap_err()
            .contains("changed since preview")
    );
    let request = ThemeRequest::Preview {
        theme_id: THEME.into(),
        background_id: Some(BACKGROUND.into()),
    };
    let mut escape = preview(false);
    escape["backgrounds"][0]["path"] = json!(format!(
        "/tmp/state/generations/{GENERATION}/theme/../private.png"
    ));
    assert!(parse_response(&request, escape.to_string().as_bytes()).is_err());
    let mut wrong_choice = preview(false);
    wrong_choice["backgrounds"][0]["selected"] = json!(false);
    assert!(parse_response(&request, wrong_choice.to_string().as_bytes()).is_err());
    let escaping_preview = json!({"schema":1,"themes":[
        {"id":THEME,"name":"public","label":"Public","origin":"user",
         "preview_path":"/tmp/state/themes/public/../../private/preview.png"}],
        "active":{"id":null,"generation":null}});
    assert!(parse_response(&ThemeRequest::List, escaping_preview.to_string().as_bytes()).is_err());
    let giant = json!({"schema":1,"themes":vec![json!({
        "id":THEME,"name":"public","label":"Public","origin":"user"}); 513],
        "active":{"id":null,"generation":null}});
    assert!(parse_response(&ThemeRequest::List, giant.to_string().as_bytes()).is_err());
}

struct Fixture(PathBuf);
impl Fixture {
    fn new() -> Self {
        let stamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let path =
            std::env::temp_dir().join(format!("theme-worker-{}-{stamp}", std::process::id()));
        fs::create_dir(&path).unwrap();
        Self(path)
    }
    fn path(&self, name: &str) -> PathBuf {
        self.0.join(name)
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        fs::remove_dir_all(&self.0).unwrap();
    }
}

fn script(path: &Path, body: &str) {
    fs::write(path, format!("#!/bin/sh\n{body}\n")).unwrap();
    let mut mode = fs::metadata(path).unwrap().permissions();
    mode.set_mode(0o700);
    fs::set_permissions(path, mode).unwrap();
}

fn wait(worker: &ThemeWorker) -> k230_theme_catalog_bridge_host::theme_catalog::ThemeReply {
    let end = Instant::now() + Duration::from_secs(3);
    loop {
        if let Some(reply) = worker.try_recv() {
            return reply;
        }
        assert!(Instant::now() < end, "worker did not answer");
        thread::sleep(Duration::from_millis(5));
    }
}

#[test]
fn worker_is_async_uses_exact_argv_and_rejects_untrusted_ids() {
    let fixture = Fixture::new();
    let command = fixture.path("k230-theme");
    let argv = fixture.path("argv");
    let payload = fixture.path("reply.json");
    fs::write(&payload, preview(false).to_string()).unwrap();
    script(
        &command,
        &format!(
            "sleep 0.3\nprintf '%s\\n' \"$@\" > '{}'\ncat '{}'",
            argv.display(),
            payload.display()
        ),
    );
    let worker = ThemeWorker::spawn(command);
    assert!(worker
        .try_submit(ThemeRequest::Preview {
            theme_id: "$(touch /tmp/should-never-exist)".into(),
            background_id: None,
        })
        .is_err());
    assert!(!argv.exists());
    let submitted = Instant::now();
    worker
        .try_submit(ThemeRequest::Preview {
            theme_id: THEME.into(),
            background_id: Some(BACKGROUND.into()),
        })
        .unwrap();
    assert!(
        submitted.elapsed() < Duration::from_millis(200),
        "submission blocked on the theme command"
    );
    assert!(wait(&worker).result.is_ok());
    assert_eq!(
        fs::read_to_string(&argv).unwrap(),
        format!("preview\n{THEME}\n--background\n{BACKGROUND}\n")
    );
    fs::write(&payload, preview(true).to_string()).unwrap();
    worker
        .try_submit(ThemeRequest::Activate {
            theme_id: THEME.into(),
            expected_generation: GENERATION.into(),
            background_id: Some(BACKGROUND.into()),
        })
        .unwrap();
    assert!(wait(&worker).result.is_ok());
    assert_eq!(
        fs::read_to_string(fixture.path("argv")).unwrap(),
        format!(
            "activate\n{THEME}\n--expected-generation\n{GENERATION}\n--background\n{BACKGROUND}\n"
        )
    );
}

#[test]
fn nonzero_json_error_and_large_output_have_bounded_results() {
    let fixture = Fixture::new();
    let command = fixture.path("k230-theme");
    script(&command, "printf '%s' '{\"schema\":1,\"error\":\"theme changed since preview; preview it again\",\"activated\":false}' >&2\nexit 1");
    let worker = ThemeWorker::spawn(command);
    worker.try_submit(ThemeRequest::List).unwrap();
    assert_eq!(
        wait(&worker).result.unwrap_err(),
        "theme changed since preview; preview it again"
    );

    let command = fixture.path("too-large");
    script(&command, "head -c 1100000 /dev/zero");
    let worker = ThemeWorker::spawn(command);
    worker.try_submit(ThemeRequest::List).unwrap();
    assert!(wait(&worker).result.unwrap_err().contains("exceeds bound"));
}
