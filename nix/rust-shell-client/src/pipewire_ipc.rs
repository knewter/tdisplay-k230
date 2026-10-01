//! PipeWire-facing plumbing for the volume UX: parsing `pw-dump`/
//! `pw-dump --monitor` JSON into the sinks/streams/default-sink this
//! shell actually needs, and the two long-lived child processes that
//! replace one-shot `wpctl`/`pactl` calls per change.
//!
//! Why a persistent process rather than a crate or a hand-rolled native
//! protocol client: `sway_ipc.rs` hand-rolls Sway's own tiny, stable,
//! single-purpose `i3-ipc` framing because that wire format is genuinely
//! small (a 14-byte header, one JSON payload) and undocumented outside
//! `sway-ipc(7)`. PipeWire's own native protocol is a much larger binary
//! RPC (fds, SPA pods, an object/permission model) with no stable public
//! wire-format spec this shell could hand-roll as cheaply, and there is
//! no `pipewire-rs`-equivalent dependency already vetted for this repo's
//! RISC-V cross toolchain (`nix/rust-shell-client/Cargo.toml` pins a
//! short, deliberately narrow dependency list). `pw-dump`/`pw-cli` are
//! already present the moment `services.pipewire.enable` ships
//! (`nix/pipewire.nix`), so this reuses binaries the system already
//! needs, at the cost of one parsing layer instead of an FFI binding.
//!
//! Cost: both processes are spawned exactly once (`main.rs`'s own
//! startup, not per change) and then sit blocked in a `read()`/`recv()`
//! most of the time -- `pw-dump --monitor` wakes only when the graph
//! actually changes (event-driven, not polling), and the `pw-cli`
//! writer only wakes when this shell's own throttled slider write or a
//! rare device-picker action sends it a line. That is far cheaper than
//! `wpctl set-volume` per drag sample: a fresh `wpctl` process pays
//! dynamic-linking, a new PipeWire client connection/handshake, and
//! process teardown on every single sample, all avoided here.
use std::{
    io::{self, Read, Write},
    path::PathBuf,
    process::{Child, ChildStdin, Command, Stdio},
    sync::mpsc::{self, Receiver, SyncSender, TrySendError},
    thread,
};

use serde_json::Value;

/// One PipeWire sink this shell can show in the device picker/expanded
/// panel. `linear_volume` is the raw `Props.channelVolumes` average
/// (0.0-1.0); callers map it through `volume::linear_to_percent` for
/// display, never storing a percent here (a percent is a UI-side
/// derived value, not graph state).
#[derive(Clone, Debug, PartialEq)]
pub struct Sink {
    pub id: u32,
    pub name: String,
    pub description: String,
    pub linear_volume: f64,
    pub muted: bool,
    pub is_default: bool,
    /// ALSA device route controls the hardware mixer, when present.
    pub route: Option<(u32, u32, u32)>,
}

/// One stream node (a sink-input in PulseAudio terms; PipeWire calls it
/// a `Stream/Output/Audio` node) -- one row in the expanded panel's
/// per-app volume list.
#[derive(Clone, Debug, PartialEq)]
pub struct Stream {
    pub id: u32,
    pub app_name: String,
    pub app_icon: Option<String>,
    pub linear_volume: f64,
    pub muted: bool,
}

#[derive(Clone, Debug, PartialEq, Default)]
pub struct GraphSnapshot {
    pub sinks: Vec<Sink>,
    pub streams: Vec<Stream>,
}

/// One row of the HUD's expanded panel/the Settings device picker --
/// either a per-app stream or a selectable output sink. Streams are
/// listed before sinks (`expanded_row`'s own order): the task's own
/// wording lists per-stream volumes before the device picker, and it
/// keeps the common case (adjusting the one app currently making sound)
/// above the less-frequent one (switching output device).
pub enum ExpandedRow<'a> {
    Stream(&'a Stream),
    Sink(&'a Sink),
}

impl GraphSnapshot {
    /// How many expanded-panel rows this snapshot has right now --
    /// `volume::hud_geometry`'s own `expanded_row_count` input, so the
    /// pill's height and its row hit-testing always agree with what
    /// `expanded_row` below actually iterates.
    pub fn expanded_row_count(&self) -> usize {
        self.streams.len() + self.sinks.len()
    }

    /// The row at `index` (0-based, streams first, then sinks), or
    /// `None` past the end -- the single place both `render.rs`'s paint
    /// and `main.rs`'s touch dispatch resolve a
    /// `volume::HudGeometry::expanded_row_at` index against real data,
    /// so the two can never disagree about which row is which.
    pub fn expanded_row(&self, index: usize) -> Option<ExpandedRow<'_>> {
        if let Some(stream) = self.streams.get(index) {
            return Some(ExpandedRow::Stream(stream));
        }
        self.sinks
            .get(index - self.streams.len())
            .map(ExpandedRow::Sink)
    }
}

