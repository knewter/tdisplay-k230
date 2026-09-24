use k230_shell_rust::appearance::{
    self, AppearancePhase, AppearanceReceiver, AppearanceToken, PaletteColor, PaletteValue,
};
use serde_json::{json, Value};
use std::{
    fs,
    io::{Read, Write},
    os::unix::{
        ffi::OsStrExt,
        fs::{symlink, PermissionsExt},
        net::UnixStream,
    },
    path::{Path, PathBuf},
    time::{Duration, SystemTime, UNIX_EPOCH},
};

struct Fixture {
    root: PathBuf,
    runtime: PathBuf,
    state: PathBuf,
    default: PathBuf,
}
impl Fixture {
    fn new() -> Self {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let root =
            std::env::temp_dir().join(format!("k230-appearance-{}-{nonce}", std::process::id()));
        let runtime = root.join("runtime");
        let state = root.join("state");
        fs::create_dir_all(&runtime).unwrap();
        fs::set_permissions(&runtime, fs::Permissions::from_mode(0o700)).unwrap();
        fs::create_dir_all(state.join("generations")).unwrap();
        let identity: Value = serde_json::from_str(include_str!(
            "../../handheld-theme-default/default-report.json"
        ))
        .unwrap();
        let id = identity["generation"].as_str().unwrap();
        let default = state.join("generations").join(id);
        fs::create_dir(&default).unwrap();
        fs::write(
            default.join("report.json"),
            include_str!("../../handheld-theme-default/default-report.json"),
        )
        .unwrap();
        fs::write(
            default.join("appearance.json"),
            include_str!("../../handheld-theme-default/default-appearance.json"),
        )
        .unwrap();
        Self {
            root,
            runtime,
            state,
            default,
        }
    }
    fn socket(&self) -> PathBuf {
        self.runtime.join("appearance.sock")
    }
    fn user_generation(&self) -> PathBuf {
        let id = "aaaaaaaaaaaaaaaaaaaaaaaa";
        let path = self.state.join("generations").join(id);
        fs::create_dir(&path).unwrap();
        let mut report: Value = serde_json::from_str(include_str!(
            "../../handheld-theme-default/default-report.json"
        ))
        .unwrap();
        let mut appearance: Value = serde_json::from_str(include_str!(
            "../../handheld-theme-default/default-appearance.json"
        ))
        .unwrap();
        report["generation"] = json!(id);
        appearance["generation"] = json!(id);
        fs::write(
            path.join("report.json"),
            serde_json::to_vec(&report).unwrap(),
        )
        .unwrap();
        fs::write(
            path.join("appearance.json"),
            serde_json::to_vec(&appearance).unwrap(),
        )
        .unwrap();
        path
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.root);
    }
}

fn send(
    receiver: &mut AppearanceReceiver,
    path: &Path,
    request: Value,
) -> (appearance::AppearanceEvent, Value) {
    let mut peer = UnixStream::connect(path).unwrap();
    peer.set_read_timeout(Some(Duration::from_millis(250)))
        .unwrap();
    peer.write_all(format!("{request}\n").as_bytes()).unwrap();
    receiver.accept().unwrap();
    let event = receiver.receive().unwrap().unwrap();
    let clone = event.clone();
    receiver.respond(event, true).unwrap();
    let mut reply = String::new();
    peer.read_to_string(&mut reply).unwrap();
    (clone, serde_json::from_str(&reply).unwrap())
}

#[test]
fn two_phase_ack_follows_typed_snapshot_adoption_and_rollback_is_idempotent() {
    let fixture = Fixture::new();
    let generation = fixture.user_generation();
    let mut receiver = AppearanceReceiver::bind_with_roots(
        fixture.socket(),
        Some(fixture.default.clone()),
        fixture.state.clone(),
    )
    .unwrap();
    assert_eq!(
        fs::metadata(fixture.socket()).unwrap().permissions().mode() & 0o777,
        0o600
    );
    let id = generation.file_name().unwrap().to_str().unwrap();
    let (prepare, reply) = send(
        &mut receiver,
        &fixture.socket(),
        json!({"protocol":1,"phase":"prepare","generation":id,"path":generation,
               "previous_generation":null,"previous_path":null}),
    );
    assert_eq!(prepare.phase, AppearancePhase::Prepare);
    let snapshot = prepare.snapshot.unwrap();
    assert!(matches!(
        snapshot.token("launcher", "background"),
        Some(AppearanceToken::Brush(_))
    ));
    assert_eq!(reply["status"], "ok");
    assert_eq!(snapshot.palette.get("mode"), Some(&PaletteValue::Dark));
    assert_eq!(
        snapshot.palette_color("background"),
        Some(PaletteColor {
            red: 0x1e,
            green: 0x1e,
            blue: 0x2e,
            alpha: 255,
        })
    );
    assert_eq!(receiver.prepared().unwrap().generation, id);
    let (commit, reply) = send(
        &mut receiver,
        &fixture.socket(),
        json!({"protocol":1,"phase":"commit","generation":id,"path":generation}),
    );
    assert_eq!(commit.phase, AppearancePhase::Commit);
    assert_eq!(reply["generation"], id);
    assert_eq!(receiver.active().unwrap().generation, id);
    for _ in 0..2 {
        let (rollback, reply) = send(
            &mut receiver,
            &fixture.socket(),
            json!({"protocol":1,"phase":"rollback","generation":null,"path":null}),
        );
        assert_eq!(rollback.phase, AppearancePhase::Rollback);
        assert!(reply["generation"].is_null());
        assert_eq!(
            receiver.active().unwrap().generation,
            fixture.default.file_name().unwrap().to_str().unwrap()
        );
    }
}

