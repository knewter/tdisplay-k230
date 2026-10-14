//! Transcript tests (task 3.1 proof). The "no SIM" transcript is the probe
//! log recorded on the board (docs/evidence/nrf9151/probe/). Every other
//! transcript is SYNTHETIC: built from the documented Nordic Serial LTE
//! Modem, 3GPP TS 27.007 and TS 27.005 formats, not recorded from hardware.
//! All numbers, PINs and coordinates are obviously fake.

use k230_modem::at::{AtError, Secret};
use k230_modem::engine::{Event, Modem, Radio, Timeouts};
use k230_modem::fake::{from_transcript, Handle};
use k230_modem::nmea::with_checksum;
use k230_modem::state::{GnssState, PowerState, Registration, SimState};
use std::cell::RefCell;
use std::rc::Rc;
use std::time::Duration;

struct Rig {
    modem: Modem,
    h: Handle,
    log: Rc<RefCell<Vec<String>>>,
    nmea: Rc<RefCell<Vec<String>>>,
}

fn rig(transcript: &str) -> Rig {
    let (link, en, h) = from_transcript(transcript);
    let log = Rc::new(RefCell::new(Vec::new()));
    let nmea = Rc::new(RefCell::new(Vec::new()));
    let (l, n) = (log.clone(), nmea.clone());
    let t = Timeouts { settle: Duration::ZERO, ..Timeouts::default() };
    let modem = Modem::new(
        Box::new(link),
        Box::new(en),
        Box::new(move |m| l.borrow_mut().push(m.to_string())),
        Box::new(move |s| n.borrow_mut().push(s.to_string())),
        t,
    );
    Rig { modem, h, log, nmea }
}

const POWER_ON: &str = "
< Ready
< +CEREG: 90
> AT
< OK
> AT+CFUN?
< +CFUN: 1
< OK
> AT+CGMR
< mfw_nrf91x1_2.0.3
< OK
> AT#XSLMVER
< #XSLMVER: \"2.9.0\",\"2.9.0-cellular-a52f6a06a9e4\"
< OK
";

const CELLULAR_SETUP: &str = "
> AT+CMGF=1
< OK
> AT+CSDH=1
< OK
> AT+CNMI=2,2,0,0,0
< OK
> AT+CEREG=5
< OK
";

fn json(r: &Rig) -> String {
    r.modem.state.to_json()
}

fn everything(r: &Rig) -> String {
    format!("{}\n{}\n{}", r.log.borrow().join("\n"), json(r), r.h.sent().join("\n").replace("AT+CPIN=\"", "AT+CPIN=<sent>\""))
}

// ---- no SIM: the lines are the probe log on the board (2026-10-13) --------

#[test]
fn no_sim_recorded_on_the_board() {
    let t = format!(
        "{POWER_ON}{CELLULAR_SETUP}
> AT%XSIM?
< %XSIM: 0,9
< OK
> AT+CPIN?
< ERROR
> AT+CEREG?
< +CEREG: 5,90
< OK
> AT+COPS?
< +COPS: 0
< OK
> AT+CESQ
< +CESQ: 99,99,255,255,255,255
< OK
"
    );
    let mut r = rig(&t);
    r.modem.set_radio(Radio::Cellular).unwrap();
    assert!(r.h.script_done());
    let s = &r.modem.state;
    assert_eq!(s.power, PowerState::On);
    assert!(s.present);
    assert_eq!(s.sim, SimState::Absent);
    assert_eq!(s.registration, Registration::SimFailure);
    assert_eq!(s.operator, None);
    assert_eq!(s.rsrp, None);
    assert_eq!(s.bars, 0);
    assert_eq!(s.modem_firmware.as_deref(), Some("mfw_nrf91x1_2.0.3"));
    assert_eq!(s.slm_version.as_deref(), Some("2.9.0"));
    assert_eq!(r.h.enable_history(), vec![true]);
}

// ---- SYNTHETIC from here on -------------------------------------------------

const PIN_REQUIRED: &str = "
> AT%XSIM?
< %XSIM: 1,0
< OK
> AT+CPIN?
< +CPIN: SIM PIN
< OK
> AT+CPINR=\"SIM PIN\"
< +CPINR: \"SIM PIN\",3,3
< OK
> AT+CEREG?
< +CEREG: 5,0
< OK
> AT+COPS?
< +COPS: 0
< OK
> AT+CESQ
< +CESQ: 99,99,255,255,255,255
< OK
";