/// `pw-dump`'s response cap. A real graph on this board's single sink
/// plus a handful of app streams is tiny; this is only a sanity bound
/// against a runaway/garbled child, mirroring `wifi_settings.rs`'s own
/// `RESPONSE_LIMIT` convention.
const DUMP_LIMIT: usize = 4 * 1024 * 1024;

fn props_volume(params: &Value) -> (f64, bool) {
    let Some(props_list) = params.get("Props").and_then(Value::as_array) else {
        return (1.0, false);
    };
    let Some(props) = props_list.first() else {
        return (1.0, false);
    };
    let linear = props
        .get("channelVolumes")
        .and_then(Value::as_array)
        .filter(|channels| !channels.is_empty())
        .map(|channels| {
            let sum: f64 = channels.iter().filter_map(Value::as_f64).sum();
            sum / channels.len() as f64
        })
        .unwrap_or(1.0);
    let muted = props.get("mute").and_then(Value::as_bool).unwrap_or(false);
    (linear, muted)
}

/// Accumulates `pw-dump --monitor`'s own per-change arrays into the
/// current, complete graph state.
///
/// This is necessary, not merely defensive: PipeWire's own `pw-dump.c`
/// (`src/tools/pw-dump.c`, read directly from the upstream source),
/// `dump_objects()`, walks its *entire* known object list on every dump
/// but explicitly `continue`s past any object whose internal `changed`
/// counter is zero, resetting the counter to zero for whatever it does
/// emit. In monitor mode this runs again on every graph change, which
/// means each printed JSON array holds only the objects that changed
/// since the previous array -- never a full re-dump of the graph. An
/// earlier version of this module read each array as if it were a
/// complete, standalone snapshot; that silently dropped every sink and
/// stream the triggering change did not itself touch (e.g. one node's
/// volume changing would make every *other* node vanish from the shown
/// state on that update). Removal has its own shape too:
/// `registry_event_global_remove` emits `{"id": <id>, "info": null}` for
/// an object that had a dump class (every `Node` does) -- checked here
/// the same way `apply_array` checks it.
#[derive(Default)]
struct Accumulator {
    sinks: std::collections::BTreeMap<u32, (String, String, f64, bool)>,
    streams: std::collections::BTreeMap<u32, (String, Option<String>, f64, bool)>,
    default_sink_name: Option<String>,
    sink_devices: std::collections::BTreeMap<u32, (u32, u32)>,
    routes: std::collections::BTreeMap<u32, Vec<(u32, u32, f64, bool)>>,
}

