//! The nRF9151 modem service for the K230 handheld.
//!
//! Layout: `at` (framing, redaction), `engine` (the AT state machine),
//! `sms`, `nmea`, `state`, `settings`, `control` (the socket protocol),
//! `recovery`, and the Linux plumbing `gpio`, `serial` and `pty`. `fake`
//! is a scripted link for the transcript tests.

pub mod at;
pub mod control;
pub mod engine;
pub mod fake;
pub mod gpio;
pub mod nmea;
pub mod pty;
pub mod recovery;
pub mod serial;
pub mod settings;
pub mod sms;
pub mod state;