#[test]
fn pin_required() {
    let mut r = rig(&format!("{POWER_ON}{CELLULAR_SETUP}{PIN_REQUIRED}"));
    r.modem.set_radio(Radio::Cellular).unwrap();
    assert!(r.h.script_done());
    assert_eq!(r.modem.state.sim, SimState::PinRequired);
    assert_eq!(r.modem.state.pin_attempts, Some(3));
    assert_eq!(r.modem.state.registration, Registration::NotRegistered);
}

const PIN: &str = "4829";

#[test]
fn wrong_pin_is_reported_once_and_not_retried() {
    let t = format!(
        "{POWER_ON}{CELLULAR_SETUP}{PIN_REQUIRED}
> AT+CPIN=\"{PIN}\"
< +CME ERROR: 16
> AT%XSIM?
< %XSIM: 1,0
< OK
> AT+CPIN?
< +CPIN: SIM PIN
< OK
> AT+CPINR=\"SIM PIN\"
< +CPINR: \"SIM PIN\",2,3
< OK
"
    );
    let mut r = rig(&t);
    r.modem.set_radio(Radio::Cellular).unwrap();
    let err = r.modem.submit_pin(&Secret::new(PIN.into())).unwrap_err();
    assert_eq!(err, AtError::Cme("16".into()));
    assert!(r.h.script_done(), "exactly one AT+CPIN= was sent");
    assert_eq!(r.modem.state.sim, SimState::PinRequired);
    assert_eq!(r.modem.state.pin_attempts, Some(2));
    assert_eq!(r.modem.state.last_error.as_deref(), Some("pin_rejected"));
    // The PIN reached the modem (the fake saw it) but nowhere else.
    assert!(r.h.sent().iter().any(|c| c.contains(PIN)));
    assert!(!r.log.borrow().iter().any(|l| l.contains(PIN)), "PIN in the log");
    assert!(!json(&r).contains(PIN), "PIN in the state");
    assert!(r.log.borrow().iter().any(|l| l == "> AT+CPIN=<redacted>"));
}

#[test]
fn accepted_pin_never_appears_in_any_log_or_state_output() {
    let t = format!(
        "{POWER_ON}{CELLULAR_SETUP}{PIN_REQUIRED}
> AT+CPIN=\"{PIN}\"
< OK
> AT%XSIM?
< %XSIM: 1,0
< OK
> AT+CPIN?
< +CPIN: READY
< OK
> AT+CEREG?
< +CEREG: 5,1,\"1A2B\",\"01234567\",7
< OK
> AT+COPS?
< +COPS: 0,0,\"Test Net\",7
< OK
> AT+CESQ
< +CESQ: 99,99,255,255,255,60
< OK
"
    );
    let mut r = rig(&t);
    r.modem.set_radio(Radio::Cellular).unwrap();
    r.modem.submit_pin(&Secret::new(PIN.into())).unwrap();
    assert!(r.h.script_done());
    assert_eq!(r.modem.state.sim, SimState::Ready);
    assert_eq!(r.modem.state.last_error, None);
    let mut seen = r.log.borrow().join("\n");
    seen.push_str(&json(&r));
    seen.push_str(&format!("{:?}", Secret::new(PIN.into())));
    assert!(!seen.contains(PIN), "PIN leaked: {seen}");
}

#[test]
fn registered() {
    let t = format!(
        "{POWER_ON}{CELLULAR_SETUP}
> AT%XSIM?
< %XSIM: 1,0
< OK
> AT+CPIN?
< +CPIN: READY
< OK
> AT+CEREG?
< +CEREG: 5,1,\"1A2B\",\"01234567\",9
< OK
> AT+COPS?
< +COPS: 0,0,\"Test Net\",9
< OK
> AT+CESQ
< +CESQ: 99,99,255,255,255,50
< OK
"
    );
    let mut r = rig(&t);
    r.modem.set_radio(Radio::Cellular).unwrap();
    let s = &r.modem.state;
    assert_eq!(s.sim, SimState::Ready);
    assert_eq!(s.registration, Registration::RegisteredHome);
    assert_eq!(s.operator.as_deref(), Some("Test Net"));
    assert_eq!(s.rat.as_deref(), Some("NB-IoT"));
    assert_eq!(s.rsrp, Some(-90));
    assert_eq!(s.bars, 4);
}

