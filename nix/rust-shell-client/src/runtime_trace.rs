//! Opt-in, bounded numeric profiling. No file I/O while collecting events.
//! Only --serve calls init; fixtures and ordinary sessions stay disabled.
use serde::Serialize;
use std::{fs::{File, OpenOptions}, io::Write, os::unix::fs::OpenOptionsExt,
    sync::{atomic::{AtomicBool, AtomicU64, AtomicU8, Ordering}, Mutex, OnceLock}};

const CAPACITY: usize = 65536;
static NEXT_SPAN: AtomicU64 = AtomicU64::new(1);
thread_local! { static PARENT: std::cell::Cell<u64> = const { std::cell::Cell::new(0) }; }
static ACTIVE: AtomicBool = AtomicBool::new(false);
static TRACE: OnceLock<Mutex<Trace>> = OnceLock::new();

#[derive(Serialize, Clone)]
pub struct Event {
    pub span_id: u64,
    pub parent_span_id: u64,
    pub kind: &'static str,
    pub start_us: u64,
    pub end_us: u64,
    pub cpu_us: u64,
    pub tid: u64,
    pub data: [u64; 6],
}
struct Trace {
    trace_id: String, file: Option<File>, deadline: u64, events: Vec<Event>, dropped: u64,
    /// Counters-only mode keeps no event ring (lowest observer cost).
    counters_only: bool,
    phase_log: Vec<PhaseChange>, phase_log_dropped: u64,
}

/// Fixed attribution table. Names are constants; nothing request-derived is
/// ever a key, so no theme name, path or secret can enter a report. Span kinds
/// are INCLUSIVE of nested spans (render_total contains scene_rebuild).
pub const COUNTED: [&str; 17] = [
    "scene_rebuild", "render_total", "picker_row_repaint", "overlay_draw",
    "thumbnail_request", "thumbnail_completion", "thumbnail_poll", "thumbnail_read_cache",
    "thumbnail_hash", "thumbnail_resolve", "thumbnail_decode",
    "appearance_prepare", "theme_helper_rpc", "theme_request",
    "speculative_admission", "speculative_completion", "overlay_prerender",
];
/// Monotonic gesture phases the Rust loop reports. Coasting and settling are
/// not distinguishable without touching the carousel, so they share MOVING.
pub const PHASE_REST: u8 = 0;
pub const PHASE_HELD: u8 = 1;
pub const PHASE_MOVING: u8 = 2;
pub const PHASES: [&str; 3] = ["rest", "held", "moving"];
const PHASE_LOG_CAPACITY: usize = 1024;
const CELLS: usize = COUNTED.len() * PHASES.len();
static PHASE: AtomicU8 = AtomicU8::new(PHASE_REST);
static COUNT: [AtomicU64; CELLS] = [const { AtomicU64::new(0) }; CELLS];
static WALL_US: [AtomicU64; CELLS] = [const { AtomicU64::new(0) }; CELLS];
static CPU_US: [AtomicU64; CELLS] = [const { AtomicU64::new(0) }; CELLS];
static MAX_WALL_US: [AtomicU64; CELLS] = [const { AtomicU64::new(0) }; CELLS];

