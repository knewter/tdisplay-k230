//! k230-modem: the one owner of the nRF9151's UART and enable line.

use k230_modem::at::AtError;
use k230_modem::control::{self, Command};
use k230_modem::engine::{Event, Modem, Radio, Timeouts};
use k230_modem::gpio::GpioEnable;
use k230_modem::pty::NmeaPty;
use k230_modem::recovery::RecoveryGate;
use k230_modem::serial::SerialLink;
use k230_modem::settings::Settings;
use k230_modem::sms::SmsStore;
use k230_modem::state::{write_atomic, PowerState, Registration};
use std::cell::RefCell;
use std::io::{Read, Write};
use std::os::unix::fs::PermissionsExt;
use std::os::unix::net::{UnixListener, UnixStream};
use std::path::PathBuf;
use std::rc::Rc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

static STOP: AtomicBool = AtomicBool::new(false);

extern "C" fn on_signal(_: libc::c_int) {
    STOP.store(true, Ordering::SeqCst);
}

struct Args {
    device: String,
    enable_line: String,
    run_dir: PathBuf,
    state_dir: PathBuf,
    group: Option<String>,
}

fn parse_args() -> Result<Args, String> {
    let mut a = Args {
        device: "/dev/ttyS3".into(),
        enable_line: "nrf9151-enable".into(),
        run_dir: "/run/k230/modem".into(),
        state_dir: "/var/lib/k230/modem".into(),
        group: None,
    };
    let mut it = std::env::args().skip(1);
    while let Some(k) = it.next() {
        let v = it.next().ok_or_else(|| format!("{k} needs a value"))?;
        match k.as_str() {
            "--device" => a.device = v,
            "--enable-line" => a.enable_line = v,
            "--run-dir" => a.run_dir = v.into(),
            "--state-dir" => a.state_dir = v.into(),
            "--group" => a.group = Some(v),
            _ => return Err(format!("unknown option {k}")),
        }
    }
    Ok(a)
}

fn group_id(name: &str) -> Option<u32> {
    let c = std::ffi::CString::new(name).ok()?;
    // SAFETY: getgrnam returns null or a pointer valid until the next call.
    let g = unsafe { libc::getgrnam(c.as_ptr()) };
    if g.is_null() {
        None
    } else {
        Some(unsafe { (*g).gr_gid })
    }
}

fn now_secs() -> u64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0)
}

struct App {
    modem: Modem,
    settings: Settings,
    settings_path: PathBuf,
    state_path: PathBuf,
    store: SmsStore,
    pty: Rc<RefCell<NmeaPty>>,
    gate: RecoveryGate,
    last_json: String,
    last_reg: Registration,
    next_health: Instant,
    next_recover_try: Instant,
}

impl App {
    fn target(&self) -> Radio {
        Radio::from_choices(self.settings.cellular, self.settings.location)
    }

    fn publish(&mut self) {
        let mut st = self.modem.state.clone();
        st.sms_count = self.store.count() as u32;
        st.cellular = self.settings.cellular;
        st.location = self.settings.location;
        st.updated = 0;
        let body = st.to_json();
        if body == self.last_json {
            return;
        }
        st.updated = now_secs();
        if let Err(e) = write_atomic(&self.state_path, st.to_json().as_bytes(), 0o640) {
            eprintln!("k230-modem: cannot write state: {e}");
        }
        self.last_json = body;
    }

    fn drain_events(&mut self) {
        for ev in std::mem::take(&mut self.modem.events) {
            let Event::Sms(sms) = ev;
            // Sender and body go to the store only, never to the journal.
            if let Err(e) = self.store.append(&sms) {
                eprintln!("k230-modem: cannot store a message: {e}");
            }
            eprintln!("k230-modem: stored an incoming message");
        }
    }

    /// Apply the persisted choices, recovering at most once a minute.
    fn apply(&mut self) -> Result<(), AtError> {
        let target = self.target();
        if target != Radio::Off && self.modem.radio() == Radio::Off {
            self.modem.state.power = PowerState::PoweringOn;
            self.publish();
        }
        if target.location() != (self.modem.state.gnss != k230_modem::state::GnssState::Off) {
            self.pty.borrow_mut().flush();
        }
        let r = self.modem.set_radio(target);
        self.drain_events();
        self.publish();
        match r {
            Err(e) if matches!(e, AtError::Timeout | AtError::Io(_)) => {
                self.recover(&e);
                Err(e)
            }
            other => other,
        }
    }