#[test]
fn fifo_payload_is_rejected_without_blocking() {
    let fixture = Fixture::new();
    let generation = fixture.user_generation();
    let report = generation.join("report.json");
    fs::remove_file(&report).unwrap();
    let c_path = std::ffi::CString::new(report.as_os_str().as_bytes()).unwrap();
    assert_eq!(unsafe { libc::mkfifo(c_path.as_ptr(), 0o600) }, 0);
    let mut receiver = AppearanceReceiver::bind_with_roots(
        fixture.socket(),
        Some(fixture.default.clone()),
        fixture.state.clone(),
    )
    .unwrap();
    let id = generation.file_name().unwrap().to_str().unwrap();
    let mut peer = UnixStream::connect(fixture.socket()).unwrap();
    peer.write_all(
        format!(
            "{}\n",
            json!({"protocol":1,"phase":"prepare",
        "generation":id,"path":generation,"previous_generation":null,"previous_path":null})
        )
        .as_bytes(),
    )
    .unwrap();
    receiver.accept().unwrap();
    let start = std::time::Instant::now();
    assert!(receiver
        .receive()
        .unwrap_err()
        .contains("invalid appearance file"));
    assert!(start.elapsed() < Duration::from_secs(1));
    assert!(receiver.prepared().is_none());
}

#[test]
fn intermediate_background_symlink_escape_is_rejected() {
    let fixture = Fixture::new();
    let generation = fixture.user_generation();
    let outside = fixture.root.join("outside");
    fs::create_dir(&outside).unwrap();
    fs::write(outside.join("portrait.png"), b"host fixture").unwrap();
    fs::create_dir(generation.join("theme")).unwrap();
    symlink(&outside, generation.join("theme/backgrounds")).unwrap();
    let mut report: Value =
        serde_json::from_slice(&fs::read(generation.join("report.json")).unwrap()).unwrap();
    report["backgrounds"] = json!(["backgrounds/portrait.png"]);
    report["selected_background"] = json!("backgrounds/portrait.png");
    fs::write(
        generation.join("report.json"),
        serde_json::to_vec(&report).unwrap(),
    )
    .unwrap();
    let mut appearance: Value =
        serde_json::from_slice(&fs::read(generation.join("appearance.json")).unwrap()).unwrap();
    appearance["background"] = json!("background");
    fs::write(
        generation.join("appearance.json"),
        serde_json::to_vec(&appearance).unwrap(),
    )
    .unwrap();
    let mut receiver = AppearanceReceiver::bind_with_roots(
        fixture.socket(),
        Some(fixture.default.clone()),
        fixture.state.clone(),
    )
    .unwrap();
    let id = generation.file_name().unwrap().to_str().unwrap();
    let mut peer = UnixStream::connect(fixture.socket()).unwrap();
    peer.write_all(
        format!(
            "{}\n",
            json!({"protocol":1,"phase":"prepare",
        "generation":id,"path":generation,"previous_generation":null,"previous_path":null})
        )
        .as_bytes(),
    )
    .unwrap();
    receiver.accept().unwrap();
    assert!(receiver
        .receive()
        .unwrap_err()
        .contains("background escapes staged theme"));
    assert!(receiver.prepared().is_none());
}

