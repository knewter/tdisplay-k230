## Layer

Userspace: NixOS session services (`nix/shell.nix`) plus the Rust shell
client (`nix/rust-shell-client`) and its two new PipeWire-facing child
processes. No kernel, device tree, or Nix module outside `nix/shell.nix`
changes; the audio hardware/device-tree layer is
`the-handheld-plays-through-its-speaker`'s, untouched here.

## Decision 1: Plain systemd system services, not the `services.pipewire`/`wireplumber` NixOS modules

Those modules wire `pipewire.socket`/`pipewire.service`/`wireplumber.
service`/`pipewire-pulse.{socket,service}` into `systemd.user.services`,
which needs a systemd `--user` instance for `shell` to actually run. That
instance is normally started by `pam_systemd` on login or by lingering
(`loginctl enable-linger`); this image has neither -- there is no login
manager, every getty on tty1 is masked (`nix/shell.nix`'s own comment on
`systemd.services."getty@tty1"`), and Sway itself already runs as a plain
system unit with `User = "shell"`, not through a user session. Rather than
add lingering (`systemd.tmpfiles.rules` touching `/var/lib/systemd/linger/
shell`) purely to make one NixOS module's chosen wiring work, three plain
system services (`pipewire`, `wireplumber`, `pipewire-pulse`), each `User =
"shell"`, `bindsTo`/`partOf`/`after = [ "shell.service" ]`, match every
other per-session daemon already in this file (`shell-notifications`,
`theme-helper`, `shell-session-bus`) and need nothing from `systemd-
logind` at all. The only other thing that module would have added --
the two ALSA plugin files redirecting plain ALSA clients through PipeWire
-- are installed the same way it installs them
(`${pkgs.pipewire}/share/alsa/alsa.conf.d/{50-pipewire,99-pipewire-
default}.conf`), by hand.

Rejected: `security.rtkit.enable`. `pipewire`'s `module-rt` asks for
realtime scheduling directly and falls back to logging a warning if
refused (harmless on a single-user board with no other realtime
contention); adding a fourth daemon purely for a priority bump contradicts
the task's own "no extra daemons beyond pipewire, wireplumber and
pipewire-pulse."

## Decision 2: `pw-cli`/`wpctl` child processes, not `pipewire-rs` or a hand-rolled native client

