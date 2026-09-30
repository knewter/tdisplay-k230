//! k230-touch-trackpad: while an HDMI output is active (panel dark), grabs
//! the GT9895 touchscreen and re-emits its multitouch contacts through a
//! virtual uinput touchpad device, so libinput classifies it as a
//! touchpad and does its own pointer acceleration, tap-to-click,
//! two-finger scroll, and pinch/swipe gesture recognition. While the
//! panel is the active output, the touchscreen is left ungrabbed for the
//! coordinator's direct absolute-touch `map_to_output` mapping.
//!
//! See `openspec/changes/the-touchscreen-becomes-an-hdmi-trackpad/` for
//! the capability this implements and what remains board-gated, and
//! `docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/board-hang-2026-09-29.md`
//! for the board failure the `--dry-run`/`--log-events` flags, the
//! degenerate-axis rejection in `uinput::axis_plan`, the `wait_readable`
//! `revents` fix, and the bounded drain loop below all exist to fix or
//! guard against.

mod devsearch;
mod event;
mod gestures;
mod mode;
mod relay;
mod shell_ipc;
mod touchdev;
mod uinput;

use event::InputEvent;
use mode::Mode;
use relay::Relay;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;
use uinput::VirtualTouchpad;

const TOUCHSCREEN_NAME: &str = "Goodix Berlin Capacitive TouchScreen";
const VIRTUAL_DEVICE_NAME: &str = "K230 Virtual Touchpad (HDMI mode)";
const DRM_ROOT: &str = "/sys/class/drm";
const POLL_INTERVAL: Duration = Duration::from_millis(750);
/// Hard cap on events drained per `wait_readable` wakeup, before yielding
/// back to the top of `run`'s loop (which re-checks the shutdown flag and
/// the HDMI/panel mode). This bounds the *worst case* of any bug -- a
/// stuck relay, a device that never reports idle -- to "loops this many
/// times, then yields," rather than "loops forever, taking the console
/// with it," independent of whether such a bug is proven to exist. See
/// `docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/board-hang-2026-09-29.md`.
const MAX_EVENTS_PER_DRAIN: u32 = 2048;

static SHUTDOWN: AtomicBool = AtomicBool::new(false);

extern "C" fn on_shutdown_signal(_sig: libc::c_int) {
    // Async-signal-safe: only sets an atomic, nothing else. The actual
    // cleanup (EVIOCGRAB release, UI_DEV_DESTROY) happens back on the main
    // thread via TrackpadSession's ordinary Drop, once `run`'s loop next
    // observes this flag -- never from inside the handler itself.
    SHUTDOWN.store(true, Ordering::SeqCst);
}

fn install_signal_handlers() {
    unsafe {
        libc::signal(libc::SIGINT, on_shutdown_signal as usize);
        libc::signal(libc::SIGTERM, on_shutdown_signal as usize);
    }
}

struct Args {
    drm_root: PathBuf,
    device_override: Option<PathBuf>,
    force_mode: Option<Mode>,
    /// Grabs and reads the touchscreen and runs the relay exactly as
    /// normal, but never opens `/dev/uinput` or writes to it -- so a
    /// misbehaving virtual device can never reach libinput/Sway at all.
    /// The safe first re-test step after the board hang: proves the grab
    /// and read side work without any risk of repeating the libinput
    /// interaction that preceded it.
    dry_run: bool,
    /// Prints every raw event read from the touchscreen and every event
    /// this program would emit (or, in `--dry-run`, would have emitted)
    /// to stderr. Independent of `--dry-run`; combine both for a fully
    /// side-effect-free bench trace.
    log_events: bool,
    shell_socket: Option<PathBuf>,
}

