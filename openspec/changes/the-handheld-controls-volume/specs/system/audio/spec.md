## Purpose

Define the PipeWire/WirePlumber session layer this shell runs, and the
volume control, live-graph awareness, HUD and output-device-picker surfaces
built on it. Disjoint from `the-handheld-plays-through-its-speaker`'s own
Inno-codec/external-I2S-route requirements for the same `system/audio`
capability; see that change for the board's ALSA/kernel-level audio path.

## ADDED Requirements

### Requirement: A session-scoped PipeWire/WirePlumber layer runs for the coherent shell

*Host build proof: `nix build .#handheld-shell-rust` and the full
`k230-coherent-shell` system closure cross-build succeed with
`systemd.services.pipewire`/`wireplumber`/`pipewire-pulse` present in the
closure. Host/build proof only -- whether these units actually reach
`active` on the board is a separate, open task (see tasks.md); no task here
claims that from a host build.*

When `k230.shell.coherentShell` is enabled, the system SHALL run `pipewire`,
`wireplumber` and `pipewire-pulse` as plain systemd system services under
the `shell` user, bound to `shell.service`'s own lifecycle, and SHALL
install the PipeWire ALSA-compat plugin files so an existing plain-ALSA
client (mpv, unchanged) is transparently redirected through PipeWire. No
additional daemon beyond these three SHALL be added for this purpose.

*Grounding: `nix/shell.nix`'s `systemd.services.pipewire`/`wireplumber`/
`pipewire-pulse`, each `bindsTo`/`partOf`/`after = [ "shell.service" ]`,
`User = "shell"`; `environment.etc."alsa/conf.d/{50-pipewire,99-pipewire-
default}.conf"` sourced from `${pkgs.pipewire}/share/alsa/alsa.conf.d/`.
Design.md Decision 1 records why the `services.pipewire`/`wireplumber`
NixOS modules were not used instead.*

#### Scenario: The shell session starts with sound server support present
- **WHEN** `k230.shell.coherentShell` is enabled and the system closure is built
- **THEN** the closure contains `pipewire`, `wireplumber`, `pipewire-pulse` and their two ALSA plugin config files, wired to start with the shell session

### Requirement: The shade and Settings each show a volume slider, matching the brightness slider's own component and floor semantics

*Host build proof: `cargo test`/`cargo clippy --all-targets` for
`nix/rust-shell-client` pass; `slider.rs`'s floor-parameterized functions
(`clamp_percent_with_floor`, `value_at_x_with_floor`,
`Drag::start_with_floor`) and `volume.rs`'s own unit tests cover the mapping,
clamping and drag-to-mute behavior below. These are host/build proofs only;
see the open real-finger task for physical acceptance.*

The Settings screen and the pull-down shade SHALL each present a volume
control directly under the existing brightness slider, using the same
shared Material-3-style track/thumb component (`slider.rs`) rather than a
forked copy. Unlike brightness, the volume slider's floor SHALL be `0`
(true silence is a reachable value); a drag to the very bottom SHALL engage
mute, and a drag anywhere above `0` SHALL clear mute and set the level,
matching Android's own slider. A tap on the leading speaker glyph SHALL
toggle mute without changing the remembered level, so unmuting restores the
level active before the mute.

*Grounding: `nix/rust-shell-client/src/slider.rs`'s `MIN_PERCENT`-vs-`floor`
split (Decision unchanged from `the-brightness-control-is-a-slider`, only
generalized); `volume::VolumeState::{set_from_drag,toggle_mute,
displayed_percent}`.*

#### Scenario: Dragging the volume slider to the bottom mutes rather than merely reading zero
- **WHEN** a person drags the volume slider to its lowest point
- **THEN** the sink reports muted, and dragging back up unmutes and shows the dragged-to level

#### Scenario: The speaker icon toggles mute and restores the remembered level
- **WHEN** a person taps the speaker glyph while the level is 70%, then taps it again
- **THEN** the sink is muted after the first tap and reads 70% again, unmuted, after the second

### Requirement: The volume UI maps a slider position through a cubic perceptual curve, matching Android and matching `wpctl` itself

*Host build proof: `volume::tests::percent_to_linear_is_cubic_not_linear`
and `linear_to_percent_round_trips_percent_to_linear` (unit tests only);
`docs/evidence/volume/wpctl.md` records the live `wpctl`/`pw-dump` capture
this curve was checked against on a development host (not this board).*

A UI slider percent SHALL map to a linear PipeWire volume amplitude through
`linear = (percent/100)^3` (and the exact inverse when reading a linear
value back to a percent for display), not a straight linear map. This SHALL
hold both for this shell's own throttled live-drag writes (which set
`channelVolumes` directly and so must compute this curve themselves) and be
consistent with `wpctl set-volume`'s own percent argument, which already
applies the same curve internally.