#[test]
fn all_background_choices_and_brush_shape_are_retained() {
    let fixture = Fixture::new();
    let generation = fixture.user_generation();
    fs::create_dir_all(generation.join("theme/backgrounds")).unwrap();
    fs::write(
        generation.join("theme/backgrounds/portrait.png"),
        b"host fixture",
    )
    .unwrap();
    fs::write(
        generation.join("theme/backgrounds/movie.mp4"),
        b"host fixture",
    )
    .unwrap();
    let mut report: Value =
        serde_json::from_slice(&fs::read(generation.join("report.json")).unwrap()).unwrap();
    report["backgrounds"] = json!(["backgrounds/portrait.png", "backgrounds/movie.mp4"]);
    report["selected_background"] = json!("backgrounds/portrait.png");
    fs::write(
        generation.join("report.json"),
        serde_json::to_vec(&report).unwrap(),
    )
    .unwrap();
    let mut appearance: Value =
        serde_json::from_slice(&fs::read(generation.join("appearance.json")).unwrap()).unwrap();
    appearance["background"] = json!("background");
    appearance["sections"]["launcher"]["background"] = json!({"kind":"brush","alpha":0.5,"angle_degrees":45.0,
        "stops":[{"argb":"#ff001122","offset":0.0},{"argb":"#80445566","offset":1.0}]});
    fs::write(
        generation.join("appearance.json"),
        serde_json::to_vec(&appearance).unwrap(),
    )
    .unwrap();
    let mut receiver = AppearanceReceiver::bind_with_roots(
        fixture.socket(),
        Some(fixture.default.clone()),
        fixture.state.clone(),
    )
    .unwrap();
    let id = generation.file_name().unwrap().to_str().unwrap();
    let (event, _) = send(
        &mut receiver,
        &fixture.socket(),
        json!({"protocol":1,"phase":"prepare",
        "generation":id,"path":generation,"previous_generation":null,"previous_path":null}),
    );
    let snapshot = event.snapshot.unwrap();
    assert_eq!(snapshot.backgrounds.len(), 2);
    assert!(snapshot.backgrounds[1].is_video);
    assert!(snapshot.backgrounds[0].selected);
    assert_eq!(
        snapshot.background.as_ref().unwrap(),
        &generation.join("theme/backgrounds/portrait.png")
    );
    match snapshot.token("launcher", "background").unwrap() {
        AppearanceToken::Brush(brush) => {
            assert_eq!(brush.stops.len(), 2);
            assert_eq!(brush.angle_degrees, 45.0);
            assert_eq!(brush.alpha, 0.5);
        }
        _ => panic!("gradient was flattened"),
    }
    report["selected_background"] = json!("backgrounds/movie.mp4");
    fs::write(
        generation.join("report.json"),
        serde_json::to_vec(&report).unwrap(),
    )
    .unwrap();
    appearance["background"] = Value::Null;
    fs::write(
        generation.join("appearance.json"),
        serde_json::to_vec(&appearance).unwrap(),
    )
    .unwrap();
    let (video, _) = send(
        &mut receiver,
        &fixture.socket(),
        json!({"protocol":1,"phase":"prepare",
        "generation":id,"path":generation,"previous_generation":null,"previous_path":null}),
    );
    let video = video.snapshot.unwrap();
    assert!(video.background.is_none());
    assert_eq!(
        video.selected_background.unwrap(),
        generation.join("theme/backgrounds/movie.mp4")
    );
}

#[test]
fn malformed_payload_and_foreign_generation_fail_without_mutating_active() {
    let fixture = Fixture::new();
    let generation = fixture.user_generation();
    let mut appearance: Value =
        serde_json::from_slice(&fs::read(generation.join("appearance.json")).unwrap()).unwrap();
    appearance["sections"]["launcher"]["background"]["alpha"] = json!(2.0);
    fs::write(
        generation.join("appearance.json"),
        serde_json::to_vec(&appearance).unwrap(),
    )
    .unwrap();
    let mut receiver = AppearanceReceiver::bind_with_roots(
        fixture.socket(),
        Some(fixture.default.clone()),
        fixture.state.clone(),
    )
    .unwrap();
    let id = generation.file_name().unwrap().to_str().unwrap();
    let mut peer = UnixStream::connect(fixture.socket()).unwrap();
    peer.write_all(
        format!(
            "{}\n",
            json!({"protocol":1,"phase":"prepare", "generation":id,
        "path":generation,"previous_generation":null,"previous_path":null})
        )
        .as_bytes(),
    )
    .unwrap();
    receiver.accept().unwrap();
    assert!(receiver.receive().unwrap_err().contains("out of range"));
    assert!(receiver.peer_fd().is_none());
    assert!(receiver.prepared().is_none());
    assert_eq!(receiver.active().unwrap().path, fixture.default);
    let foreign = fixture.root.join(id);
    fs::create_dir(&foreign).unwrap();
    fs::copy(
        fixture.default.join("appearance.json"),
        foreign.join("appearance.json"),
    )
    .unwrap();
    fs::copy(
        fixture.default.join("report.json"),
        foreign.join("report.json"),
    )
    .unwrap();
    let mut peer = UnixStream::connect(fixture.socket()).unwrap();
    peer.write_all(
        format!(
            "{}\n",
            json!({"protocol":1,"phase":"prepare", "generation":id,
        "path":foreign,"previous_generation":null,"previous_path":null})
        )
        .as_bytes(),
    )
    .unwrap();
    receiver.accept().unwrap();
    assert!(receiver
        .receive()
        .unwrap_err()
        .contains("outside private cache"));
    assert!(receiver.peer_fd().is_none());
}

