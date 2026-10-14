//! The AT state machine: one command in flight, a timeout on each, URCs
//! absorbed between and during commands, and the power sequencing of
//! design Decision 3.

use crate::at::{
    final_result, redact_command, split_fields, unquote, AtError, Final, Secret,
};
use crate::nmea;
use crate::sms::{parse_udh, Assembler, Sms};
use crate::state::{bars_for_rsrp, GnssState, PowerState, Registration, SimState, State};
use std::io;
use std::time::{Duration, Instant};

pub trait Link {
    fn send(&mut self, data: &[u8]) -> io::Result<()>;
    /// The next line, or `None` when `timeout` passes first.
    fn recv_line(&mut self, timeout: Duration) -> io::Result<Option<String>>;
}

pub trait EnableLine {
    fn set(&mut self, on: bool) -> io::Result<()>;
}

#[derive(Debug, Clone)]
pub struct Timeouts {
    pub ready: Duration,
    pub short: Duration,
    pub cfun: Duration,
    pub cmgs: Duration,
    /// Pause after the enable line goes low before it may rise again.
    pub settle: Duration,
}

impl Default for Timeouts {
    fn default() -> Self {
        Timeouts {
            ready: Duration::from_secs(10),
            short: Duration::from_secs(5),
            cfun: Duration::from_secs(15),
            cmgs: Duration::from_secs(60),
            settle: Duration::from_secs(2),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Radio {
    Off,
    Cellular,
    Gnss,
    Both,
}

impl Radio {
    pub fn from_choices(cellular: bool, location: bool) -> Radio {
        match (cellular, location) {
            (false, false) => Radio::Off,
            (true, false) => Radio::Cellular,
            (false, true) => Radio::Gnss,
            (true, true) => Radio::Both,
        }
    }
    pub fn cellular(self) -> bool {
        matches!(self, Radio::Cellular | Radio::Both)
    }
    pub fn location(self) -> bool {
        matches!(self, Radio::Gnss | Radio::Both)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Event {
    Sms(Sms),
}

struct CmtHeader {
    from: String,
    time: String,
    udhi: bool,
}

pub struct Modem {
    link: Box<dyn Link>,
    enable: Box<dyn EnableLine>,
    log: Box<dyn FnMut(&str)>,
    nmea: Box<dyn FnMut(&str)>,
    pub state: State,
    pub events: Vec<Event>,
    pub timeouts: Timeouts,
    pub consecutive_timeouts: u32,
    radio: Radio,
    cfun: Option<u8>,
    pending_cmt: Option<CmtHeader>,
    asm: Assembler,
    last_sent: String,
    ready_seen: bool,
    xsim_init: Option<bool>,
    sysmode_gnss_only: bool,
    cellular_configured: bool,
    gnss_running: bool,
    unexpected_reset: bool,
}

fn fatal(e: &AtError) -> bool {
    matches!(e, AtError::Timeout | AtError::Io(_))
}

impl Modem {
    pub fn new(
        link: Box<dyn Link>,
        enable: Box<dyn EnableLine>,
        log: Box<dyn FnMut(&str)>,
        nmea: Box<dyn FnMut(&str)>,
        timeouts: Timeouts,
    ) -> Modem {
        Modem {
            link,
            enable,
            log,
            nmea,
            state: State::default(),
            events: Vec::new(),
            timeouts,
            consecutive_timeouts: 0,
            radio: Radio::Off,
            cfun: None,
            pending_cmt: None,
            asm: Assembler::default(),
            last_sent: String::new(),
            ready_seen: false,
            xsim_init: None,
            sysmode_gnss_only: false,
            cellular_configured: false,
            gnss_running: false,
            unexpected_reset: false,
        }
    }

    pub fn radio(&self) -> Radio {
        self.radio
    }

    fn log(&mut self, msg: &str) {
        (self.log)(msg);
    }

    // ----- command layer -------------------------------------------------

    fn send_cmd(&mut self, cmd: &str) -> Result<(), AtError> {
        let shown = redact_command(cmd);
        self.log(&format!("> {shown}"));
        self.last_sent = cmd.to_string();
        self.link.send(format!("{cmd}\r").as_bytes())?;
        Ok(())
    }

    fn collect(&mut self, timeout: Duration, stop_at_prompt: bool) -> Result<Vec<String>, AtError> {
        let deadline = Instant::now() + timeout;
        let mut resp = Vec::new();
        loop {
            let Some(left) = deadline.checked_duration_since(Instant::now()) else {
                return Err(self.timed_out());
            };
            match self.link.recv_line(left)? {
                None => return Err(self.timed_out()),
                Some(l) => {
                    self.consecutive_timeouts = 0;
                    if l == self.last_sent {
                        continue; // echo
                    }
                    if stop_at_prompt && l == "> " {
                        return Ok(resp);
                    }
                    if let Some(f) = final_result(&l) {
                        self.log(&format!("< {l}"));
                        self.state.present = true;
                        return match f {
                            Final::Ok => Ok(resp),
                            Final::Err(e) => Err(e),
                        };
                    }
                    if !self.absorb(&l) {
                        resp.push(l);
                    }
                }
            }
        }
    }

    fn timed_out(&mut self) -> AtError {
        self.consecutive_timeouts += 1;
        let shown = redact_command(&self.last_sent);
        self.log(&format!("timeout waiting for the answer to {shown}"));
        self.state.last_error = Some(format!("timeout: {shown}"));
        AtError::Timeout
    }

    pub fn exec(&mut self, cmd: &str, timeout: Duration) -> Result<Vec<String>, AtError> {
        self.send_cmd(cmd)?;
        self.collect(timeout, false)
    }

    /// A command whose failure matters only when it means the link is gone.
    fn soft(&mut self, cmd: &str, timeout: Duration) -> Result<Vec<String>, AtError> {
        match self.exec(cmd, timeout) {
            Err(e) if !fatal(&e) => Ok(Vec::new()),
            r => r,
        }
    }

    /// Read at most one line (a URC) and absorb it.
    pub fn poll(&mut self, timeout: Duration) -> Result<(), AtError> {
        if let Some(l) = self.link.recv_line(timeout)? {
            self.consecutive_timeouts = 0;
            if final_result(&l).is_none() {
                self.absorb(&l);
            }
        }
        for s in self.asm.flush_stale(Instant::now(), Duration::from_secs(300)) {
            self.events.push(Event::Sms(s));
        }
        Ok(())
    }

    /// True once if the modem restarted on its own.
    pub fn take_unexpected_reset(&mut self) -> bool {
        std::mem::take(&mut self.unexpected_reset)
    }

    // ----- unsolicited and informational lines ------------------------------

    /// Update state from a line. Returns true when the line was consumed
    /// (not part of a command's answer).
    fn absorb(&mut self, l: &str) -> bool {
        if let Some(h) = self.pending_cmt.take() {
            self.log("< <sms body withheld>");
            self.on_sms(h, l);
            return true;
        }
        if l == "Ready" {
            self.log("< Ready");
            if self.state.power == PowerState::On {
                self.log("modem restarted by itself");
                self.unexpected_reset = true;
            }
            self.ready_seen = true;
            return true;
        }
        if let Some(rest) = l.strip_prefix("+CMT:") {
            self.log("< +CMT <header withheld>");
            let f = split_fields(rest);
            let from = f.first().map(|s| unquote(s).to_string()).unwrap_or_default();
            let time = f.get(2).map(|s| unquote(s).to_string()).unwrap_or_default();
            // With AT+CSDH=1 the header carries <fo> as its fifth field.
            let fo: u32 = f.get(4).and_then(|s| s.parse().ok()).unwrap_or(0);
            self.pending_cmt = Some(CmtHeader { from, time, udhi: fo & 0x40 != 0 });
            return true;
        }
        if l.starts_with("#XGNSSNMEA:") {
            if let Some(s) = nmea::parse_urc(l) {
                self.on_nmea(&s);
            }
            return true;
        }
        self.log(&format!("< {l}"));
        if let Some(r) = l.strip_prefix("+CEREG:") {
            self.on_cereg(r);
        } else if let Some(r) = l.strip_prefix("+COPS:") {
            self.on_cops(r);
        } else if let Some(r) = l.strip_prefix("+CESQ:") {
            self.on_cesq(r);
        } else if let Some(r) = l.strip_prefix("+CPIN:") {
            self.on_cpin(r.trim());
        } else if let Some(r) = l.strip_prefix("+CPINR:") {
            let f = split_fields(r);
            self.state.pin_attempts = f.get(1).and_then(|s| s.parse().ok());
        } else if let Some(r) = l.strip_prefix("%XSIM:") {
            let f = split_fields(r);
            self.xsim_init = f.first().map(|s| s == "1");
        } else if let Some(r) = l.strip_prefix("+CFUN:") {
            self.cfun = r.trim().parse().ok();
        } else if let Some(r) = l.strip_prefix("#XSLMVER:") {
            let f = split_fields(r);
            self.state.slm_version = f.first().map(|s| unquote(s).to_string());
        } else if l.starts_with("mfw_") {
            self.state.modem_firmware = Some(l.to_string());
        }
        false
    }

    fn on_cereg(&mut self, rest: &str) {
        let f = split_fields(rest);
        // Read form `<n>,<stat>[,..]` has a numeric second field; the URC
        // form `<stat>[,<tac>,<ci>,<act>]` has none or a quoted one.
        let read_form = f.get(1).map(|s| !s.is_empty() && s.parse::<u32>().is_ok()).unwrap_or(false);
        let (stat_idx, act_idx) = if read_form { (1, 4) } else { (0, 3) };
        let stat: u32 = f.get(stat_idx).and_then(|s| s.parse().ok()).unwrap_or(4);
        let reg = match stat {
            0 => Registration::NotRegistered,
            1 => Registration::RegisteredHome,
            2 => Registration::Searching,
            3 => Registration::Denied,
            5 => Registration::RegisteredRoaming,
            90 => Registration::SimFailure,
            _ => Registration::Unknown,
        };
        if self.state.registration != reg {
            self.state.registration = reg;
            if matches!(reg, Registration::RegisteredHome | Registration::RegisteredRoaming) {
                // The operator and signal changed with it; the caller of
                // poll() refreshes them on its next tick.
                self.state.last_error = None;
            }
        }
        if let Some(a) = f.get(act_idx).and_then(|s| act_name(s)) {
            self.state.rat = Some(a.to_string());
        }
    }

    fn on_cops(&mut self, rest: &str) {
        let f = split_fields(rest);
        if f.len() >= 3 {
            self.state.operator = Some(unquote(&f[2]).to_string());
            if let Some(a) = f.get(3).and_then(|s| act_name(s)) {
                self.state.rat = Some(a.to_string());
            }
        } else {
            self.state.operator = None;
        }
    }

    fn on_cesq(&mut self, rest: &str) {
        let f = split_fields(rest);
        let idx: Option<i32> = f.get(5).and_then(|s| s.parse().ok());
        // 255 means "not known or not detectable"; 0..=97 maps to -140..-44 dBm.
        self.state.rsrp = match idx {
            Some(i) if (0..=97).contains(&i) => Some(i - 140),
            _ => None,
        };
        self.state.bars = bars_for_rsrp(self.state.rsrp);
    }

    fn on_cpin(&mut self, r: &str) {
        self.state.sim = match r {
            "READY" => SimState::Ready,
            "SIM PIN" => SimState::PinRequired,
            "SIM PUK" => SimState::PukRequired,
            _ => SimState::Error,
        };
    }

    fn on_nmea(&mut self, s: &str) {
        match nmea::fix_status(s) {
            Some(true) if self.state.gnss != GnssState::Off => self.state.gnss = GnssState::Fix,
            Some(false) if self.state.gnss != GnssState::Off => self.state.gnss = GnssState::Searching,
            _ => {}
        }
        (self.nmea)(s);
    }

    fn on_sms(&mut self, h: CmtHeader, body: &str) {
        let (concat, text) = if h.udhi {
            match parse_udh(body) {
                Some((c, rest)) => (Some(c), rest),
                None => (None, body),
            }
        } else {
            (None, body)
        };
        for s in self.asm.add(&h.from, &h.time, concat, text, Instant::now()) {
            self.events.push(Event::Sms(s));
        }
    }

    // ----- sequences ------------------------------------------------------

    fn fail_power(&mut self, why: &str) {
        let _ = self.enable.set(false);
        self.state.power = PowerState::Error;
        self.state.last_error = Some(why.to_string());
        self.state.clear_radio();
        self.radio = Radio::Off;
        self.reset_flags();
    }

    fn reset_flags(&mut self) {
        self.cfun = None;
        self.xsim_init = None;
        self.sysmode_gnss_only = false;
        self.cellular_configured = false;
        self.gnss_running = false;
        self.pending_cmt = None;
    }

    /// Decision 3: enable high, wait for the firmware's ready line (or time
    /// out), `AT+CFUN?`, then the requested mode (see `set_radio`).
    pub fn power_on(&mut self) -> Result<(), AtError> {
        self.state.power = PowerState::PoweringOn;
        self.state.last_error = None;
        self.reset_flags();
        self.ready_seen = false;
        self.unexpected_reset = false;
        if let Err(e) = self.enable.set(true) {
            self.fail_power("enable_line");
            return Err(e.into());
        }
        let deadline = Instant::now() + self.timeouts.ready;
        while !self.ready_seen {
            let Some(left) = deadline.checked_duration_since(Instant::now()) else { break };
            match self.link.recv_line(left) {
                Ok(Some(l)) => {
                    if final_result(&l).is_none() {
                        self.absorb(&l);
                    }
                }
                Ok(None) => break,
                Err(e) => {
                    self.fail_power("serial");
                    return Err(e.into());
                }
            }
        }
        if !self.ready_seen {
            self.log("no Ready line in time; probing with AT");
        }
        let mut answered = false;
        for _ in 0..3 {
            match self.exec("AT", self.timeouts.short) {
                Err(AtError::Timeout) => continue,
                Err(AtError::Io(_)) => break,
                _ => {
                    answered = true;
                    break;
                }
            }
        }
        if !answered {
            self.fail_power("no_response");
            return Err(AtError::Timeout);
        }
        self.state.power = PowerState::On;
        self.state.last_error = None;
        // The firmware auto-connects: after power-on it is cellular-capable
        // with system mode 1,1,1,0 and no GNSS session.
        self.radio = Radio::Cellular;
        let t = self.timeouts.short;
        self.soft("AT+CFUN?", t)?;
        let cgmr = self.soft("AT+CGMR", t)?;
        if self.state.modem_firmware.is_none() {
            self.state.modem_firmware = cgmr.into_iter().next();
        }
        self.soft("AT#XSLMVER", t)?;
        Ok(())
    }

    /// Bring the radio to `target` (Off powers the modem down).
    pub fn set_radio(&mut self, target: Radio) -> Result<(), AtError> {
        self.state.cellular = target.cellular();
        self.state.location = target.location();
        if target == Radio::Off {
            return self.power_off();
        }
        if self.radio == Radio::Off {
            self.power_on()?;
        }
        let t = self.timeouts.short;
        let tc = self.timeouts.cfun;

        if self.gnss_running && !target.location() {
            self.soft("AT#XGNSS=0", t)?;
            self.gnss_running = false;
            self.state.gnss = GnssState::Off;
        }

        let want_gnss_only = target == Radio::Gnss;
        if want_gnss_only && !self.sysmode_gnss_only {
            // Vendor GNSS-only recipe (docs/AT_COMMANDS.MD). The system mode
            // can only change in CFUN 0 or 4 (UNVERIFIED on this unit), so
            // go quiet with 4 first; 4 does not write the network context
            // to flash the way 0 does.
            if self.gnss_running {
                self.soft("AT#XGNSS=0", t)?;
                self.gnss_running = false;
            }
            self.soft("AT#XNMEA=1", t)?;
            self.soft("AT+CFUN=4", tc)?;
            self.soft("AT%XSYSTEMMODE=0,0,1,0", t)?;
            self.soft("AT+CFUN=31", tc)?;
            self.sysmode_gnss_only = true;
            self.cellular_configured = false;
            self.state.clear_radio();
        } else if !want_gnss_only && self.sysmode_gnss_only {
            self.soft("AT+CFUN=4", tc)?;
            self.soft("AT%XSYSTEMMODE=1,1,1,0", t)?;
            self.soft("AT+CFUN=1", tc)?;
            self.sysmode_gnss_only = false;
            self.cfun = Some(1);
        }

        if target.cellular() {
            if matches!(self.cfun, Some(0) | Some(4)) {
                self.soft("AT+CFUN=1", tc)?;
                self.cfun = Some(1);
            }
            if !self.cellular_configured {
                // Text mode, full text headers (for concatenation), new
                // messages routed to us as +CMT, registration URCs with
                // location detail. UNVERIFIED: the nRF91 modem firmware may
                // support only PDU mode here; if it answers ERROR the SMS
                // parts stay unavailable and last_error says so.
                match self.exec("AT+CMGF=1", t) {
                    Err(e) if fatal(&e) => return Err(e),
                    Err(_) => self.state.last_error = Some("sms_unavailable".into()),
                    Ok(_) => {}
                }
                self.soft("AT+CSDH=1", t)?;
                self.soft("AT+CNMI=2,2,0,0,0", t)?;
                self.soft("AT+CEREG=5", t)?;
                self.cellular_configured = true;
            }
            self.refresh_sim()?;
            self.refresh_signal()?;
        }

        if target.location() && !self.gnss_running {
            self.soft("AT#XNMEA=1", t)?;
            match self.exec("AT#XGNSS=1,0,0,0", t) {
                Ok(_) => {
                    self.gnss_running = true;
                    self.state.gnss = GnssState::Searching;
                }
                Err(e) if !fatal(&e) => {
                    self.state.gnss = GnssState::Off;
                    self.state.last_error = Some("gnss_start_failed".into());
                }
                Err(e) => return Err(e),
            }
        }
        self.radio = target;
        Ok(())
    }

    /// `AT+CFUN=0`, then the enable line low.
    pub fn power_off(&mut self) -> Result<(), AtError> {
        self.state.power = PowerState::PoweringOff;
        if self.radio != Radio::Off {
            // CFUN=0 stores the network context to flash on the nRF91.
            // That is acceptable for a deliberate power-off; where the radio
            // only needs to go quiet, AT+CFUN=4 is used instead.
            let tc = self.timeouts.cfun;
            if let Err(e) = self.exec("AT+CFUN=0", tc) {
                self.log(&format!("CFUN=0 failed ({e}); cutting power anyway"));
            }
        }
        let r = self.enable.set(false);
        std::thread::sleep(self.timeouts.settle);
        self.state.power = PowerState::Off;
        self.state.clear_radio();
        self.radio = Radio::Off;
        self.reset_flags();
        r.map_err(AtError::from)
    }

    /// Cut power without talking to the modem, wait, and let the caller
    /// bring the radio back with `set_radio`.
    pub fn hard_cycle(&mut self) {
        let _ = self.enable.set(false);
        std::thread::sleep(self.timeouts.settle);
        self.state.power = PowerState::Off;
        self.state.clear_radio();
        self.radio = Radio::Off;
        self.reset_flags();
        self.consecutive_timeouts = 0;
    }

    /// Drive the enable line low without any AT traffic (startup).
    pub fn line_low(&mut self) -> io::Result<()> {
        self.enable.set(false)
    }

    pub fn refresh_sim(&mut self) -> Result<(), AtError> {
        let t = self.timeouts.short;
        self.soft("AT%XSIM?", t)?;
        match self.exec("AT+CPIN?", t) {
            Ok(_) => {}
            Err(e) if fatal(&e) => return Err(e),
            Err(AtError::Cme(c)) => {
                self.state.sim = match c.as_str() {
                    "10" => SimState::Absent,
                    "11" => SimState::PinRequired,
                    "12" => SimState::PukRequired,
                    _ => SimState::Error,
                }
            }
            Err(_) => {
                self.state.sim = if self.xsim_init == Some(false) { SimState::Absent } else { SimState::Error };
            }
        }
        if self.state.sim == SimState::PinRequired {
            self.soft("AT+CPINR=\"SIM PIN\"", t)?;
        } else {
            self.state.pin_attempts = None;
        }
        Ok(())
    }

    pub fn refresh_signal(&mut self) -> Result<(), AtError> {
        let t = self.timeouts.short;
        self.soft("AT+CEREG?", t)?;
        self.soft("AT+COPS?", t)?;
        self.soft("AT+CESQ", t)?;
        Ok(())
    }

    /// Keep-alive for a modem with nothing to report (GNSS only).
    pub fn ping(&mut self) -> Result<(), AtError> {
        let t = self.timeouts.short;
        self.soft("AT", t).map(|_| ())
    }

    /// Send the PIN once. A rejection is reported, never retried.
    pub fn submit_pin(&mut self, pin: &Secret) -> Result<(), AtError> {
        let cmd = format!("AT+CPIN=\"{}\"", pin.expose());
        let t = self.timeouts.short;
        let r = self.exec(&cmd, t);
        drop(cmd);
        match &r {
            Ok(_) => self.state.last_error = None,
            Err(AtError::Cme(c)) if c == "16" => self.state.last_error = Some("pin_rejected".into()),
            Err(e) => self.state.last_error = Some(format!("pin_failed: {e}")),
        }
        if r.as_ref().is_err_and(fatal) {
            return r.map(|_| ());
        }
        self.refresh_sim()?;
        if r.is_ok() {
            self.refresh_signal()?;
        }
        r.map(|_| ())
    }

    /// Text mode send: `AT+CMGS`, the `> ` prompt, the body and Ctrl-Z.
    pub fn send_sms(&mut self, number: &str, body: &str) -> Result<(), AtError> {
        let t = self.timeouts.short;
        self.send_cmd(&format!("AT+CMGS=\"{number}\""))?;
        self.collect(t, true)?;
        let mut payload = body.as_bytes().to_vec();
        payload.push(0x1a);
        self.link.send(&payload)?;
        match self.collect(self.timeouts.cmgs, false) {
            Ok(_) => Ok(()),
            Err(e) => {
                let _ = self.link.send(&[0x1b]);
                Err(e)
            }
        }
    }
}

fn act_name(s: &str) -> Option<&'static str> {
    match s.trim() {
        "7" => Some("LTE-M"),
        "9" => Some("NB-IoT"),
        _ => None,
    }
}