impl Accumulator {
    /// Applies one already-parsed top-level array (a full `pw-dump`, or
    /// one `--monitor` delta) into the running state. An object present
    /// in `objects` replaces any previous entry for its `id`; an
    /// `"info": null` object removes it; anything else is left as it
    /// was. A metadata array that does not itself carry a
    /// `default.audio.sink` entry (most graph changes have nothing to do
    /// with the default sink) leaves `default_sink_name` at whatever it
    /// was before -- it is never reset just because this particular
    /// delta happened not to mention it.
    fn apply_array(&mut self, objects: &[Value]) {
        if let Some(name) = default_sink_name(objects) {
            self.default_sink_name = Some(name);
        }
        for object in objects {
            let Some(id) = object.get("id").and_then(Value::as_u64) else {
                continue;
            };
            let id = id as u32;
            if object.get("info").is_some_and(Value::is_null) {
                self.sinks.remove(&id);
                self.streams.remove(&id);
                self.sink_devices.remove(&id);
                self.routes.remove(&id);
                continue;
            }
            if object.get("type").and_then(Value::as_str) == Some("PipeWire:Interface:Device") {
                if let Some(routes) = object.pointer("/info/params/Route").and_then(Value::as_array) {
                    let active = routes.iter().filter_map(|route| {
                        if route.get("direction").and_then(Value::as_str) != Some("Output") { return None; }
                        let index = route.get("index")?.as_u64()? as u32;
                        let device = route.get("device")?.as_u64()? as u32;
                        let props = route.get("props")?;
                        let (volume, muted) = props_volume(&serde_json::json!({"Props": [props]}));
                        Some((index, device, volume, muted))
                    }).collect();
                    self.routes.insert(id, active);
                }
                continue;
            }
            if object.get("type").and_then(Value::as_str) != Some("PipeWire:Interface:Node") {
                continue;
            }
            let Some(info) = object.get("info") else { continue };
            let Some(props) = info.get("props") else { continue };
            let Some(media_class) = props.get("media.class").and_then(Value::as_str) else {
                continue;
            };
            let params = info.get("params").cloned().unwrap_or(Value::Null);
            let (linear_volume, muted) = props_volume(&params);
            match media_class {
                "Audio/Sink" => {
                    self.streams.remove(&id);
                    if let (Some(device), Some(profile)) = (props.get("device.id").and_then(Value::as_u64), props.get("card.profile.device").and_then(Value::as_u64)) {
                        self.sink_devices.insert(id, (device as u32, profile as u32));
                    } else { self.sink_devices.remove(&id); }
                    let name = props
                        .get("node.name")
                        .and_then(Value::as_str)
                        .unwrap_or_default()
                        .to_string();
                    let description = props
                        .get("node.description")
                        .and_then(Value::as_str)
                        .unwrap_or(&name)
                        .to_string();
                    self.sinks.insert(id, (name, description, linear_volume, muted));
                }
                "Stream/Output/Audio" => {
                    self.sinks.remove(&id);
                    let app_name = props
                        .get("application.name")
                        .and_then(Value::as_str)
                        .or_else(|| props.get("node.name").and_then(Value::as_str))
                        .unwrap_or("(unknown app)")
                        .to_string();
                    // The canonical PipeWire key is hyphenated
                    // (`application.icon-name`, `pipewire/keys.h`'s own
                    // `PW_KEY_APP_ICON_NAME`, read directly) -- not the
                    // underscored `application.icon_name` an earlier
                    // version of this parser looked for, which never
                    // matches a real dump.
                    let app_icon = props
                        .get("application.icon-name")
                        .and_then(Value::as_str)
                        .map(String::from);
                    self.streams.insert(id, (app_name, app_icon, linear_volume, muted));
                }
                _ => {}
            }
        }
    }

    /// Materializes the current state as a `GraphSnapshot`. `is_default`
    /// is computed here, not stored per-sink, so a default-sink change
    /// (its own metadata entry, possibly in a later array than the sink
    /// itself) always reflects correctly against every sink already
    /// known, not just whichever one was being applied at the time the
    /// name last changed.
    fn snapshot(&self) -> GraphSnapshot {
        let sinks = self
            .sinks
            .iter()
            .map(|(&id, (name, description, linear_volume, muted))| {
                let route = self.sink_devices.get(&id).and_then(|&(device, profile)| {
                    self.routes.get(&device)?.iter().find(|r| r.1 == profile)
                        .map(|&(index, profile, volume, muted)| ((device, index, profile), volume, muted))
                });
                Sink {
                id,
                name: name.clone(),
                description: description.clone(),
                linear_volume: route.map_or(*linear_volume, |r| r.1),
                muted: route.map_or(*muted, |r| r.2),
                is_default: self.default_sink_name.as_deref() == Some(name.as_str()),
                route: route.map(|r| r.0),
            }})
            .collect();
        let streams = self
            .streams
            .iter()
            .map(|(&id, (app_name, app_icon, linear_volume, muted))| Stream {
                id,
                app_name: app_name.clone(),
                app_icon: app_icon.clone(),
                linear_volume: *linear_volume,
                muted: *muted,
            })
            .collect();
        GraphSnapshot { sinks, streams }
    }
}

fn default_sink_name(objects: &[Value]) -> Option<String> {
    objects.iter().find_map(|object| {
        if object.get("type").and_then(Value::as_str) != Some("PipeWire:Interface:Metadata") {
            return None;
        }
        let entries = object.get("metadata").and_then(Value::as_array)?;
        entries.iter().find_map(|entry| {
            if entry.get("key").and_then(Value::as_str) != Some("default.audio.sink") {
                return None;
            }
            let value = entry.get("value")?;
            // PipeWire nests this as either an already-parsed object or a
            // JSON-encoded string, depending on the metadata type; accept
            // both rather than assuming one.
            let name = match value {
                Value::String(raw) => serde_json::from_str::<Value>(raw)
                    .ok()
                    .and_then(|nested| nested.get("name").and_then(Value::as_str).map(String::from)),
                Value::Object(_) => value.get("name").and_then(Value::as_str).map(String::from),
                _ => None,
            };
            name
        })
    })
}