#[derive(Serialize, Clone)]
pub struct PhaseChange { pub t_us: u64, pub phase: &'static str }
#[derive(Serialize, Clone, Debug, PartialEq)]
pub struct Counter { pub kind: &'static str, pub phase: &'static str, pub count: u64,
    pub wall_us: u64, pub cpu_us: u64, pub max_wall_us: u64 }

fn cell(kind: &str) -> Option<usize> {
    let k = COUNTED.iter().position(|name| *name == kind)?;
    Some(k * PHASES.len() + PHASE.load(Ordering::Relaxed).min(PHASES.len() as u8 - 1) as usize)
}
fn accumulate(kind: &str, wall_us: u64, cpu_us: u64) {
    let Some(i) = cell(kind) else { return; };
    COUNT[i].fetch_add(1, Ordering::Relaxed);
    WALL_US[i].fetch_add(wall_us, Ordering::Relaxed);
    CPU_US[i].fetch_add(cpu_us, Ordering::Relaxed);
    MAX_WALL_US[i].fetch_max(wall_us, Ordering::Relaxed);
}
/// Non-zero cells only; wall and thread-CPU time are separate fields.
pub fn counters() -> Vec<Counter> {
    let mut out = Vec::new();
    for (k, kind) in COUNTED.iter().enumerate() {
        for (p, phase) in PHASES.iter().enumerate() {
            let i = k * PHASES.len() + p;
            let count = COUNT[i].load(Ordering::Relaxed);
            if count != 0 {
                out.push(Counter { kind, phase, count, wall_us: WALL_US[i].load(Ordering::Relaxed),
                    cpu_us: CPU_US[i].load(Ordering::Relaxed), max_wall_us: MAX_WALL_US[i].load(Ordering::Relaxed) });
            }
        }
    }
    out
}
/// Report the current gesture phase; only changes are logged (bounded).
pub fn set_phase(phase: u8) {
    if !active() { return; }
    let phase = phase.min(PHASES.len() as u8 - 1);
    if PHASE.swap(phase, Ordering::Relaxed) == phase { return; }
    let t_us = now_us();
    if let Some(trace) = TRACE.get() {
        if let Ok(mut trace) = trace.lock() {
            if trace.phase_log.len() < PHASE_LOG_CAPACITY {
                trace.phase_log.push(PhaseChange { t_us, phase: PHASES[phase as usize] });
            } else { trace.phase_log_dropped = trace.phase_log_dropped.saturating_add(1); }
        }
    }
}

fn clock_us(clock: libc::clockid_t) -> u64 {
    let mut ts = libc::timespec { tv_sec: 0, tv_nsec: 0 };
    if unsafe { libc::clock_gettime(clock, &mut ts) } != 0 { return 0; }
    ts.tv_sec as u64 * 1_000_000 + ts.tv_nsec as u64 / 1000
}
pub fn now_us() -> u64 { clock_us(libc::CLOCK_MONOTONIC) }
fn thread_us() -> u64 { clock_us(libc::CLOCK_THREAD_CPUTIME_ID) }
fn tid() -> u64 { unsafe { libc::syscall(libc::SYS_gettid) as u64 } }
pub fn active() -> bool { ACTIVE.load(Ordering::Relaxed) }

pub fn init() -> Result<(), String> {
    let Some(path) = std::env::var_os("K230_TRACE_PATH") else { return Ok(()); };
    let seconds = std::env::var("K230_TRACE_SECONDS").unwrap_or_else(|_| "120".into())
        .parse::<u64>().map_err(|_| "invalid picker trace duration")?;
    if !(10..=180).contains(&seconds) { return Err("picker trace duration must be 10..180 seconds".into()); }
    let trace_id = std::env::var("K230_TRACE_ID")
        .unwrap_or_else(|_| format!("{:016x}{:016x}", std::process::id(), now_us())).to_ascii_lowercase();
    if trace_id.len() != 32 || !trace_id.bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err("trace ID must be 32 hexadecimal digits".into());
    }
    let file = OpenOptions::new().write(true).create_new(true).mode(0o600)
        .custom_flags(libc::O_NOFOLLOW).open(path).map_err(|e| e.to_string())?;
    let counters_only = std::env::var("K230_TRACE_COUNTERS_ONLY").is_ok_and(|v| v == "1");
    TRACE.set(Mutex::new(Trace { trace_id, file: Some(file), deadline: now_us() + seconds * 1_000_000,
        events: Vec::with_capacity(if counters_only { 0 } else { CAPACITY }), dropped: 0,
        counters_only, phase_log: Vec::with_capacity(PHASE_LOG_CAPACITY), phase_log_dropped: 0 })).map_err(|_| "trace already initialized")?;
    ACTIVE.store(true, Ordering::Relaxed);
    event("trace_start", [seconds, CAPACITY as u64, counters_only as u64, 0, 0, 0]);
    Ok(())
}
fn append(trace: &mut Trace, event: Event) {
    if trace.counters_only { return; }
    if trace.events.len() < CAPACITY { trace.events.push(event); }
    else { trace.dropped = trace.dropped.saturating_add(1); }
}
fn record(event: Event) {
    if !active() { return; }
    if let Some(trace) = TRACE.get() {
        if let Ok(mut trace) = trace.lock() {
            if active() { append(&mut trace, event); }
        }
    }
}
pub fn event(kind: &'static str, data: [u64; 6]) {
    if !active() { return; }
    let now = now_us();
    accumulate(kind, 0, 0);
    record(Event { span_id: 0, parent_span_id: PARENT.with(|p| p.get()), kind, start_us: now, end_us: now, cpu_us: 0, tid: tid(), data });
}
/// Only fixed hexadecimal correlation identifiers cross the helper boundary.
pub fn context() -> Option<serde_json::Value> {
    if !active() { return None; }
    let trace = TRACE.get()?.lock().ok()?;
    Some(serde_json::json!({"trace_id": trace.trace_id,
        "parent_span_id": format!("{:016x}", PARENT.with(|p| p.get()))}))
}
pub struct Span { _thread_bound: std::marker::PhantomData<std::rc::Rc<()>>, id: u64, parent: u64, kind: &'static str, start: u64, cpu: u64 }
impl Span {
    pub fn new(kind: &'static str) -> Self {
        if active() {
            let id = ((std::process::id() as u64) << 32) | NEXT_SPAN.fetch_add(1, Ordering::Relaxed);
            let parent = PARENT.with(|p| p.replace(id));
            Self { _thread_bound: std::marker::PhantomData, id, parent, kind, start: now_us(), cpu: thread_us() }
        } else { Self { _thread_bound: std::marker::PhantomData, id: 0, parent: 0, kind, start: 0, cpu: 0 } }
    }
}
impl Drop for Span {
    fn drop(&mut self) {
        if self.id != 0 { PARENT.with(|p| p.set(self.parent)); }
        if self.start != 0 && active() {
            let end = now_us();
            let cpu = thread_us().saturating_sub(self.cpu);
            accumulate(self.kind, end.saturating_sub(self.start), cpu);
            record(Event { span_id: self.id, parent_span_id: self.parent, kind: self.kind, start_us: self.start, end_us: end,
                cpu_us: cpu, tid: tid(), data: [0; 6] });
        }
    }
}
/// Called between event-loop iterations. Serialization happens once, AFTER the
/// bounded observation window; it must not be included in measured gestures.
pub fn finish_if_due() -> Result<(), String> {
    if !active() { return Ok(()); }
    let Some(trace) = TRACE.get() else { return Ok(()); };
    let mut trace = trace.lock().map_err(|_| "trace lock poisoned")?;
    let now = now_us();
    if now < trace.deadline { return Ok(()); }
    ACTIVE.store(false, Ordering::Relaxed);
    let events = std::mem::take(&mut trace.events);
    let dropped = trace.dropped;
    let deadline = trace.deadline;
    let trace_id = trace.trace_id.clone();
    let (counters_only, phase_log, phase_log_dropped) =
        (trace.counters_only, std::mem::take(&mut trace.phase_log), trace.phase_log_dropped);
    let Some(mut file) = trace.file.take() else { return Ok(()); };
    drop(trace);
    #[derive(Serialize)]
    struct Report { schema: u32, clock: &'static str, trace_id: String, pid: u32,
        capacity: usize, deadline_us: u64, finished_us: u64, dropped: u64, events: Vec<Event>,
        counters_only: bool, counters: Vec<Counter>, phase_log: Vec<PhaseChange>, phase_log_dropped: u64 }
    let report = Report { schema: 1, clock: "CLOCK_MONOTONIC", trace_id,
        pid: std::process::id(), capacity: CAPACITY, deadline_us: deadline,
        finished_us: now, dropped, events,
        counters_only, counters: counters(), phase_log, phase_log_dropped };
    serde_json::to_writer(&mut file, &report).map_err(|e| e.to_string())?;
    file.write_all(b"\n").map_err(|e| e.to_string())?;
    file.flush().map_err(|e| e.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn theme_picker_trace_bounds_memory_and_reports_overflow() {
        let mut trace = Trace { trace_id: "fixture".into(), file: None, deadline: 0, events: Vec::new(), dropped: 0,
            counters_only: false, phase_log: Vec::new(), phase_log_dropped: 0 };
        let e = Event { span_id: 0, parent_span_id: 0, kind: "fixture", start_us: 1, end_us: 2, cpu_us: 1, tid: 1, data: [0; 6] };
        for _ in 0..CAPACITY+3 { append(&mut trace, e.clone()); }
        assert_eq!(trace.events.len(), CAPACITY);
        assert_eq!(trace.dropped, 3);
    }
    #[test]
    fn theme_picker_trace_span_is_noop_when_disabled() {
        assert!(!active());
        let span = Span::new("fixture");
        assert_eq!(span.start, 0);
    }
    #[test]
    fn theme_picker_counters_are_fixed_name_bounded_and_split_by_phase() {
        assert!(COUNTED.len() * PHASES.len() == CELLS && CELLS < 128);
        assert!(COUNTED.iter().all(|k| k.bytes().all(|b| b.is_ascii_lowercase() || b == b'_')));
        // Unknown kinds (anything request-derived) are never keyed.
        assert!(cell("not_a_counted_kind").is_none());
        // Distinct statics per test run: read deltas, tests may run in parallel.
        let before = counters();
        let get = |v: &[Counter], k: &str, p: &str| v.iter().find(|c| c.kind == k && c.phase == p)
            .map_or((0, 0, 0, 0), |c| (c.count, c.wall_us, c.cpu_us, c.max_wall_us));
        PHASE.store(PHASE_HELD, Ordering::Relaxed);
        accumulate("scene_rebuild", 900, 400);
        accumulate("scene_rebuild", 100, 100);
        PHASE.store(PHASE_MOVING, Ordering::Relaxed);
        accumulate("scene_rebuild", 50, 10);
        accumulate("unknown", 1, 1);
        PHASE.store(PHASE_REST, Ordering::Relaxed);
        let after = counters();
        let d = |k, p| { let (a, b) = (get(&after, k, p), get(&before, k, p)); (a.0 - b.0, a.1 - b.1, a.2 - b.2) };
        assert_eq!(d("scene_rebuild", "held"), (2, 1000, 500));
        assert_eq!(d("scene_rebuild", "moving"), (1, 50, 10));
        assert!(get(&after, "scene_rebuild", "held").3 >= 900); // wall max kept apart from CPU
    }
    #[test]
    fn theme_picker_phase_changes_are_inert_when_disabled() {
        assert!(!active());
        let before = PHASE.load(Ordering::Relaxed);
        set_phase(PHASE_HELD); // inactive: must not change state or touch the log
        assert_eq!(PHASE.load(Ordering::Relaxed), before);
        assert!(TRACE.get().is_none());
    }
}