fn parse_args() -> Args {
    let mut args = Args {
        drm_root: PathBuf::from(DRM_ROOT),
        device_override: None,
        force_mode: None,
        dry_run: false,
        log_events: false,
        shell_socket: None,
    };
    for arg in std::env::args().skip(1) {
        if let Some(v) = arg.strip_prefix("--drm-root=") {
            args.drm_root = PathBuf::from(v);
        } else if let Some(v) = arg.strip_prefix("--device=") {
            args.device_override = Some(PathBuf::from(v));
        } else if let Some(v) = arg.strip_prefix("--shell-socket=") {
            args.shell_socket = Some(PathBuf::from(v));
        } else if arg == "--dry-run" {
            args.dry_run = true;
        } else if arg == "--log-events" {
            args.log_events = true;
        } else if let Some(v) = arg.strip_prefix("--force-mode=") {
            // Manual override, per the operator's "a manual override is
            // fine as extra": bypasses DRM polling entirely. Not the
            // normal path -- `auto` (the default, i.e. no flag) is.
            args.force_mode = match v {
                "trackpad" => Some(Mode::Trackpad),
                "direct" => Some(Mode::DirectTouch),
                "auto" => None,
                other => {
                    eprintln!("k230-touch-trackpad: unknown --force-mode={other}, ignoring (use trackpad|direct|auto)");
                    None
                }
            };
        } else {
            eprintln!("k230-touch-trackpad: unknown argument {arg:?}, ignoring");
        }
    }
    args
}

fn find_touchscreen(device_override: &Option<PathBuf>) -> Option<PathBuf> {
    if let Some(p) = device_override {
        return Some(p.clone());
    }
    let text = std::fs::read_to_string("/proc/bus/input/devices").ok()?;
    devsearch::find_event_device(&text, TOUCHSCREEN_NAME)
}

enum PumpResult {
    Event,
    Idle,
    Closed,
}

/// Holds the live trackpad-mode state: the grabbed touchscreen, the
/// (optional, absent in `--dry-run`) virtual device, and the translator.
/// Constructed on entering trackpad mode, dropped (which ungrabs and
/// destroys the uinput device, if any) on leaving it, on any pump error,
/// or on shutdown.
struct TrackpadSession {
    touch: touchdev::TouchDevice,
    virt: Option<VirtualTouchpad>,
    relay: Relay,
    gate: Option<gestures::Gate>,
    shell: Option<shell_ipc::Shell>,
    log_events: bool,
}

impl TrackpadSession {
    fn start(
        device_path: &Path,
        dry_run: bool,
        log_events: bool,
        socket: Option<&PathBuf>,
    ) -> std::io::Result<Self> {
        let touch = touchdev::TouchDevice::open(device_path)?;
        let ranges = touch.read_ranges()?;
        // Validate/sanitize (uinput::axis_plan) before grabbing anything:
        // a rejected axis plan means this returns Err without ever taking
        // EVIOCGRAB, so a misconfigured board is left in plain direct-touch
        // mode (the caller's Err branch does not tear anything down that
        // was never set up) rather than a half-grabbed state.
        let plan = uinput::axis_plan(&ranges).map_err(std::io::Error::other)?;
        touch.grab()?;
        let virt = if dry_run {
            eprintln!("k230-touch-trackpad: --dry-run, not creating a uinput device");
            None
        } else {
            Some(VirtualTouchpad::create(VIRTUAL_DEVICE_NAME, &ranges)?)
        };
        eprintln!(
            "k230-touch-trackpad: entered trackpad mode, grabbed {} (x {}..{} y {}..{}), axes: {}",
            device_path.display(),
            ranges.position_x.minimum,
            ranges.position_x.maximum,
            ranges.position_y.minimum,
            ranges.position_y.maximum,
            plan.iter()
                .map(|a| a.code.to_string())
                .collect::<Vec<_>>()
                .join(",")
        );
        let socket = socket.filter(|_| !dry_run);
        let gate = socket.map(|_| {
            let mut gate = gestures::Gate::new(ranges);
            if let Ok(positions) = touch.slot_positions() { gate.prime(&positions); }
            gate
        });
        Ok(TrackpadSession {
            touch,
            virt,
            relay: Relay::new(),
            log_events,
            gate,
            shell: socket.map(|path| shell_ipc::Shell::new(path.clone())),
        })
    }