/// Parses one JSON array (a full `pw-dump`, or one `--monitor` delta) on
/// its own, against otherwise-empty prior state. Used for a self-
/// contained one-shot dump and by this module's own tests; `spawn_monitor`
/// does *not* call this per array (that was the bug an earlier version of
/// this module had -- see `Accumulator`'s own doc comment) and instead
/// keeps one running `Accumulator` for the child's whole lifetime.
/// Unknown/irrelevant object types and fields are ignored rather than
/// rejected -- a real dump carries many object kinds (devices, ports,
/// factories, clients) this shell has no use for.
pub fn parse_dump(json: &str) -> Result<GraphSnapshot, String> {
    if json.len() > DUMP_LIMIT {
        return Err("pw-dump output too large".into());
    }
    let value: Value = serde_json::from_str(json).map_err(|error| error.to_string())?;
    let objects = value.as_array().ok_or("pw-dump output was not a JSON array")?;
    let mut accumulator = Accumulator::default();
    accumulator.apply_array(objects);
    Ok(accumulator.snapshot())
}

/// Formats the `pw-cli` line to set a node's volume/mute. `pw-cli`
/// accepts commands non-interactively over stdin (its documented
/// scripting mode); this is the exact single line this shell's
/// persistent `pw-cli` child is fed per throttled write. The volume
/// values themselves are the caller's linear (0.0-1.0) amplitude --
/// `volume::percent_to_linear`'s job, not this module's.
// stdin is the pw-cli command language, not a shell: outer shell quotes
// make SPA parse a string rather than a Props object and silently discard it.
pub fn set_volume_command(node_id: u32, linear_volume: f64, muted: bool) -> String {
    let clamped = linear_volume.clamp(0.0, 1.0);
    format!(
        "set-param {node_id} Props {{ \"channelVolumes\": [ {v:.4}, {v:.4} ], \"mute\": {m} }}",
        v = clamped,
        m = muted,
    )
}

/// A device Route write matches WirePlumber/wpctl's ALSA hardware-mixer path.
/// Writing the sink's DSP Props instead would stack a second volume/mute.
pub fn set_sink_volume_command(sink: &Sink, linear: f64, muted: bool) -> String {
    if let Some((device, index, profile)) = sink.route {
        format!("set-param {device} Route {{ \"index\": {index}, \"device\": {profile}, \"props\": {{ \"channelVolumes\": [ {v:.4}, {v:.4} ], \"mute\": {muted} }}, \"save\": true }}", v=linear.clamp(0.0,1.0))
    } else { set_volume_command(sink.id, linear, muted) }
}

/// One PipeWire event this shell's monitor thread hands to `main.rs`:
/// a freshly parsed snapshot, or the monitor child dying (never
/// silently -- `main.rs` decides whether/how to surface that; this
/// module never retries on its own beyond what `spawn_monitor` already
/// does).
pub enum Event {
    Snapshot(GraphSnapshot),
    MonitorExited,
}

/// Spawns `dump_command` (normally `pw-dump`) with `--monitor` (or
/// whatever `extra_args` the caller supplies -- tests substitute a
/// fixture script and different args) and streams parsed snapshots back
/// over the returned channel. The channel is small and lossy on
/// purpose: a stale snapshot behind a fresher one is simply dropped
/// (`try_send`), since only the latest graph state is ever useful to
/// paint.
pub fn spawn_monitor(dump_command: PathBuf, extra_args: &[&str]) -> io::Result<Receiver<Event>> {
    let mut child = Command::new(&dump_command)
        .args(extra_args)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()?;
    let stdout = child.stdout.take().ok_or_else(|| {
        io::Error::other("pw-dump gave no stdout")
    })?;
    let (sender, receiver) = mpsc::sync_channel(4);
    thread::spawn(move || {
        run_monitor_reader(stdout, &sender);
        let _ = sender.try_send(Event::MonitorExited);
        let _ = child.kill();
        let _ = child.wait();
    });
    Ok(receiver)
}

fn run_monitor_reader(stdout: impl Read, sender: &SyncSender<Event>) {
    let stream = serde_json::Deserializer::from_reader(stdout).into_iter::<Value>();
    // One `Accumulator` for the whole life of the child, not one per
    // array: `pw-dump --monitor` prints only what changed on each event
    // (`Accumulator`'s own doc comment cites the upstream source for
    // this), so a fresh accumulator per array would show only the most
    // recently changed node and silently drop every other sink/stream.
    let mut accumulator = Accumulator::default();
    for parsed in stream {
        let Ok(value) = parsed else {
            break;
        };
        let Some(objects) = value.as_array() else {
            continue;
        };
        accumulator.apply_array(objects);
        if let Err(TrySendError::Disconnected(_)) =
            sender.try_send(Event::Snapshot(accumulator.snapshot()))
        {
            break;
        }
    }
}

