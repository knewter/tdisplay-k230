//! Raises the on-screen keyboard when a text field takes focus and lowers it
//! when focus leaves (openspec/changes/a-focused-text-field-raises-the-keyboard).
//!
//! A bare input-method-v2 client. It binds the seat's input method, waits for
//! `activate`/`deactivate`/`done`, and runs the same
//! `k230-keyboard-gesture-signal show|hide` helper the two-finger gesture and
//! the shell use. It never commits text, never sets preedit and never
//! requests the keyboard grab, so every key still reaches the focused client.
//! It blocks in the Wayland queue; there is no timer and no polling.
//!
//! Environment:
//!   K230_KEYBOARD_SIGNAL        helper to run (required)
//!   K230_OSK_KEY_STAMP          file whose mtime is the last base key press
//!                               (default $XDG_RUNTIME_DIR/k230-keyboard-base-last-key)
//!   K230_OSK_SUPPRESS_SECONDS   suppression window (default 10)

use k230_shell_rust::osk_focus::{self, Action, Event, Focus};
use std::path::PathBuf;
use std::process::{Command, ExitCode};
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use wayland_client::{
    globals::{registry_queue_init, GlobalListContents},
    protocol::{wl_registry, wl_seat},
    Connection, Dispatch, QueueHandle,
};
use wayland_protocols_misc::zwp_input_method_v2::client::{
    zwp_input_method_manager_v2::{self, ZwpInputMethodManagerV2},
    zwp_input_method_v2::{self, ZwpInputMethodV2},
};

struct App {
    focus: Focus,
    signal: PathBuf,
    stamp: Option<PathBuf>,
    suppress: Duration,
    ignore: Vec<String>,
    sway: Option<PathBuf>,
}

/// True when the focused window is one of `ignore`. Asked only before a
/// show, so a focus change costs one `get_tree` at most.
fn focused_is_ignored(ignore: &[String], sway: &Option<PathBuf>) -> bool {
    let Some(path) = sway else { return false };
    if ignore.is_empty() {
        return false;
    }
    match k230_shell_rust::sway_ipc::query(path, 4, b"") {
        Ok(tree) => osk_focus::focused_app_id(&tree).is_some_and(|id| ignore.iter().any(|i| *i == id)),
        Err(e) => {
            eprintln!("k230-osk-focus: get_tree failed: {e}");
            false
        }
    }
}

fn secs(t: SystemTime) -> f64 {
    t.duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}

fn since_last_key(stamp: &Option<PathBuf>) -> Option<Duration> {
    let path = stamp.as_ref()?;
    let mtime = std::fs::metadata(path).ok()?.modified().ok()?;
    osk_focus::stamp_age(secs(SystemTime::now()), secs(mtime))
}

impl App {
    fn feed(&mut self, event: Event) {
        let stamp = &self.stamp;
        let action = self
            .focus
            .handle(event, || since_last_key(stamp), self.suppress);
        if action == Some(Action::Show) && focused_is_ignored(&self.ignore, &self.sway) {
            return;
        }
        if let Some(action) = action {
            let word = match action {
                Action::Show => "show",
                Action::Hide => "hide",
            };
            match Command::new(&self.signal).arg(word).status() {
                Ok(s) if s.success() => {}
                Ok(s) => eprintln!("k230-osk-focus: {word} signal exited {s}"),
                Err(e) => eprintln!("k230-osk-focus: {word} signal failed: {e}"),
            }
        }
    }
}

impl Dispatch<wl_registry::WlRegistry, GlobalListContents> for App {
    fn event(
        _: &mut Self,
        _: &wl_registry::WlRegistry,
        _: wl_registry::Event,
        _: &GlobalListContents,
        _: &Connection,
        _: &QueueHandle<Self>,
    ) {
    }
}
impl Dispatch<wl_seat::WlSeat, ()> for App {
    fn event(
        _: &mut Self,
        _: &wl_seat::WlSeat,
        _: wl_seat::Event,
        _: &(),
        _: &Connection,
        _: &QueueHandle<Self>,
    ) {
    }
}
impl Dispatch<ZwpInputMethodManagerV2, ()> for App {
    fn event(
        _: &mut Self,
        _: &ZwpInputMethodManagerV2,
        _: zwp_input_method_manager_v2::Event,
        _: &(),
        _: &Connection,
        _: &QueueHandle<Self>,
    ) {
    }
}
impl Dispatch<ZwpInputMethodV2, ()> for App {
    fn event(
        state: &mut Self,
        _: &ZwpInputMethodV2,
        event: zwp_input_method_v2::Event,
        _: &(),
        _: &Connection,
        _: &QueueHandle<Self>,
    ) {
        use zwp_input_method_v2::Event as E;
        match event {
            E::Activate => state.feed(Event::Activate),
            E::Deactivate => state.feed(Event::Deactivate),
            E::Done => state.feed(Event::Done),
            E::Unavailable => {
                eprintln!("k230-osk-focus: input method unavailable (another client owns it)");
                state.feed(Event::Unavailable);
            }
            _ => {}
        }
    }
}

fn run() -> Result<(), String> {
    let signal = std::env::var_os("K230_KEYBOARD_SIGNAL")
        .map(PathBuf::from)
        .ok_or("K230_KEYBOARD_SIGNAL is not set")?;
    let stamp = std::env::var_os("K230_OSK_KEY_STAMP")
        .map(PathBuf::from)
        .or_else(|| {
            std::env::var_os("XDG_RUNTIME_DIR")
                .map(|d| PathBuf::from(d).join("k230-keyboard-base-last-key"))
        });
    let suppress =
        osk_focus::parse_suppress(std::env::var("K230_OSK_SUPPRESS_SECONDS").ok().as_deref());

    let conn = Connection::connect_to_env().map_err(|e| e.to_string())?;
    let (globals, mut queue) = registry_queue_init::<App>(&conn).map_err(|e| e.to_string())?;
    let qh = queue.handle();
    let seat: wl_seat::WlSeat = globals
        .bind(&qh, 1..=1, ())
        .map_err(|e| format!("wl_seat: {e}"))?;
    let manager: ZwpInputMethodManagerV2 = globals
        .bind(&qh, 1..=1, ())
        .map_err(|e| format!("zwp_input_method_manager_v2: {e}"))?;
    let _im = manager.get_input_method(&seat, &qh, ());

    let mut app = App {
        focus: Focus::new(),
        signal,
        stamp,
        suppress,
        ignore: osk_focus::parse_ignore(std::env::var("K230_OSK_FOCUS_IGNORE").ok().as_deref()),
        sway: std::env::var_os("SWAYSOCK").map(PathBuf::from),
    };
    loop {
        queue
            .blocking_dispatch(&mut app)
            .map_err(|e| e.to_string())?;
    }
}

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("k230-osk-focus: {e}");
            ExitCode::FAILURE
        }
    }
}
