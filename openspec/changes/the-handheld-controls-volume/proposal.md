## Why

A person on this handheld has no on-screen way to see or change how loud
anything is. Volume can only move by editing an ALSA mixer control from a
console, and nothing on the panel shows the current level, which app is
making noise, or which output device is in use. `the-brightness-control-is-a-
slider` gave the shade and Settings a shared Material-3 slider component for
brightness; the same review that asked for that
(`docs/design/shell-polish-review-2026-09.md`) compares this shell's Quick
Settings surface to Android's throughout, and Android's own Quick Settings
shade puts a volume slider directly under the brightness one, plus a
key-triggered HUD for out-of-band changes. Nothing here plays that role yet.

Before this change, the image also does not run a sound server at all:
`grep -rn pipewire nix/` finds one `pipewireSupport = false` in
`nix/video-probe.nix` (mpv's own build) and nothing else. mpv talks to ALSA
directly (`alsaSupport = true`, `pipewireSupport = false`,
`pulseSupport = false` in that same file), which is fine for one process
owning the one Inno-codec ALSA device outright, but gives no place for a
shell-level volume control to live, no way to see per-app streams, and no
way to route to more than one output. This change adds PipeWire +
WirePlumber (`nix/shell.nix`, gated on `k230.shell.coherentShell` the same
as every other per-session daemon there) as plain system-level systemd
services running as the `shell` user -- not the `services.pipewire`/
`services.wireplumber` NixOS modules, which wire into a systemd `--user`
instance this image never starts (no login manager, no session lingering;
Sway itself already runs as a plain system unit). mpv is not rebuilt; it
keeps talking to ALSA, and two installed ALSA plugin config files
(`${pipewireLean}/share/alsa/alsa.conf.d/{50-pipewire,99-pipewire-
default}.conf` -- `pipewireLean`, not the stock `pkgs.pipewire`; see below)
transparently redirect that ALSA traffic through PipeWire, so mpv's own
output becomes an ordinary PipeWire stream node with no change to
`nix/video-probe.nix` at all. `pipewireLean`/`wireplumberLean` disable six
optional PipeWire backends (Bluetooth, Vulkan, X11, RAOP, ROC, mDNS) this
board's volume UX never uses and this board has no onboard Bluetooth at
all (`docs/research/bluetooth-onboard.md`) -- measured directly
(`docs/evidence/volume/closure-size.md`) to produce **no net reduction**
in this board's actual whole-system closure for two independent, traced
reasons recorded there, kept anyway because every process this change
itself runs still uses the trimmed package (design.md Decision 9).

`the-handheld-plays-through-its-speaker` (open, not yet archived) adds a
`system/audio` capability describing the Inno codec's default route and an
opt-in external-I2S switch for an optional MAX98357A amplifier; both are
board-side (kernel/device-tree) concerns, unaffected by this change. This
proposal adds its own `system/audio` requirements alongside that change's,
for the PipeWire/WirePlumber layer and the shell surfaces built on it --
volume control, live-graph awareness, the HUD, and an output device picker.

## What Changes

- **PipeWire/WirePlumber, for the shell session only.** `nix/shell.nix`
  gains `systemd.services.pipewire`/`wireplumber`/`pipewire-pulse`, each a
  plain system unit (`User = "shell"`, `XDG_RUNTIME_DIR=/run/shell`),
  `bindsTo`/`partOf` on `shell.service` the same way `shell-notifications`
  and `theme-helper` already are. No `security.rtkit.enable` (module-rt
  falls back to asking for RT scheduling directly and logs a warning
  instead) -- exactly the three processes the task asks for, nothing more.
  Two ALSA plugin config files redirect mpv's existing direct-ALSA output
  through PipeWire without touching the mpv derivation.
- **A volume slider under the brightness slider**, in the shade and in
  Settings, reusing `slider.rs`'s existing Material-3 track/thumb painter
  and touch-band machinery rather than forking it. `slider.rs` gained a
  `floor`-parameterized form (`clamp_percent_with_floor`,
  `value_at_x_with_floor`, `Drag::start_with_floor`) alongside its existing
  brightness-only wrappers, so brightness's 3%-floor behavior is unchanged
  and the volume slider's own floor is `0` (true silence is a reachable
  value; muting is a separate flag -- `volume::VolumeState`). A tap on the
  speaker glyph toggles mute without disturbing the remembered level.
- **An Android-style perceptual volume curve**, not a linear one:
  `volume::percent_to_linear`/`linear_to_percent` implement the cubic taper
  (`linear = (percent/100)^3`) Android's own volume-curve tables approximate,
  so equal slider steps read as roughly equal loudness steps. `wpctl`'s own
  `set-volume`/`get-volume` were checked directly against this board's dev
  host (`wpctl set-volume ID 0.58` produces a PipeWire `channelVolumes` of
  `0.195114`; `0.58^3 = 0.195112`), confirming `wpctl` itself already applies
  this exact curve -- this module's own curve is for the shell's live-drag
  writes, which bypass `wpctl` for cost reasons (below), and must agree with
  it or a drag and the following authoritative commit would visibly jump.
- **One persistent `pw-cli` writer, not a process per change.** A live
  drag's throttled writes (`slider::live_write_due`'s ~25/s cadence, reused
  unchanged) go to one long-lived `pw-cli` child's stdin
  (`pipewire_ipc::WriterHandle`, a `set-param <id> Props '{ "channelVolumes":
  [...] }'` line per write, verified against a real PipeWire session:
  `pw-cli`'s interactive/stdin command mode needs roughly one second after
  connecting for its registry to sync before a `set-param`/`info` targeting
  an existing id succeeds -- `pw-cli`'s one-shot CLI-argument form waits out
  that sync internally, but the persistent stdin form does not, which only
  matters once at this shell's own startup, not per write). A drag's
  release, a mute toggle, a hardware volume key and the device picker all
  go through short-lived, human-percent `wpctl set-volume ID <percent>%`/
  `set-mute ID 0|1|toggle`/`set-default ID` calls instead -- rare,
  user-paced events, not per-sample -- mirroring the brightness slider's own
  "throttled direct write while dragging, one authoritative call on
  release" split (`docs/evidence/volume/` has the exact commands and
  captured `wpctl`/`pw-dump` output this was checked against).