#[test]
fn rollback_without_prepare_restores_prior_snapshot_and_acks_exact_generation() {
    let fixture = Fixture::new();
    let previous = fixture.user_generation();
    let mut receiver = AppearanceReceiver::bind_with_roots(
        fixture.socket(),
        Some(fixture.default.clone()),
        fixture.state.clone(),
    )
    .unwrap();
    let id = previous.file_name().unwrap().to_str().unwrap();
    let (event, reply) = send(
        &mut receiver,
        &fixture.socket(),
        json!({"protocol":1,"phase":"rollback","generation":id,"path":previous}),
    );
    assert_eq!(event.phase, AppearancePhase::Rollback);
    assert_eq!(reply["generation"], id);
    assert_eq!(receiver.active().unwrap().generation, id);
    assert!(receiver.prepared().is_none());
}

#[test]
fn fragmented_request_and_frozen_prepare_snapshot_do_not_reread_mutated_payload() {
    let fixture = Fixture::new();
    let generation = fixture.user_generation();
    let id = generation.file_name().unwrap().to_str().unwrap();
    let mut receiver = AppearanceReceiver::bind_with_roots(
        fixture.socket(),
        Some(fixture.default.clone()),
        fixture.state.clone(),
    )
    .unwrap();
    let request = format!(
        "{}\n",
        json!({"protocol":1,"phase":"prepare","generation":id,
        "path":generation,"previous_generation":null,"previous_path":null})
    );
    let mut peer = UnixStream::connect(fixture.socket()).unwrap();
    peer.set_read_timeout(Some(Duration::from_millis(250)))
        .unwrap();
    let split = request.len() / 2;
    peer.write_all(&request.as_bytes()[..split]).unwrap();
    receiver.accept().unwrap();
    assert!(receiver.receive().unwrap().is_none());
    peer.write_all(&request.as_bytes()[split..]).unwrap();
    let event = receiver.receive().unwrap().unwrap();
    receiver.respond(event, true).unwrap();
    let mut reply = String::new();
    peer.read_to_string(&mut reply).unwrap();
    assert_eq!(
        serde_json::from_str::<Value>(&reply).unwrap()["status"],
        "ok"
    );
    let mut changed: Value =
        serde_json::from_slice(&fs::read(generation.join("appearance.json")).unwrap()).unwrap();
    changed["sections"]["launcher"]["background"]["alpha"] = json!(0.1);
    fs::write(
        generation.join("appearance.json"),
        serde_json::to_vec(&changed).unwrap(),
    )
    .unwrap();
    let (commit, _) = send(
        &mut receiver,
        &fixture.socket(),
        json!({"protocol":1,"phase":"commit","generation":id,"path":generation}),
    );
    match commit
        .snapshot
        .unwrap()
        .token("launcher", "background")
        .unwrap()
    {
        AppearanceToken::Brush(brush) => assert_eq!(brush.alpha, 0.95),
        _ => panic!("brush lost"),
    }
}

#[test]
fn oversized_request_is_closed_without_event_or_state_change() {
    let fixture = Fixture::new();
    let mut receiver = AppearanceReceiver::bind_with_roots(
        fixture.socket(),
        Some(fixture.default.clone()),
        fixture.state.clone(),
    )
    .unwrap();
    let mut peer = UnixStream::connect(fixture.socket()).unwrap();
    peer.write_all(&vec![b'x'; 4097]).unwrap();
    receiver.accept().unwrap();
    assert!(receiver.receive().unwrap_err().contains("exceeds bound"));
    assert!(receiver.peer_fd().is_none());
    assert!(receiver.prepared().is_none());
    assert_eq!(receiver.active().unwrap().path, fixture.default);
}