    fn recover(&mut self, why: &AtError) {
        self.modem.state.power = PowerState::Error;
        self.modem.state.last_error.get_or_insert_with(|| format!("{why}"));
        self.publish();
        self.next_recover_try = Instant::now() + Duration::from_secs(5);
        if self.target() == Radio::Off {
            return;
        }
        if !self.gate.permit(Instant::now()) {
            eprintln!("k230-modem: recovery suppressed (one per minute)");
            return;
        }
        eprintln!("k230-modem: power-cycling the modem after: {why}");
        self.modem.hard_cycle();
        let target = self.target();
        if let Err(e) = self.modem.set_radio(target) {
            eprintln!("k230-modem: recovery failed: {e}");
            self.modem.state.power = PowerState::Error;
            self.modem.state.last_error = Some(format!("{e}"));
        }
        self.drain_events();
        self.publish();
    }

    fn tick(&mut self) {
        let now = Instant::now();
        if self.modem.state.power == PowerState::Error && self.target() != Radio::Off && now >= self.next_recover_try {
            self.recover(&AtError::Timeout);
            return;
        }
        if self.modem.radio() == Radio::Off {
            std::thread::sleep(Duration::from_millis(200));
            return;
        }
        let r = self.modem.poll(Duration::from_millis(200));
        if let Err(e) = r {
            self.recover(&e);
            return;
        }
        if self.modem.take_unexpected_reset() {
            eprintln!("k230-modem: the modem restarted on its own; reconfiguring");
            self.modem.hard_cycle();
            if let Err(e) = self.apply() {
                eprintln!("k230-modem: reconfigure failed: {e}");
            }
            return;
        }
        if self.modem.consecutive_timeouts >= 3 {
            self.recover(&AtError::Timeout);
            return;
        }
        let reg = self.modem.state.registration;
        let mut r: Result<(), AtError> = Ok(());
        if reg != self.last_reg {
            self.last_reg = reg;
            if matches!(reg, Registration::RegisteredHome | Registration::RegisteredRoaming) {
                r = self.modem.refresh_signal();
            }
        }
        if r.is_ok() && now >= self.next_health {
            self.next_health = now + Duration::from_secs(30);
            r = if self.modem.radio().cellular() {
                let s = self.modem.refresh_sim();
                s.and_then(|_| self.modem.refresh_signal())
            } else {
                self.modem.ping()
            };
        }
        if let Err(e) = r {
            self.recover(&e);
            return;
        }
        self.drain_events();
        self.publish();
    }

    fn persist(&mut self) {
        if let Err(e) = self.settings.save(&self.settings_path) {
            eprintln!("k230-modem: cannot save settings: {e}");
        }
    }

    fn handle(&mut self, mut s: UnixStream) {
        let _ = s.set_nonblocking(false);
        let _ = s.set_read_timeout(Some(Duration::from_secs(5)));
        let mut line = Vec::new();
        let mut byte = [0u8; 1];
        while line.len() < 256 {
            match s.read(&mut byte) {
                Ok(1) if byte[0] == b'\n' => break,
                Ok(1) => line.push(byte[0]),
                _ => break,
            }
        }
        let reply = match control::parse(&String::from_utf8_lossy(&line)) {
            Err(code) => format!("err {code}"),
            Ok(cmd) => self.run(cmd, &mut s),
        };
        let _ = s.write_all(format!("{reply}\n").as_bytes());
    }

    fn run(&mut self, cmd: Command, s: &mut UnixStream) -> String {
        // Log the verb only; arguments (a PIN, a number) never reach the journal.
        match cmd {
            Command::Status => {
                eprintln!("k230-modem: control: status");
                let mut st = self.modem.state.clone();
                st.sms_count = self.store.count() as u32;
                st.updated = now_secs();
                format!("ok {}", st.to_json())
            }
            Command::PowerOn | Command::PowerOff | Command::GnssOn | Command::GnssOff => {
                match cmd {
                    Command::PowerOn => self.settings.cellular = true,
                    Command::PowerOff => self.settings.cellular = false,
                    Command::GnssOn => self.settings.location = true,
                    _ => self.settings.location = false,
                }
                eprintln!("k230-modem: control: cellular={} location={}", self.settings.cellular, self.settings.location);
                self.persist();
                match self.apply() {
                    Ok(()) => "ok".into(),
                    Err(e) => format!("err modem_{e}"),
                }
            }
            Command::Pin(pin) => {
                eprintln!("k230-modem: control: pin");
                if !self.modem.radio().cellular() {
                    return "err cellular_off".into();
                }
                let r = self.modem.submit_pin(&pin);
                drop(pin);
                self.publish();
                match r {
                    Ok(()) => "ok".into(),
                    Err(AtError::Cme(c)) if c == "16" => match self.modem.state.pin_attempts {
                        Some(n) => format!("err pin_rejected attempts={n}"),
                        None => "err pin_rejected".into(),
                    },
                    Err(e) => format!("err pin_failed_{e}"),
                }
            }
            Command::SmsSend { number } => {
                eprintln!("k230-modem: control: sms send");
                let mut body = Vec::new();
                let _ = s.take(1025).read_to_end(&mut body);
                let body = String::from_utf8_lossy(&body).trim_end_matches('\n').to_string();
                if let Err(code) = control::valid_body(&body) {
                    return format!("err {code}");
                }
                if !self.modem.radio().cellular() {
                    return "err cellular_off".into();
                }
                match self.modem.send_sms(&number, &body) {
                    Ok(()) => "ok".into(),
                    Err(e) => format!("err sms_failed_{e}"),
                }
            }
            Command::SmsClear => {
                eprintln!("k230-modem: control: sms clear");
                match self.store.clear() {
                    Ok(()) => {
                        self.publish();
                        "ok".into()
                    }
                    Err(_) => "err store".into(),
                }
            }
        }
    }
}