- **Watching the PipeWire graph for external changes.** One persistent
  `pw-dump --monitor` child (`pipewire_ipc::spawn_monitor`) is read
  incrementally off its stdout pipe (`serde_json`'s own streaming
  deserializer, already a pinned dependency -- no new crate). `pw-dump
  --monitor` prints one full array at connect and, from then on, only the
  objects that changed on each event (confirmed directly against upstream
  `pw-dump.c`'s `dump_objects()`, and against a live capture: a `wpctl
  set-volume`/`set-mute` on this dev host's own PipeWire session produced a
  1-2 object array, never a full re-dump), and a removed object appears as
  `{"id": <id>, "info": null}` rather than being omitted (also captured
  directly). `pipewire_ipc::Accumulator` keeps one running graph across the
  child's whole life for exactly this reason -- an earlier draft of this
  parser treated every array as a complete snapshot and silently dropped
  every sink/stream a given change did not itself touch.
- **An Android-style volume HUD** (`volume::Hud`): a vertical pill on the
  right edge, shown for any change this shell did not itself just make on
  its own visible slider (`volume::ChangeOrigin::raises_hud` -- a hardware
  key or an external graph change raises it; the shade/Settings slider's own
  drag does not, since it is already its own visible feedback, mirroring the
  brightness slider's own toast suppression). Auto-hides after 2.5s
  (`volume::HUD_AUTO_HIDE_MS`, the middle of the task's "about 2-3s"), can be
  dragged along the edge (`Hud::start_drag`/`drag_to`/`end_drag`, touch-id
  owned the same way `slider::Drag`/`Carousel`/`PanelClose` already are),
  and expands via a "…" affordance to a per-stream list -- one row per
  PipeWire `Stream/Output/Audio` node, each with its own slider, app name
  (`application.name`) and icon (`application.icon-name`, the real
  `PW_KEY_APP_ICON_NAME` -- checked directly against this machine's
  installed `pipewire/keys.h`, not the underscored spelling a first guess
  might reach for) where resolvable, falling back to the node's own name.
- **Hardware/keyboard volume keys**, wired through Sway `bindsym`
  (`XF86AudioRaiseVolume`/`LowerVolume`/`Mute`) straight to `wpctl`, not
  through a private signal to the Rust client -- the client's own graph
  watcher picks up the resulting change exactly the same way it would pick
  up any other external change, so hardware keys need no separate plumbing.
  `docs/research/board-capability-inventory.md` documents no dedicated
  volume buttons on the main board and no landed keymap for the optional
  keyboard/nRF9151 base's TCA8418 matrix that would emit these keysyms;
  this remains a hook for a keyboard that does, not a claim this board's own
  keys exist.
- **An output device picker**, in the expanded HUD and in Settings, listing
  every PipeWire `Audio/Sink`: the Inno codec line-out always, and the
  external-I2S route from `the-handheld-plays-through-its-speaker` if and
  when that change's kernel patch lands and WirePlumber exposes it as a
  separate node/profile -- modeled as an ordinary sink pick
  (`wpctl set-default ID`), not a new Settings toggle, so the two changes
  compose without either needing to know about the other's UI. Whether the
  external route in fact appears as a separate WirePlumber sink or only as
  the ALSA-level "External I2S Output Switch" control that change adds is
  still open and is recorded, not assumed, in `docs/evidence/volume/`.

## Non-goals

- No claim that this board has a working loudspeaker or that the external
  I2S route is audible -- that is `the-handheld-plays-through-its-speaker`'s
  own, still-open UNVERIFIED claim. This change's own audible-output tasks
  (line-out through headphones, and the external route if present) are left
  open below.
- No change to the theme picker (`theme_ui.rs`, `theme_carousel.rs`,
  `theme_thumbnails.rs`, `theme_catalog.rs`, `appearance.rs`) or the app
  drawer (`navigation.rs`'s drawer paths, the drawer render, `drawer_close_
  drag_zone`) -- both owned by other concurrent work.
- No rebuild of mpv and no new gstreamer/JACK/Bluetooth-audio plumbing --
  PipeWire's ALSA-compat layer is the entire integration surface mpv needs.
- No `pipewire-rs`/native-protocol client and no `security.rtkit.enable`;
  see design.md for why each was rejected.
- Real-finger board acceptance, real hardware-key acceptance, and any
  audible-output check are explicitly left open; see tasks.md. This
  worktree does not touch the board or `/dev/ttyACM0`.

## Capabilities

### New Capabilities

- `system/audio`: this change's own delta adds the PipeWire/WirePlumber
  session layer and the shell-side volume UX built on it (slider, HUD,
  device picker, live-graph awareness) as `ADDED Requirements` against this
  not-yet-archived capability -- the same posture
  `the-handheld-plays-through-its-speaker` takes for its own, disjoint
  Inno-codec/external-I2S requirements. Whichever of the two changes
  archives first is the one that actually creates
  `openspec/specs/system/audio/spec.md`; the other's archive then lands as
  an ordinary further `ADDED Requirements` delta against the now-existing
  capability. Neither change modifies or removes a requirement the other
  owns.