`sway_ipc.rs` hand-rolls Sway's own IPC framing because that wire format is
small, stable and documented (`sway-ipc(7)`). PipeWire's native protocol is
a much larger binary RPC (fds, SPA pods, an object/permission model) with
no equivalently small stable spec to hand-roll, and `Cargo.toml` pins a
short, deliberately narrow dependency list (no `libspa`/`libpipewire` FFI
binding already vetted for this repo's riscv64 cross toolchain). `pw-dump`,
`pw-cli` and `wpctl` are already present the moment `services.pipewire`-
equivalent config ships (they are the same `pkgs.pipewire`/`pkgs.
wireplumber` outputs the systemd units above already pull in), so this
reuses binaries the system already needs, at the cost of one JSON/text
parsing layer instead of an FFI binding. This was checked, not assumed to
cross-compile: `pipewire-riscv64-unknown-linux-gnu-1.6.8` is already built
and cached on the shared build host from unrelated prior work on this
machine, so the cross-compilation risk this design accepts is not
hypothetical -- it is already known to succeed at this exact pin.

Cost: two long-lived children, not one process per change. `pw-dump
--monitor` sits blocked in a `read()` and only wakes when the graph
actually changes -- confirmed directly (a 3-second idle capture on a real
desktop PipeWire session produced no output past the initial dump; a
`wpctl set-volume`/`set-mute` during a second capture produced exactly one
small array per change). The persistent `pw-cli` writer sits blocked
waiting on its stdin pipe and only wakes when this shell sends it a
line. Both are far cheaper than spawning `wpctl set-volume` per drag
sample: a fresh `wpctl` process pays dynamic linking, a new PipeWire
client connection/handshake and process teardown on every sample, all
avoided here. Reading the graph is genuinely free of polling: the reader
thread's own `read()` call is the only wait, and it wakes exactly when
PipeWire has something to say, never on a timer. The one caveat found
directly, not assumed: `pw-cli`'s *interactive* (piped-stdin) command mode
needs on the order of one second after connecting for its own registry to
sync before a `set-param`/`info` against an existing global id succeeds
(its one-shot CLI-argument form waits out this sync internally; the
persistent stdin form does not). This only matters once, at this shell's
own startup -- by the time a person's first drag can possibly happen, the
writer has been alive far longer than that.

Rejected: `pipewire-rs`. Not vetted for this cross toolchain, and its own
dependency surface (bindgen against `libpipewire`/`libspa` C headers) is a
larger, riskier addition than two already-present CLI tools for a shell
this narrow in scope. Revisit if a future change needs finer-grained
native events this text/JSON interface cannot express.

## Decision 3: The read side never treats one `--monitor` array as a complete snapshot

Read directly from PipeWire's own `pw-dump.c` (`dump_objects()`): every
dump, including each one `--monitor` prints after the first, walks the
*entire* known object list but skips any object whose internal `changed`
counter is zero. In monitor mode this means each printed array holds only
what changed since the previous one, confirmed against a live capture (a
single `wpctl set-volume` produced a two-object array: the changed sink
plus an unrelated ALSA device renegotiation event that happened to land in
the same event). `pipewire_ipc::Accumulator` keeps one running map across
the monitor child's entire lifetime for exactly this reason. An earlier
version of this parser applied each array against fresh, empty state,
which silently dropped every sink and stream a given change did not
itself touch -- one node's volume changing made every *other* node vanish
from the shown state on that update. This is the load-bearing reason the
read side is stateful; it is not incidental accumulation.

Removal has its own shape, also checked directly: an object that
disappears from the graph is reported as `{"id": <id>, "info": null}`,
not by omission (omission means "unchanged"). Captured live: a `wpctl`
invocation's own transient PipeWire client connect/disconnect produced
exactly this shape for its `Client` object.

## Decision 4: The cubic percent-to-linear curve, and where it is (and is not) applied

Android's `AudioService` volume-curve tables approximate a cubic taper
rather than a linear gain, because loudness perception is roughly
logarithmic and a linear fader puts most of the audible change in the
bottom quarter of the track. `volume::percent_to_linear`
(`linear = (percent/100)^3`) reproduces that shape. This was checked
against `wpctl` itself, not assumed to match it: on a real desktop
PipeWire session, `wpctl set-volume ID 0.58` (and separately `0.57`)
produced a `channelVolumes` of `0.195114` (`0.42`, `57`, `42` produced
equally exact cubes) -- `wpctl`'s own `VOL[%]` argument is already this
same cubic-perceptual value, not a raw linear gain, which is why the
authoritative commit path (release, mute, hardware keys, device picker)
can hand `wpctl` a plain percent and rely on it to apply the identical
curve, while the throttled live-drag path (writing raw `channelVolumes`
directly, for cost reasons -- Decision 2) must compute
`percent_to_linear` itself so the two paths never visibly disagree at the
handoff between a drag and its own release.

## Decision 5: A separate `muted` flag, not "volume clamped to zero"

Mirrors Android's own panel: dragging the slider to its very bottom (`0`)
sets `VolumeState::muted` and *keeps* the last non-zero level remembered,
so tapping the speaker glyph to unmute restores exactly that level, never
a default. An external report of `0` (someone else silenced the sink) is
treated the same way, so a genuinely-silent external sink shows as muted
here too, not as a zero-but-unmuted slider a person would then have to
drag back up from nothing. This is the reason `VolumeState` is not simply
a `u8` percent: brightness's own slider has no equivalent need (a real
sysfs read is always shown as-is with no separate mute concept), but
volume's Android-parity requirement does.

## Decision 6: The HUD raises for hardware keys and external changes, never for the shell's own visible slider

Mirrors the brightness slider's own toast suppression
(`main.rs::suppresses_action_message`, commit "Suppress the brightness
slider's own success toast"): a gesture already on screen (dragging the
shade's or Settings' own slider) needs no second surface telling the
person what they can already see happening. `volume::ChangeOrigin`
enumerates exactly the origins this shell can distinguish
(`OwnSlider`/`HardwareKey`/`ExternalGraph`) and `raises_hud()` is the one
place that decision lives, so `main.rs` never re-derives it ad hoc at each
call site.

**Known, still-open gap** (`tasks.md` 4.3): the HUD's own visibility
state and touch dispatch are fully route-independent, but the surface it
paints onto today is not -- `render.rs`'s `draw_with_hud` only runs while
the overlay layer (Drawer/Shade/Settings) is already mapped. A hardware
key pressed with nothing open updates the graph/slider state correctly but
shows no HUD until some sheet happens to be open. Closing this needs the
overlay layer to map itself purely because the HUD wants to show,
regardless of route -- left as a named follow-up, not solved here.

## Decision 7: Hardware/keyboard volume keys go straight to `wpctl`, not through a private signal to the Rust client

Sway's own `bindsym XF86AudioRaiseVolume/LowerVolume/Mute` each `exec` a
`wpctl set-volume`/`set-mute` call directly. No new socket, IPC message or
signal from Sway to the Rust client exists or is needed: the client's own
`pw-dump --monitor` reader (Decision 2/3) observes the resulting Props
change exactly the way it would observe any other external app's change,
and `ChangeOrigin::ExternalGraph` (Decision 6) raises the HUD from that one
code path. A hardware key is, from this shell's point of view, simply
another external graph change with a very short causal chain.