fn run() -> Result<(), String> {
    let a = parse_args()?;
    let gid = a.group.as_deref().and_then(group_id);
    std::fs::create_dir_all(&a.run_dir).map_err(|e| format!("run dir: {e}"))?;
    std::fs::create_dir_all(&a.state_dir).map_err(|e| format!("state dir: {e}"))?;

    // Take the enable line first and hold it low: off until a person asks.
    let gpio = GpioEnable::open_named(&a.enable_line).map_err(|e| format!("enable line {}: {e}", a.enable_line))?;
    let link = SerialLink::open(&a.device).map_err(|e| format!("{}: {e}", a.device))?;
    let pty = Rc::new(RefCell::new(
        NmeaPty::create(&a.run_dir.join("nmea"), gid).map_err(|e| format!("nmea pty: {e}"))?,
    ));

    let nmea_sink = pty.clone();
    let mut modem = Modem::new(
        Box::new(link),
        Box::new(gpio),
        Box::new(|m| eprintln!("k230-modem: {m}")),
        Box::new(move |s| nmea_sink.borrow_mut().write_line(s)),
        Timeouts::default(),
    );
    modem.line_low().map_err(|e| format!("enable line: {e}"))?;

    let settings_path = a.state_dir.join("settings.json");
    let sock_path = a.run_dir.join("control");
    let _ = std::fs::remove_file(&sock_path);
    let listener = UnixListener::bind(&sock_path).map_err(|e| format!("control socket: {e}"))?;
    listener.set_nonblocking(true).map_err(|e| e.to_string())?;
    let _ = std::fs::set_permissions(&sock_path, std::fs::Permissions::from_mode(0o660));
    if let Some(g) = gid {
        if let Ok(c) = std::ffi::CString::new(sock_path.to_string_lossy().as_bytes()) {
            // SAFETY: valid path; a failed chown only leaves the socket root-only.
            unsafe { libc::chown(c.as_ptr(), 0, g) };
        }
    }
    // SAFETY: the handler only stores to an atomic.
    unsafe {
        libc::signal(libc::SIGTERM, on_signal as usize);
        libc::signal(libc::SIGINT, on_signal as usize);
    }

    let mut app = App {
        modem,
        settings: Settings::load(&settings_path),
        settings_path,
        state_path: a.run_dir.join("state.json"),
        store: SmsStore::open(a.state_dir.join("sms.jsonl"), 200),
        pty,
        gate: RecoveryGate::new(Duration::from_secs(60)),
        last_json: String::new(),
        last_reg: Registration::Unknown,
        next_health: Instant::now() + Duration::from_secs(30),
        next_recover_try: Instant::now(),
    };
    app.publish();
    eprintln!("k230-modem: started; modem off (cellular={} location={})", app.settings.cellular, app.settings.location);
    if app.target() != Radio::Off {
        let _ = app.apply();
    }

    while !STOP.load(Ordering::SeqCst) {
        match listener.accept() {
            Ok((s, _)) => app.handle(s),
            Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => {}
            Err(e) => eprintln!("k230-modem: accept: {e}"),
        }
        app.tick();
    }
    eprintln!("k230-modem: stopping; powering the modem off");
    let _ = app.modem.power_off();
    app.publish();
    let _ = std::fs::remove_file(&sock_path);
    Ok(())
}

fn main() {
    if let Err(e) = run() {
        eprintln!("k230-modem: {e}");
        std::process::exit(1);
    }
}