#[test]
fn a_registration_urc_between_commands_updates_state() {
    let mut r = rig("
< +CEREG: 1,\"1A2B\",\"01234567\",7
");
    r.modem.poll(Duration::from_millis(1)).unwrap();
    assert_eq!(r.modem.state.registration, Registration::RegisteredHome);
    assert_eq!(r.modem.state.rat.as_deref(), Some("LTE-M"));
}

#[test]
fn a_timeout_is_an_error_and_counts_toward_recovery() {
    let t = "
> AT
!
";
    let mut r = rig(t);
    assert_eq!(r.modem.exec("AT", Duration::from_secs(5)), Err(AtError::Timeout));
    assert_eq!(r.modem.consecutive_timeouts, 1);
    assert_eq!(r.modem.state.last_error.as_deref(), Some("timeout: AT"));
}

#[test]
fn an_sms_prompt_that_never_comes_is_cancelled_with_esc() {
    // Left alone, a modem still waiting for a body would swallow the next
    // commands as message text.
    let mut r = rig("
> AT+CMGS=\"+15555550100\"
!
>> ^[
");
    assert_eq!(r.modem.send_sms("+15555550100", "hi"), Err(AtError::Timeout));
    assert!(r.h.script_done());
}

#[test]
fn power_on_that_never_answers_cuts_the_power_again() {
    // No Ready, and three silent probes.
    let mut r = rig("
> AT
!
> AT
!
> AT
!
");
    assert_eq!(r.modem.set_radio(Radio::Cellular), Err(AtError::Timeout));
    assert_eq!(r.modem.state.power, PowerState::Error);
    assert_eq!(r.modem.state.last_error.as_deref(), Some("no_response"));
    assert_eq!(r.h.enable_history(), vec![true, false]);
    assert!(r.h.script_done());
}

#[test]
fn power_off_sends_cfun_0_then_drops_the_line() {
    let t = format!(
        "{POWER_ON}
> AT+CFUN=0
< OK
"
    );
    let mut r = rig(&t);
    r.modem.power_on().unwrap();
    r.modem.set_radio(Radio::Off).unwrap();
    assert!(r.h.script_done());
    assert_eq!(r.h.enable_history(), vec![true, false]);
    assert_eq!(r.modem.state.power, PowerState::Off);
    assert_eq!(r.modem.state.sim, SimState::Unknown);
}

#[test]
fn inbound_sms_is_stored_and_kept_out_of_the_log() {
    let mut r = rig("
< +CMT: \"+15555550100\",,\"26/10/13,12:00:00+00\",145,4,0,0,\"+15555550999\",145,11
< test string
");
    r.modem.poll(Duration::from_millis(1)).unwrap();
    r.modem.poll(Duration::from_millis(1)).unwrap();
    assert_eq!(r.modem.events.len(), 1);
    let Event::Sms(s) = &r.modem.events[0];
    assert_eq!((s.from.as_str(), s.body.as_str(), s.parts), ("+15555550100", "test string", 1));
    assert_eq!(s.time, "26/10/13,12:00:00+00");
    let log = r.log.borrow().join("\n");
    assert!(!log.contains("+15555550100") && !log.contains("test string"), "{log}");
}

#[test]
fn multipart_sms_is_joined_in_order() {
    let mut r = rig("
< +CMT: \"+15555550100\",,\"26/10/13,12:00:05+00\",145,68,0,0,\"+15555550999\",145,22
< 050003A70202world
< +CMT: \"+15555550100\",,\"26/10/13,12:00:04+00\",145,68,0,0,\"+15555550999\",145,22
< 050003A70201Hello 
");
    for _ in 0..4 {
        r.modem.poll(Duration::from_millis(1)).unwrap();
    }
    assert_eq!(r.modem.events.len(), 1);
    let Event::Sms(s) = &r.modem.events[0];
    assert_eq!(s.body, "Hello world");
    assert_eq!(s.parts, 2);
}

#[test]
fn a_message_without_a_usable_header_is_kept_as_it_came() {
    let mut r = rig("
< +CMT: \"+15555550100\",,\"26/10/13,12:00:00+00\",145,64,0,0,\"+15555550999\",145,9
< 9999zzzz
");
    for _ in 0..2 {
        r.modem.poll(Duration::from_millis(1)).unwrap();
    }
    let Event::Sms(s) = &r.modem.events[0];
    assert_eq!(s.body, "9999zzzz");
}

#[test]
fn sending_an_sms_uses_the_prompt_and_ctrl_z() {
    let t = format!(
        "{POWER_ON}{CELLULAR_SETUP}
> AT%XSIM?
< OK
> AT+CPIN?
< +CPIN: READY
< OK
> AT+CEREG?
< OK
> AT+COPS?
< OK
> AT+CESQ
< OK
> AT+CMGS=\"+15555550100\"
< > 
>> test string^Z
< +CMGS: 7
< OK
"
    );
    let mut r = rig(&t);
    r.modem.set_radio(Radio::Cellular).unwrap();
    r.modem.send_sms("+15555550100", "test string").unwrap();
    assert!(r.h.script_done());
    let log = r.log.borrow().join("\n");
    assert!(log.contains("> AT+CMGS=<redacted>"));
    assert!(!log.contains("+15555550100") && !log.contains("test string"), "{log}");
}

#[test]
fn a_failed_send_aborts_the_prompt_with_escape() {
    let t = format!(
        "{POWER_ON}
> AT+CMGS=\"+15555550100\"
< > 
>> hi^Z
< +CMS ERROR: 330
>> ^[
"
    );
    let mut r = rig(&t);
    r.modem.power_on().unwrap();
    assert_eq!(r.modem.send_sms("+15555550100", "hi"), Err(AtError::Cms("330".into())));
    assert!(r.h.script_done(), "Esc was sent to leave the prompt");
}

#[test]
fn nmea_burst_goes_to_the_pty_and_sets_the_gnss_state() {
    let gga0 = with_checksum("GPGGA,000000.00,0100.0000,N,00100.0000,E,0,00,99.9,0.0,M,,M,,");
    let gga1 = with_checksum("GPGGA,000001.00,0100.0000,N,00100.0000,E,1,06,1.2,0.0,M,,M,,");
    let gsv = with_checksum("GPGSV,1,1,02,01,00,000,30,02,00,000,31");
    let rmc = with_checksum("GNRMC,000001.00,A,0100.0000,N,00100.0000,E,0.0,0.0,010100,,,A");
    let t = format!(
        "{POWER_ON}
> AT#XGNSS=0
< OK
> AT#XNMEA=1
< OK
> AT+CFUN=4
< OK
> AT%XSYSTEMMODE=0,0,1,0
< OK
> AT+CFUN=31
< OK
> AT#XNMEA=1
< OK
> AT#XGNSS=1,0,0,0
< OK
< #XGNSSNMEA: {gga0}
< #XGNSSNMEA: {gsv}
< #XGNSSNMEA: \"{gga1}\"
< #XGNSSNMEA: {rmc}
< #XGNSSNMEA: $GPGGA,garbled*00
"
    )
    .replace("> AT#XGNSS=0\n< OK\n", "");
    let mut r = rig(&t);
    r.modem.set_radio(Radio::Gnss).unwrap();
    assert!(r.h.script_done());
    assert_eq!(r.modem.state.gnss, GnssState::Searching);
    assert_eq!(r.modem.state.sim, SimState::Unknown, "no cellular fields in GNSS-only");
    for _ in 0..5 {
        r.modem.poll(Duration::from_millis(1)).unwrap();
        if r.nmea.borrow().len() == 1 {
            assert_eq!(r.modem.state.gnss, GnssState::Searching);
        }
    }
    assert_eq!(*r.nmea.borrow(), vec![gga0, gsv, gga1, rmc], "bad checksum dropped, quotes stripped");
    assert_eq!(r.modem.state.gnss, GnssState::Fix);
    let log = r.log.borrow().join("\n");
    assert!(!log.contains("GPGGA") && !log.contains("0100.0000"), "positions must not be logged");
    assert!(!json(&r).contains("0100.0000"));
}

#[test]
fn turning_location_off_stops_gnss_and_powers_down() {
    let t = format!(
        "{POWER_ON}
> AT#XNMEA=1
< OK
> AT+CFUN=4
< OK
> AT%XSYSTEMMODE=0,0,1,0
< OK
> AT+CFUN=31
< OK
> AT#XNMEA=1
< OK
> AT#XGNSS=1,0,0,0
< OK
> AT+CFUN=0
< OK
"
    );
    let mut r = rig(&t);
    r.modem.set_radio(Radio::Gnss).unwrap();
    r.modem.set_radio(Radio::Off).unwrap();
    assert!(r.h.script_done());
    assert_eq!(r.modem.state.gnss, GnssState::Off);
    assert_eq!(r.h.enable_history(), vec![true, false]);
}

#[test]
fn unexpected_ready_while_on_flags_a_restart() {
    let t = POWER_ON.to_string();
    let mut r = rig(&t);
    r.modem.power_on().unwrap();
    r.h.push_rx("Ready");
    r.modem.poll(Duration::from_millis(1)).unwrap();
    assert!(r.modem.take_unexpected_reset());
    assert!(!r.modem.take_unexpected_reset());
}

#[test]
fn nothing_the_service_logs_carries_a_secret_or_a_number_in_any_scenario() {
    // The no-SIM and registered paths log; neither may carry the fake PIN
    // or the fake number from the other fixtures.
    let mut r = rig(&format!("{POWER_ON}{CELLULAR_SETUP}{PIN_REQUIRED}"));
    r.modem.set_radio(Radio::Cellular).unwrap();
    let all = everything(&r);
    assert!(!all.contains(PIN) && !all.contains("+1555"));
}