/// The persistent `pw-cli` writer: one child process, fed one command
/// line per throttled slider write or device-picker action. Commands are
/// fire-and-forget from this shell's point of view -- `pw-cli` prints a
/// reply on stdout, but this shell has no need to correlate it with a
/// specific write (the next `pw-dump --monitor` snapshot is the
/// authoritative confirmation), so stdout is discarded rather than read.
pub struct Writer {
    stdin: ChildStdin,
    _child: Child,
}

impl Writer {
    pub fn spawn(cli_command: PathBuf) -> io::Result<Self> {
        let mut child = Command::new(&cli_command)
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()?;
        let stdin = child.stdin.take().ok_or_else(|| {
            io::Error::other("pw-cli gave no stdin")
        })?;
        Ok(Self { stdin, _child: child })
    }

    pub fn send(&mut self, command: &str) -> io::Result<()> {
        self.stdin.write_all(command.as_bytes())?;
        self.stdin.write_all(b"\n")?;
        self.stdin.flush()
    }
}

/// A background-thread-owned handle a UI thread can hand throttled
/// commands to without blocking on the child's own pace. Mirrors
/// `WifiWorker`'s request/reply split (`wifi_settings.rs`), minus the
/// reply half -- there is nothing to reply with here.
pub struct WriterHandle {
    commands: SyncSender<String>,
}

impl WriterHandle {
    pub fn spawn(cli_command: PathBuf) -> io::Result<Self> {
        let mut writer = Writer::spawn(cli_command)?;
        let (commands, incoming) = mpsc::sync_channel::<String>(8);
        thread::spawn(move || {
            while let Ok(command) = incoming.recv() {
                if writer.send(&command).is_err() {
                    break;
                }
            }
        });
        Ok(Self { commands })
    }

    /// Best-effort: if the channel is momentarily full (the writer
    /// thread is mid-write), the oldest queued write is simply
    /// superseded by dropping this one -- the next throttled sample
    /// carries the current value anyway, same "only the latest state
    /// matters" reasoning as `spawn_monitor`'s channel.
    pub fn try_send(&self, command: String) {
        let _ = self.commands.try_send(command);
    }
}