Rejected: a dedicated `k230-volume-key` helper that both changes the
volume *and* signals the shell directly (e.g. over `SWAYSOCK` or a new
Unix socket). This would duplicate the exact update path the graph
watcher already provides, for no benefit -- the graph watcher's own
latency (an OS-scheduled wake on the monitor child's pipe becoming
readable) is not meaningfully slower than a purpose-built signal would be,
and a second path is a second thing that can disagree with the graph.

## Decision 8: The output device picker models the external I2S route as an ordinary sink pick

Whether `the-handheld-plays-through-its-speaker`'s external-I2S switch
ever surfaces as its own WirePlumber node/profile (as opposed to only an
ALSA-level "External I2S Output Switch" mixer control with no separate
PipeWire-visible sink) is that change's own open question, not decided
here. This change's device picker only ever lists whatever `Audio/Sink`
nodes WirePlumber actually exposes and calls `wpctl set-default ID` on the
one a person picks -- it adds no separate Settings toggle for the
external route, so the two changes compose regardless of which way that
question resolves. If the external route never becomes a separate sink,
the picker simply never shows a second entry, and that mixer switch stays
`the-handheld-plays-through-its-speaker`'s own Settings-toggle decision to
make, not something this change should pre-empt.

## Decision 9: A trimmed `pipewire.override`, not the stock nixpkgs package

Measured directly (`docs/evidence/volume/closure-size.md` -- via
`nix-store -q --size` summed over a `nix-store -qR` closure listing; that
file also records why `nix path-info -rS` reported grossly wrong per-path
sizes on this specific store and should not be trusted here): nixpkgs'
stock `pipewire` package cross-compiled for this board builds with every
optional backend on -- Bluetooth (`bluez` plus its LC3/LDAC/aptX codec
libraries), Vulkan, X11 (which also pulls in `libcanberra`/`libmysofa`),
RAOP/AirPlay, ROC network streaming, and mDNS/Avahi discovery -- and its
own package closure is about 0.44 GiB on this toolchain. None of that is
used by this board's volume UX (ALSA line-out plus the PulseAudio-compat
shim for mpv), and this board has no onboard Bluetooth at all
(`docs/research/bluetooth-onboard.md`), so a Bluetooth-capable audio server
would be actively misleading about what this hardware can do, not merely
wasteful. `nix/shell.nix`'s own `pipewireLean` binding disables the six
backends nixpkgs exposes as plain override booleans
(`bluezSupport`/`vulkanSupport`/`x11Support`/`raopSupport`/`rocSupport`/
`zeroconfSupport`), and `wireplumberLean = pkgs.wireplumber.override
{ pipewire = pipewireLean; }` (WirePlumber links against PipeWire
directly, so it needed the same override, not just the systemd units'
own `ExecStart`/`PATH` references) -- the same "measure a real cost, then
cut what this board doesn't use" reasoning `swayBase`'s own
Xwayland-disabled override already established in this file.

**Measured just as directly: this override pair produces no net reduction
in this board's actual whole-system closure.** Three full toplevel builds
(`docs/evidence/volume/closure-size.md`) traced why: `bluez` and the other
disabled backends' own dependencies are already reachable from elsewhere in
this image regardless of pipewire (`hardware.bluetooth.enable = true`,
landed separately by `the-handheld-talks-bluetooth`, most directly), and a
NixOS-internal ALSA-plugins aggregate this repo's own nix files do not
build or control still pulls in the *stock*, untrimmed `pipewire` package
independent of what `pipewireLean`/`wireplumberLean` or any service unit
here actually run -- confirmed by finding the stock package still present,
referenced from an `all-plugins` derivation, in the final closure. Kept
anyway: every process this change itself spawns (the three systemd units,
and the persistent `pw-cli`/`pw-dump` children `pipewire_ipc.rs` spawns)
genuinely runs the trimmed package, which stays the architecturally correct
and more honest choice (a board with no onboard Bluetooth should not run a
Bluetooth-capable sound server, whatever a different, out-of-scope NixOS
aggregation mechanism does elsewhere in the same image) even though the
board-wide closure number did not move. Fully closing that remaining gap
is a named, open follow-up (`docs/evidence/volume/closure-size.md`'s own
last section), not something this change claims to have solved.

Separately not eliminated: `ffmpeg`/`gstreamer` support and the `docs`/
`installed_tests` outputs. Nixpkgs 1.6.8's own `package.nix` hardcodes
`(lib.mesonEnable "ffmpeg" true)`/`(lib.mesonEnable "gstreamer" true)` in
its `mesonFlags` list rather than exposing them as override parameters, and
`ffmpeg-headless`/`gst_all_1.gstreamer` are unconditional (not
`lib.optional`-gated) build inputs -- trimming them means forking the
derivation's own `mesonFlags`/`buildInputs` construction, not a supported
override, and was judged not worth that fragility (a nixpkgs version bump
could silently re-widen or break a hand-patched flags list with no build
failure to notice it).