*Grounding: `volume::percent_to_linear`/`linear_to_percent`;
`docs/evidence/volume/wpctl.md`'s captured `wpctl set-volume ID 0.58` ->
`channelVolumes: [0.195114, 0.195114]` (`0.58^3 = 0.195112`), and a second,
independent data point at `0.57`/`0.185185`.*

#### Scenario: Equal slider steps read as roughly equal loudness steps
- **WHEN** the slider moves from 50% to 60%, and separately from 90% to 100%
- **THEN** the underlying linear amplitude changes by a small amount near the top and a larger amount lower down, per the cubic curve, not a fixed linear step either place

### Requirement: A live drag writes PipeWire directly through one persistent process, throttled, never blocking the UI

*Host build proof: `pipewire_ipc::tests::writer_handle_delivers_commands_
in_order_to_a_real_child_process` spawns a real child process (a test
double, not `pw-cli` itself) and confirms ordered delivery over a real
pipe; `set_volume_command_formats_a_scriptable_pw_cli_line` covers the
exact command text. Host/build proof only.*

While a volume slider drag is in progress, the system SHALL send writes at
roughly the same throttled cadence the brightness slider already uses
(`slider::LIVE_WRITE_INTERVAL_MS`), each written to one already-running
`pw-cli` child process's stdin (no process spawned per write), never
blocking the Wayland/UI thread. The drag's release SHALL always send one
additional, authoritative `wpctl set-volume ID <percent>%` call regardless
of the live-write throttle's own timing, so the committed value is always
the one `wpctl` itself computed and PipeWire/WirePlumber actually holds.

*Grounding: `pipewire_ipc::{Writer,WriterHandle,set_volume_command}`;
design.md Decision 2's cost accounting and Decision 4's curve-agreement
reasoning.*

#### Scenario: A drag sends throttled writes to one persistent process
- **WHEN** a person drags the volume slider continuously for one second
- **THEN** writes are sent to the same already-running `pw-cli` process at roughly the brightness slider's own throttled rate, and no new process is spawned per write

#### Scenario: Release always commits through the authoritative path
- **WHEN** a drag releases at a moment the live-write throttle had not yet fired for the finger's current position
- **THEN** the release still sends the finger's true final value through a `wpctl set-volume` call

### Requirement: The shell watches the PipeWire graph and reflects external changes live

*Host build proof: `pipewire_ipc::tests::a_delta_that_only_touches_one_
node_does_not_wipe_the_others`, `a_removal_delta_drops_only_the_named_
object`, and the fixture-replay tests against `tests/fixtures/pipewire/*`
(captured-shape JSON, not live board output) all pass. Host/build proof
only -- see the open task for whether this board's own WirePlumber
actually names its sinks/streams the way these fixtures assume.*

The system SHALL run one persistent `pw-dump --monitor` process for the
life of the shell session and apply every array it prints -- the initial
full dump and every subsequent per-change delta -- onto one running graph
model, never discarding a sink or stream a given delta did not itself
mention. An object reported as `{"id": <id>, "info": null}` SHALL be
removed from that model. The shade's and Settings' own sliders, the HUD,
and the expanded per-stream panel SHALL all reflect this same running
model, so an external app, `wpctl` from a console, or a hardware key
changing the default sink's volume or mute state is shown without polling.

*Grounding: `pipewire_ipc::{spawn_monitor,run_monitor_reader,Accumulator}`;
design.md Decision 3, citing upstream `pw-dump.c`'s `dump_objects()`
directly and a live capture of the exact array shapes involved.*

#### Scenario: An external volume change updates the shown level without polling
- **WHEN** some other process changes the default sink's volume while the shade is open
- **THEN** the shade's slider moves to the new value once the monitor process's next array is applied, with no fixed-interval poll driving the update

#### Scenario: A change to one node never hides an unrelated node already known
- **WHEN** the default sink's volume changes while an unrelated app stream is already playing
- **THEN** the app stream remains visible and unchanged in the running model after the sink's own update is applied

### Requirement: An Android-style volume HUD appears for changes the shell did not itself just show

*Host build proof: `volume::tests::hud_is_hidden_until_shown_and_
autohides_after_its_window`, `hud_toggle_expand_flips_state_and_refreshes_
the_timer`, `hud_drag_is_owned_by_the_touch_that_started_it`, and
`change_origin_only_the_own_slider_suppresses_the_hud` all pass.
QEMU capture: `docs/evidence/volume/` shows the HUD collapsed and expanded.
Host/QEMU proof only -- see the open real-finger and hardware-volume-key
tasks.*