/// Reads complete `pw-cli`-style command lines from `reader` -- exposed
/// for a test double server, not used in production (production only
/// ever *writes* to `pw-cli`'s stdin).
#[cfg(test)]
fn read_lines(reader: impl Read) -> Vec<String> {
    use std::io::{BufRead, BufReader};
    BufReader::new(reader)
        .lines()
        .map_while(Result::ok)
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    fn sink_object(id: u32, name: &str, volumes: &str, muted: bool) -> String {
        format!(
            r#"{{
                "id": {id},
                "type": "PipeWire:Interface:Node",
                "info": {{
                    "props": {{
                        "media.class": "Audio/Sink",
                        "node.name": "{name}",
                        "node.description": "K230 Inno Codec"
                    }},
                    "params": {{
                        "Props": [ {{ "channelVolumes": [{volumes}], "mute": {muted} }} ]
                    }}
                }}
            }}"#
        )
    }

    fn stream_object(id: u32, app_name: &str, icon: &str, volumes: &str) -> String {
        format!(
            r#"{{
                "id": {id},
                "type": "PipeWire:Interface:Node",
                "info": {{
                    "props": {{
                        "media.class": "Stream/Output/Audio",
                        "application.name": "{app_name}",
                        "application.icon-name": "{icon}",
                        "node.name": "{app_name}"
                    }},
                    "params": {{
                        "Props": [ {{ "channelVolumes": [{volumes}], "mute": false }} ]
                    }}
                }}
            }}"#
        )
    }

    fn metadata_object(sink_name: &str) -> String {
        format!(
            r#"{{
                "id": 0,
                "type": "PipeWire:Interface:Metadata",
                "props": {{ "metadata.name": "default" }},
                "metadata": [
                    {{ "subject": 0, "key": "default.audio.sink", "type": "Spa:String:JSON",
                       "value": "{{\"name\":\"{sink_name}\"}}" }}
                ]
            }}"#
        )
    }

    #[test]
    fn parse_dump_finds_the_default_sink_and_a_stream_with_its_app_metadata() {
        let sink_name = "alsa_output.platform-soc_i2s.k230-inno.stereo-fallback";
        let json = format!(
            "[{}, {}, {}]",
            sink_object(45, sink_name, "0.5, 0.5", false),
            stream_object(78, "mpv", "mpv", "1.0, 1.0"),
            metadata_object(sink_name),
        );
        let snapshot = parse_dump(&json).unwrap();
        assert_eq!(snapshot.sinks.len(), 1);
        let sink = &snapshot.sinks[0];
        assert_eq!(sink.id, 45);
        assert_eq!(sink.name, sink_name);
        assert_eq!(sink.description, "K230 Inno Codec");
        assert!((sink.linear_volume - 0.5).abs() < 1e-9);
        assert!(!sink.muted);
        assert!(sink.is_default);

        assert_eq!(snapshot.streams.len(), 1);
        let stream = &snapshot.streams[0];
        assert_eq!(stream.app_name, "mpv");
        assert_eq!(stream.app_icon.as_deref(), Some("mpv"));
        assert!((stream.linear_volume - 1.0).abs() < 1e-9);
    }

    #[test]
    fn parse_dump_marks_no_sink_default_when_metadata_names_something_else() {
        let json = format!(
            "[{}, {}]",
            sink_object(1, "alsa_output.a", "1.0, 1.0", false),
            metadata_object("alsa_output.b"),
        );
        let snapshot = parse_dump(&json).unwrap();
        assert!(!snapshot.sinks[0].is_default);
    }

    #[test]
    fn parse_dump_reads_a_muted_sink_and_ignores_unknown_object_types() {
        let json = format!(
            "[{}, {{\"id\":9,\"type\":\"PipeWire:Interface:Client\"}}]",
            sink_object(2, "alsa_output.c", "0.0, 0.0", true),
        );
        let snapshot = parse_dump(&json).unwrap();
        assert_eq!(snapshot.sinks.len(), 1);
        assert!(snapshot.sinks[0].muted);
        assert!((snapshot.sinks[0].linear_volume).abs() < 1e-9);
    }

    #[test]
    fn parse_dump_rejects_non_array_and_oversized_input() {
        assert!(parse_dump("{}").is_err());
        assert!(parse_dump("not json").is_err());
        let huge = "[".to_string() + &"0".repeat(DUMP_LIMIT + 1) + "]";
        assert!(parse_dump(&huge).is_err());
    }

    #[test]
    fn run_monitor_reader_delivers_a_snapshot_per_concatenated_dump() {
        let first = format!("[{}]", sink_object(1, "alsa_output.a", "0.2, 0.2", false));
        let second = format!("[{}]", sink_object(1, "alsa_output.a", "0.8, 0.8", false));
        // `pw-dump --monitor` re-emits a whole fresh array on each graph
        // change, back to back with no delimiter -- exactly what a real
        // child's stdout looks like over two changes.
        let concatenated = format!("{first}{second}");
        let (sender, receiver) = mpsc::sync_channel(4);
        run_monitor_reader(Cursor::new(concatenated.into_bytes()), &sender);
        let mut snapshots = Vec::new();
        while let Ok(Event::Snapshot(snapshot)) = receiver.try_recv() {
            snapshots.push(snapshot);
        }
        assert_eq!(snapshots.len(), 2);
        assert!((snapshots[0].sinks[0].linear_volume - 0.2).abs() < 1e-9);
        assert!((snapshots[1].sinks[0].linear_volume - 0.8).abs() < 1e-9);
    }

    #[test]
    fn a_delta_that_only_touches_one_node_does_not_wipe_the_others() {
        // The bug this `Accumulator` exists to fix: `pw-dump --monitor`
        // emits only the objects that changed on a given event (confirmed
        // directly against `pw-dump.c`'s `dump_objects()`). A sink's
        // volume changing must not make an unrelated, untouched stream
        // vanish from the running snapshot.
        let sink_name = "alsa_output.a";
        let initial = format!(
            "[{}, {}, {}]",
            sink_object(1, sink_name, "0.5, 0.5", false),
            stream_object(2, "mpv", "multimedia-player", "1.0"),
            metadata_object(sink_name),
        );
        let delta = format!("[{}]", sink_object(1, sink_name, "0.9, 0.9", false));
        let (sender, receiver) = mpsc::sync_channel(4);
        run_monitor_reader(Cursor::new(format!("{initial}{delta}").into_bytes()), &sender);
        let mut snapshots = Vec::new();
        while let Ok(Event::Snapshot(snapshot)) = receiver.try_recv() {
            snapshots.push(snapshot);
        }
        assert_eq!(snapshots.len(), 2);
        // The stream was never re-sent in the delta, but must still be
        // present in the cumulative snapshot after it.
        let after_delta = &snapshots[1];
        assert_eq!(after_delta.streams.len(), 1);
        assert_eq!(after_delta.streams[0].app_name, "mpv");
        assert!((after_delta.sinks[0].linear_volume - 0.9).abs() < 1e-9);
        assert!(after_delta.sinks[0].is_default);
    }

    #[test]
    fn a_removal_delta_drops_only_the_named_object() {
        let sink_name = "alsa_output.a";
        let initial = format!(
            "[{}, {}]",
            sink_object(1, sink_name, "0.5, 0.5", false),
            stream_object(2, "mpv", "multimedia-player", "1.0"),
        );
        let removal = r#"[{"id": 2, "type": "PipeWire:Interface:Node", "info": null}]"#;
        let (sender, receiver) = mpsc::sync_channel(4);
        run_monitor_reader(
            Cursor::new(format!("{initial}{removal}").into_bytes()),
            &sender,
        );
        let mut snapshots = Vec::new();
        while let Ok(Event::Snapshot(snapshot)) = receiver.try_recv() {
            snapshots.push(snapshot);
        }
        let after_removal = snapshots.last().expect("a snapshot after removal");
        assert!(after_removal.streams.is_empty());
        assert_eq!(after_removal.sinks.len(), 1);
    }

    const DUMP_INITIAL_FIXTURE: &str =
        include_str!("../tests/fixtures/pipewire/dump-initial.json");
    const MONITOR_SINK_MUTED_FIXTURE: &str =
        include_str!("../tests/fixtures/pipewire/monitor-sink-muted.json");
    const MONITOR_STREAM_REMOVED_FIXTURE: &str =
        include_str!("../tests/fixtures/pipewire/monitor-stream-removed.json");
    const MONITOR_DEFAULT_SINK_CHANGED_FIXTURE: &str =
        include_str!("../tests/fixtures/pipewire/monitor-default-sink-changed.json");

    #[test]
    fn a_captured_initial_dump_fixture_parses_into_one_sink_and_one_stream() {
        let snapshot = parse_dump(DUMP_INITIAL_FIXTURE).expect("valid fixture");
        assert_eq!(snapshot.sinks.len(), 1);
        assert_eq!(snapshot.streams.len(), 1);
        let sink = &snapshot.sinks[0];
        assert_eq!(sink.id, 50);
        assert_eq!(sink.description, "K230 Inno codec line-out");
        assert!(sink.is_default);
        assert!((sink.linear_volume - 0.512).abs() < 1e-9);
        let stream = &snapshot.streams[0];
        assert_eq!(stream.app_name, "k230 video");
        assert_eq!(stream.app_icon.as_deref(), Some("multimedia-player"));
    }

    #[test]
    fn captured_fixtures_replayed_through_the_monitor_reader_track_mute_removal_and_the_default_sink() {
        let (sender, receiver) = mpsc::sync_channel(8);
        let mut combined = String::new();
        combined.push_str(DUMP_INITIAL_FIXTURE);
        combined.push_str(MONITOR_SINK_MUTED_FIXTURE);
        combined.push_str(MONITOR_STREAM_REMOVED_FIXTURE);
        combined.push_str(MONITOR_DEFAULT_SINK_CHANGED_FIXTURE);
        run_monitor_reader(Cursor::new(combined.into_bytes()), &sender);
        let mut snapshots = Vec::new();
        while let Ok(Event::Snapshot(snapshot)) = receiver.try_recv() {
            snapshots.push(snapshot);
        }
        assert_eq!(snapshots.len(), 4);
        // After the mute event: still 1 sink (muted), 1 stream untouched.
        assert!(snapshots[1].sinks[0].muted);
        assert_eq!(snapshots[1].streams.len(), 1);
        // After the stream-removed event: stream gone, sink untouched.
        assert!(snapshots[2].streams.is_empty());
        assert_eq!(snapshots[2].sinks.len(), 1);
        // After the default-sink-changed event: a second sink appeared and
        // is now the default; the first (still-known) sink is not.
        let last = &snapshots[3];
        assert_eq!(last.sinks.len(), 2);
        let default_sink = last.sinks.iter().find(|sink| sink.is_default).expect("a default");
        assert_eq!(default_sink.id, 120);
    }

    #[test]
    fn expanded_row_lists_streams_before_sinks_and_bounds_the_index() {
        let snapshot = GraphSnapshot {
            sinks: vec![Sink {
                id: 50,
                name: "alsa_output.a".into(),
                description: "Inno codec".into(),
                linear_volume: 0.5,
                muted: false,
                is_default: true,
                route: None,
            }],
            streams: vec![Stream {
                id: 78,
                app_name: "mpv".into(),
                app_icon: Some("multimedia-player".into()),
                linear_volume: 1.0,
                muted: false,
            }],
        };
        assert_eq!(snapshot.expanded_row_count(), 2);
        assert!(matches!(snapshot.expanded_row(0), Some(ExpandedRow::Stream(s)) if s.app_name == "mpv"));
        assert!(matches!(snapshot.expanded_row(1), Some(ExpandedRow::Sink(s)) if s.id == 50));
        assert!(snapshot.expanded_row(2).is_none());
    }

    #[test]
    fn hardware_route_overrides_dsp_props_and_survives_device_only_updates() {
        let sink = serde_json::json!({"id":52,"type":"PipeWire:Interface:Node","info":{"props":{"media.class":"Audio/Sink","node.name":"inno","device.id":51,"card.profile.device":3},"params":{"Props":[{"channelVolumes":[1.0,1.0],"mute":false}]}}});
        let device = |v:f64, muted:bool| serde_json::json!({"id":51,"type":"PipeWire:Interface:Device","info":{"params":{"Route":[{"index":0,"device":2,"direction":"Input","props":{"channelVolumes":[1.0]}},{"index":1,"device":3,"direction":"Output","props":{"channelVolumes":[v,v],"mute":muted}}]}}});
        let mut acc=Accumulator::default();
        acc.apply_array(&[device(0.064,false),sink]);
        let snapshot=acc.snapshot();let sink=&snapshot.sinks[0];
        assert_eq!(sink.route,Some((51,1,3)));
        assert!((sink.linear_volume-0.064).abs()<1e-9);
        let line=set_sink_volume_command(sink,0.125,true);
        let payload:Value=serde_json::from_str(line.strip_prefix("set-param 51 Route ").unwrap()).unwrap();
        assert_eq!(payload["index"],1);assert_eq!(payload["device"],3);
        assert_eq!(payload["props"]["mute"],true);
        assert_eq!(payload["props"]["channelVolumes"][0],0.125);
        acc.apply_array(&[device(0.216,true)]);
        assert_eq!(acc.snapshot().sinks[0].linear_volume,0.216);
        assert!(acc.snapshot().sinks[0].muted);
        acc.apply_array(&[serde_json::json!({"id":51,"info":null})]);
        assert_eq!(acc.snapshot().sinks[0].route,None);
        assert_eq!(acc.snapshot().sinks[0].linear_volume,1.0);
    }

    #[test]
    fn set_volume_command_formats_a_scriptable_pw_cli_line() {
        let line = set_volume_command(45, 0.5, false);
        assert_eq!(
            line,
            "set-param 45 Props { \"channelVolumes\": [ 0.5000, 0.5000 ], \"mute\": false }"
        );
        let muted = set_volume_command(45, 1.0, true);
        assert!(muted.contains("\"mute\": true"));
    }

    #[test]
    fn set_volume_command_clamps_out_of_range_linear_volume() {
        let line = set_volume_command(1, 5.0, false);
        assert!(line.contains("1.0000"));
        let line = set_volume_command(1, -5.0, false);
        assert!(line.contains("0.0000"));
    }

    /// A real round trip: a fake "pw-cli" (a tiny script that just
    /// copies its stdin to a file) fed two commands through
    /// `WriterHandle`, proving the writer thread actually delivers both
    /// lines to the child's stdin in order over a real pipe, not just an
    /// in-memory buffer.
    #[test]
    fn writer_handle_delivers_commands_in_order_to_a_real_child_process() {
        let dir = std::env::temp_dir().join(format!(
            "k230-pipewire-writer-test-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        let capture = dir.join("captured.txt");
        let script = dir.join("fake-pw-cli.sh");
        std::fs::write(&script, format!("#!/bin/sh\ncat > {}\n", capture.display())).unwrap();
        std::fs::set_permissions(
            &script,
            std::os::unix::fs::PermissionsExt::from_mode(0o755),
        )
        .unwrap();

        let handle = WriterHandle::spawn(script).unwrap();
        handle.try_send(set_volume_command(45, 0.25, false));
        handle.try_send(set_volume_command(45, 0.75, false));
        drop(handle);

        // Give the writer thread and the child's `cat` a moment to
        // finish; polled rather than a fixed sleep window alone; bounded
        // so a genuine failure still fails the test instead of hanging.
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(5);
        let mut content = String::new();
        while std::time::Instant::now() < deadline {
            content = std::fs::read_to_string(&capture).unwrap_or_default();
            if content.lines().count() >= 2 {
                break;
            }
            std::thread::sleep(std::time::Duration::from_millis(20));
        }
        let lines = read_lines(Cursor::new(content.clone().into_bytes()));
        assert_eq!(lines.len(), 2, "captured: {content:?}");
        assert!(lines[0].contains("0.2500"));
        assert!(lines[1].contains("0.7500"));
        std::fs::remove_dir_all(&dir).unwrap();
    }
}
