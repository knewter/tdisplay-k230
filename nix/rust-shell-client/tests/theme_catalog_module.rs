//! Direct-helper-socket proof for `ThemeWorker` (no board, no Python, no
//! real `theme-helper.service`): a fake Unix-socket "daemon" and a fake
//! subprocess script stand in for the real ones, so this proves the
//! socket-first/subprocess-fallback *decision* itself, not the daemon's own
//! behaviour (already proven host-side by `tests.test_theme_helper_daemon`
//! and `tests.test_omarchy_theme_activation`).
#[path = "../src/theme_catalog.rs"]
mod theme_catalog;

use serde_json::{json, Value};
use std::{
    fs,
    io::{Read, Write},
    os::unix::{fs::PermissionsExt, net::UnixListener},
    path::{Path, PathBuf},
    thread,
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};
use theme_catalog::{ThemeReply, ThemeRequest, ThemeResponse, ThemeWorker};

struct Fixture {
    root: PathBuf,
}
impl Fixture {
    fn new() -> Self {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let root = std::env::temp_dir().join(format!(
            "k230-theme-catalog-{}-{nonce}",
            std::process::id()
        ));
        fs::create_dir(&root).unwrap();
        Self { root }
    }
    fn path(&self, name: &str) -> PathBuf {
        self.root.join(name)
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.root);
    }
}

/// A subprocess standing in for `k230-theme`: if actually invoked, it
/// creates `marker` (so a test can assert it was never run) and prints
/// `body` as its `list`/`preview`/`activate` reply.
fn fake_command(fixture: &Fixture, marker: &Path, body: &Value) -> PathBuf {
    let path = fixture.path("fake-k230-theme");
    fs::write(
        &path,
        format!(
            "#!/bin/sh\ntouch {}\ncat <<'EOF'\n{}\nEOF\n",
            marker.display(),
            body
        ),
    )
    .unwrap();
    fs::set_permissions(&path, fs::Permissions::from_mode(0o700)).unwrap();
    path
}

fn list_body() -> Value {
    json!({"schema": 1, "themes": [], "active": {"id": Value::Null, "generation": Value::Null}})
}

/// Accepts exactly one connection, reads its newline-terminated request,
/// asserts it matches `theme_client.py`'s own `as_request()` shape for a
/// `list` call, and replies with `{"result": body, "exit_code": code}`.
fn serve_one(socket_path: PathBuf, body: Value, code: i64) -> thread::JoinHandle<Value> {
    let listener = UnixListener::bind(&socket_path).unwrap();
    thread::spawn(move || {
        let (mut stream, _) = listener.accept().unwrap();
        let mut buffer = Vec::new();
        let mut chunk = [0u8; 4096];
        loop {
            let count = stream.read(&mut chunk).unwrap();
            if count == 0 {
                break;
            }
            buffer.extend_from_slice(&chunk[..count]);
            if buffer.contains(&b'\n') {
                break;
            }
        }
        let end = buffer.iter().position(|byte| *byte == b'\n').unwrap();
        let request: Value = serde_json::from_slice(&buffer[..end]).unwrap();
        let reply = json!({"result": body, "exit_code": code});
        stream
            .write_all((reply.to_string() + "\n").as_bytes())
            .unwrap();
        request
    })
}

fn recv(worker: &ThemeWorker, id: u64) -> ThemeReply {
    let deadline = Instant::now() + Duration::from_secs(5);
    loop {
        if let Some(reply) = worker.try_recv() {
            assert_eq!(reply.id, id);
            return reply;
        }
        assert!(Instant::now() < deadline, "worker never replied");
        thread::sleep(Duration::from_millis(5));
    }
}