    /// Reads and relays one event.
    ///
    /// `Ok(PumpResult::Idle)`: the (non-blocking) device has no event
    /// available right now -- the caller should stop draining and go back
    /// to polling the output mode.
    /// `Ok(PumpResult::Closed)`: the touchscreen device disappeared (e.g.
    /// it was unbound); the caller should tear this session down.
    fn pump_one(&mut self) -> std::io::Result<PumpResult> {
        let ev: InputEvent = match self.touch.read_event() {
            Ok(ev) => ev,
            Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => return Ok(PumpResult::Idle),
            Err(e) if e.kind() == std::io::ErrorKind::UnexpectedEof => {
                return Ok(PumpResult::Closed)
            }
            Err(e) => return Err(e),
        };
        if self.log_events {
            eprintln!(
                "k230-touch-trackpad: in  type={} code={} value={}",
                ev.type_, ev.code, ev.value
            );
        }
        if let Some(gate) = self.gate.as_mut() {
            if let Some(action) = gate.push(ev, shell_ipc::monotonic_ms()) {
                self.action(action)?;
            }
        } else {
            self.emit(vec![ev])?;
        }
        Ok(PumpResult::Event)
    }
    fn emit(&mut self, events: Vec<InputEvent>) -> std::io::Result<()> {
        for ev in events {
            for out in self.relay.process(ev) {
                if self.log_events {
                    eprintln!(
                        "k230-touch-trackpad: out type={} code={} value={}",
                        out.type_, out.code, out.value
                    );
                }
                if let Some(virt) = self.virt.as_mut() {
                    virt.emit(&out)?;
                }
            }
        }
        Ok(())
    }
    fn action(&mut self, action: gestures::Action) -> std::io::Result<()> {
        use gestures::Action;
        match action {
            Action::Pass(events) => self.emit(events)?,
            Action::Begin {
                edge,
                outward,
                dx,
                dy,
            } => {
                let started = shell_ipc::monotonic_ms();
                let accepted = self
                    .shell
                    .as_mut()
                    .is_some_and(|shell| shell.begin(edge, outward));
                if self.log_events {
                    eprintln!("k230-touch-trackpad: shell edge={} outward={} accepted={} ack_ms={}",
                        edge.name(), outward, accepted, shell_ipc::monotonic_ms() - started);
                }
                if let Some(action) = self
                    .gate
                    .as_mut()
                    .and_then(|gate| gate.acknowledge(accepted))
                {
                    self.action(action)?;
                }
                if accepted {
                    self.shell.as_ref().unwrap().motion(dx, dy);
                }
            }
            Action::Move { dx, dy } => {
                if self.log_events { eprintln!("k230-touch-trackpad: shell move dx={dx:.6} dy={dy:.6}"); }
                if let Some(shell) = &self.shell {
                    shell.motion(dx, dy);
                }
            }
            Action::End | Action::Cancel => {
                if self.log_events { eprintln!("k230-touch-trackpad: shell terminal={action:?}"); }
                if let Some(shell) = &self.shell {
                    shell.end(matches!(action, Action::Cancel));
                }
            }
        }
        Ok(())
    }
    fn expire(&mut self) -> std::io::Result<()> {
        if let Some(action) = self
            .gate
            .as_mut()
            .and_then(|gate| gate.expire(shell_ipc::monotonic_ms()))
        {
            self.action(action)?;
        }
        Ok(())
    }
}

impl Drop for TrackpadSession {
    fn drop(&mut self) {
        // Ungrab before the virtual device's own Drop destroys it, so
        // there is no window where neither device is delivering events.
        if let Some(shell) = &self.shell {
            shell.end(true);
        }
        let _ = self.touch.ungrab();
        eprintln!("k230-touch-trackpad: left trackpad mode, ungrabbed touchscreen");
    }
}