A hardware/keyboard volume key or any external PipeWire graph change to the
default sink's volume/mute SHALL raise a vertical pill HUD on the panel's
right edge; a drag on the shade's or Settings' own volume slider SHALL
NOT, since that slider is already its own visible feedback (mirroring the
brightness slider's own commit-toast suppression). The HUD SHALL auto-hide
about 2.5 seconds after its last change, SHALL be draggable along the
edge, and SHALL expand via a "…" affordance into a per-stream list: one row
per PipeWire `Stream/Output/Audio` node, each with its own slider, and the
app's name and icon where `application.name`/`application.icon-name` are
present, falling back to the node's own name.

*Grounding: `volume::{Hud,ChangeOrigin,HUD_AUTO_HIDE_MS}`;
`pipewire_ipc::GraphSnapshot::streams` supplies the expanded panel's rows.*

#### Scenario: A hardware volume key raises the HUD and it auto-hides
- **WHEN** a volume key changes the default sink's level
- **THEN** the HUD appears showing the new level and disappears on its own about 2.5 seconds after the last such change

#### Scenario: Dragging the shade's own slider does not also raise the HUD
- **WHEN** a person drags the shade's own volume slider
- **THEN** no HUD appears, since the slider itself is already visible on screen

#### Scenario: The "…" affordance expands to per-app streams
- **WHEN** a person taps the HUD's expand affordance while at least one app is playing audio
- **THEN** the panel shows one row per playing app, each with its own name (or icon, where resolvable) and its own slider

### Requirement: Hardware/keyboard volume keys act through the same external-change path as any other app

*Host build proof: the Sway config fragment is part of the
`k230-coherent-shell` closure build. `docs/research/board-capability-
inventory.md` is cited, not re-derived, for what this board's own inputs
are known to emit. Host/build proof only; see the open task for whether any
attached keyboard actually sends these keysyms on this board.*

When a `bindsym`-recognized volume key event reaches Sway, the system
SHALL run the corresponding `wpctl set-volume`/`set-mute` command against
the default sink directly, with no separate signal from Sway to the Rust
shell client -- the shell's own PipeWire graph watcher SHALL be the sole
mechanism that notices the resulting change and raises the HUD, the same
way it would for any other external change. <!-- UNVERIFIED --> Whether
this board's main unit or its optional keyboard/nRF9151 base emits any of
these keysyms today is not established from source; these bindings are
inert until a keyboard that emits them is attached.

*Grounding: `nix/shell.nix`'s `bindsym XF86AudioRaiseVolume/LowerVolume/
Mute` lines (`k230.shell.coherentShell`-gated); design.md Decision 7.*

#### Scenario: A recognized volume key changes the level with no dedicated shell-side handler
- **WHEN** Sway receives an `XF86AudioRaiseVolume`/`LowerVolume`/`Mute` key event
- **THEN** `wpctl` changes the default sink directly, and the Rust shell client's own graph watcher (not a message from Sway) is what notices and raises the HUD

### Requirement: An output device picker lists PipeWire sinks in the expanded HUD and in Settings

*Host build proof: cargo unit tests over `pipewire_ipc::GraphSnapshot::
sinks`/`Sink::is_default`. QEMU capture under `docs/evidence/volume/`.
Host/QEMU proof only; the second (external-route) sink's actual existence
on hardware is `the-handheld-plays-through-its-speaker`'s own open
question, not decided or claimed here.*

The expanded HUD panel and the Settings screen SHALL each list every
PipeWire `Audio/Sink` node currently known (at minimum the Inno codec line-
out), marking the current default, and SHALL let a person pick a different
one via `wpctl set-default ID`. <!-- UNVERIFIED --> Whether `the-handheld-
plays-through-its-speaker`'s external-I2S route ever appears as a second,
separate sink here, versus remaining only an ALSA-level mixer switch with
no distinct PipeWire node, is not established and this requirement does
not assume either outcome -- the picker simply shows however many sinks
WirePlumber actually reports.

*Grounding: `pipewire_ipc::{GraphSnapshot,Sink}`; design.md Decision 8.*

#### Scenario: Picking a different sink changes the default
- **WHEN** more than one `Audio/Sink` node is known and a person picks one that is not currently default
- **THEN** `wpctl set-default` is called with that sink's id, and the graph watcher's next update shows it as the new default

#### Scenario: A single-sink board still shows a picker with one entry, not a broken one
- **WHEN** only the Inno codec's own sink is known
- **THEN** the picker shows exactly that one entry, already marked default, and offers no other choice