#[test]
fn a_working_helper_socket_answers_without_ever_running_the_subprocess() {
    let fixture = Fixture::new();
    let socket_path = fixture.path("helper.sock");
    let marker = fixture.path("subprocess-ran");
    let poison = fake_command(
        &fixture,
        &marker,
        &json!({"schema": 1, "error": "must not run: the socket should have answered", "activated": false}),
    );
    let server = serve_one(socket_path.clone(), list_body(), 0);

    let worker = ThemeWorker::spawn(poison, socket_path);
    let id = worker.try_submit(ThemeRequest::List).unwrap();
    let reply = recv(&worker, id);

    let request = server.join().unwrap();
    assert_eq!(request["action"], "list");
    assert!(request.get("id").is_none(), "list must not carry an id");
    match reply.result {
        Ok(ThemeResponse::List(list)) => assert!(list.themes.is_empty()),
        other => panic!("expected an empty list reply, got {other:?}"),
    }
    assert!(!marker.exists(), "the subprocess fallback ran despite a working socket reply");
}

#[test]
fn a_daemon_reported_error_is_returned_without_falling_back() {
    let fixture = Fixture::new();
    let socket_path = fixture.path("helper.sock");
    let marker = fixture.path("subprocess-ran");
    let poison = fake_command(
        &fixture,
        &marker,
        &json!({"schema": 1, "error": "must not run", "activated": false}),
    );
    let server = serve_one(
        socket_path.clone(),
        json!({"schema": 1, "error": "theme is no longer in the catalog", "activated": false}),
        1,
    );

    let worker = ThemeWorker::spawn(poison, socket_path);
    let id = worker
        .try_submit(ThemeRequest::Preview {
            theme_id: "a".repeat(24),
            background_id: None,
        })
        .unwrap();
    let reply = recv(&worker, id);
    server.join().unwrap();

    match reply.result {
        Err(message) => assert_eq!(message, "theme is no longer in the catalog"),
        other => panic!("expected the daemon's own error, got {other:?}"),
    }
    assert!(!marker.exists(), "a daemon-reported error must not retry via the subprocess");
}

#[test]
fn a_missing_helper_socket_falls_back_to_the_subprocess() {
    let fixture = Fixture::new();
    let socket_path = fixture.path("no-such-helper.sock"); // never bound
    let marker = fixture.path("subprocess-ran");
    let command = fake_command(&fixture, &marker, &list_body());

    let worker = ThemeWorker::spawn(command, socket_path);
    let id = worker.try_submit(ThemeRequest::List).unwrap();
    let reply = recv(&worker, id);

    assert!(marker.exists(), "a missing socket must fall back to the subprocess");
    match reply.result {
        Ok(ThemeResponse::List(list)) => assert!(list.themes.is_empty()),
        other => panic!("expected the subprocess's own list reply, got {other:?}"),
    }
}

#[test]
fn a_malformed_socket_reply_falls_back_to_the_subprocess() {
    let fixture = Fixture::new();
    let socket_path = fixture.path("helper.sock");
    let marker = fixture.path("subprocess-ran");
    let command = fake_command(&fixture, &marker, &list_body());
    let listener = UnixListener::bind(&socket_path).unwrap();
    let server = thread::spawn(move || {
        let (mut stream, _) = listener.accept().unwrap();
        // Not JSON at all, and no trailing newline either.
        stream.write_all(b"not json").unwrap();
    });

    let worker = ThemeWorker::spawn(command, socket_path);
    let id = worker.try_submit(ThemeRequest::List).unwrap();
    let reply = recv(&worker, id);
    server.join().unwrap();

    assert!(marker.exists(), "a malformed reply must fall back to the subprocess");
    assert!(matches!(reply.result, Ok(ThemeResponse::List(_))));
}

#[test]
fn an_empty_helper_socket_path_disables_the_direct_path_entirely() {
    // Matches `theme_command`'s own unset-env convention in `main.rs`: an
    // empty path means "no direct socket attempt", not "connect to the
    // current directory".
    let fixture = Fixture::new();
    let marker = fixture.path("subprocess-ran");
    let command = fake_command(&fixture, &marker, &list_body());

    let worker = ThemeWorker::spawn(command, PathBuf::new());
    let id = worker.try_submit(ThemeRequest::List).unwrap();
    let reply = recv(&worker, id);

    assert!(marker.exists());
    assert!(matches!(reply.result, Ok(ThemeResponse::List(_))));
}