fn run(args: Args) {
    let mut session: Option<TrackpadSession> = None;
    let mut last_mode: Option<Mode> = None;
    // A start failure (e.g. axis_plan rejecting a degenerate range) will
    // keep failing identically every poll until the underlying hardware
    // state changes, so back off the retry log/attempt rate rather than
    // repeating it every POLL_INTERVAL forever.
    let mut start_failures: u32 = 0;

    while !SHUTDOWN.load(Ordering::SeqCst) {
        let mode = args
            .force_mode
            .unwrap_or_else(|| mode::detect_mode(&args.drm_root));

        if last_mode != Some(mode) {
            eprintln!(
                "k230-touch-trackpad: mode -> {mode:?} (panel connected: {})",
                mode::panel_connected(&args.drm_root)
            );
            last_mode = Some(mode);
            start_failures = 0;
        }

        match (mode, &mut session) {
            (Mode::Trackpad, None) => match find_touchscreen(&args.device_override) {
                Some(path) => match TrackpadSession::start(&path, args.dry_run, args.log_events, args.shell_socket.as_ref()) {
                    Ok(s) => {
                        session = Some(s);
                        start_failures = 0;
                    }
                    Err(e) => {
                        eprintln!("k230-touch-trackpad: failed to start trackpad session: {e}");
                        start_failures = start_failures.saturating_add(1);
                    }
                },
                None => eprintln!(
                    "k230-touch-trackpad: HDMI active but no input device named {TOUCHSCREEN_NAME:?} found in /proc/bus/input/devices"
                ),
            },
            (Mode::DirectTouch, Some(_)) => {
                session = None; // Drop ungrabs and destroys the virtual device.
            }
            _ => {}
        }

        if let Some(s) = session.as_mut() {
            // Block (via poll(2)) until either an event is ready -- so
            // real touch input has no added latency from this loop at
            // all -- or the timeout elapses, at which point the loop
            // re-checks the HDMI/panel mode and the shutdown flag. This is
            // what keeps mode-switch and signal detection bounded without
            // busy-polling the touch fd in between real touches.
            match s
                .touch
                .wait_readable(if s.gate.as_ref().is_some_and(|gate| gate.pending()) {
                    5
                } else {
                    POLL_INTERVAL.as_millis() as i32
                }) {
                Ok(true) => {
                    let mut drained = 0u32;
                    loop {
                        if SHUTDOWN.load(Ordering::SeqCst) {
                            break;
                        }
                        if drained >= MAX_EVENTS_PER_DRAIN {
                            // Yield back to the outer loop rather than
                            // draining without bound -- see
                            // MAX_EVENTS_PER_DRAIN's doc comment. If more
                            // data is still pending, the next
                            // wait_readable call returns immediately and
                            // draining resumes; this only guarantees the
                            // shutdown flag and mode are re-checked at
                            // least this often even under a sustained flood.
                            break;
                        }
                        match s.pump_one() {
                            Ok(PumpResult::Event) => {
                                drained += 1;
                                continue;
                            }
                            Ok(PumpResult::Idle) => break,
                            Ok(PumpResult::Closed) => {
                                eprintln!("k230-touch-trackpad: touchscreen device closed, leaving trackpad mode");
                                session = None;
                                break;
                            }
                            Err(e) => {
                                eprintln!("k230-touch-trackpad: read/emit error, leaving trackpad mode: {e}");
                                session = None;
                                break;
                            }
                        }
                    }
                }
                Ok(false) => {
                    if let Err(e) = s.expire() {
                        eprintln!("k230-touch-trackpad: gate expiry error: {e}");
                        session = None;
                    }
                }
                Err(e) => {
                    eprintln!("k230-touch-trackpad: poll error, leaving trackpad mode: {e}");
                    session = None;
                }
            }
        } else {
            // Backs off up to ~8x the normal poll interval after repeated
            // start failures, instead of retrying (and re-logging) a
            // doomed axis_plan rejection every 750ms forever.
            let backoff = POLL_INTERVAL * start_failures.clamp(1, 8);
            std::thread::sleep(backoff);
        }
    }

    // `session`'s Drop (ungrab + UI_DEV_DESTROY) runs here as it goes out
    // of scope, on a clean shutdown-flag exit from the loop above.
    eprintln!("k230-touch-trackpad: shutting down");
}

fn main() {
    install_signal_handlers();
    let args = parse_args();
    run(args);
}
