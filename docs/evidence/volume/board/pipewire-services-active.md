# Board result: PipeWire services active, two real bugs found and fixed

Evidence class: **board observation, relayed** -- the coordinator ran this
directly against a flashed/test-activated board (system
`z3zbk6gx8j5gd2pzamrzg5vapa0bjwnd`, this branch's own commit before the
fixes below) and reported the result back; this worktree never touched
`/dev/ttyACM0` or the board itself (AGENTS.md). What follows is the
coordinator's own report, not a console transcript captured here -- a
weaker citation than a committed boot log, but still a tier-1 board
observation, not an inference.

## What was confirmed working

`pipewire`, `wireplumber`, and `pipewire-pulse` are all reported `active`
on the board (task 1.4's first half).

## Bug 1: only a "Dummy Output" sink

The `shell` user was not in the `audio` group (`id shell` showed
`shell, video, input, seat` only), and `/dev/snd/*` ships `root:audio
0660` -- WirePlumber's ALSA monitor could not open card 0 (`K230_I2S_
INNO`) at all. The coordinator confirmed the diagnosis directly: a
temporary `chmod o+rw /dev/snd/*` plus restarting the three services
produced `Built-in Audio Stereo` as the real default sink/source; that
chmod does not survive a reboot.

**Fix**: `nix/shell.nix`'s `users.users.shell.extraGroups` now includes
`"audio"`, declaratively -- the same group `/dev/snd/*`'s own udev rule
already grants access to, with no per-unit `SupplementaryGroups` override
needed since every PipeWire-adjacent process already runs as `User =
"shell"`.

## Bug 2: `wpctl`/`pw-dump`/`pw-cli` unreachable from the running client

`wpctl` was on neither the system PATH nor the Rust client's own PATH
(its `/proc/<pid>/environ` had no wireplumber path) -- every mute tap,
drag-release commit, and device-picker pick would have failed silently on
the board. Checked directly (not just assumed) against the exact built
unit file for system `z3zbk6gx`: `shell-ui.service`'s own generated
`Environment=PATH=...` line *did* already include both `wireplumberLean`
and `pipewireLean`'s `bin/` directories (this change's earlier `path =
[...]` addition to that unit). Why the live process still did not see
this is not resolved here -- rather than keep depending on `PATH` search
working end to end for something this important, `wpctl`/`pw-dump`/
`pw-cli` are now also passed as absolute store paths via their own
`K230_WPCTL`/`K230_PW_DUMP`/`K230_PW_CLI` environment variables (the same
"substitute the real path at build time" convention `K230_SETTINGS`/
`K230_SWAYMSG` already use in this file), which is what `main.rs`'s own
`std::env::var_os("K230_WPCTL")`-style reads already preferred over a bare
`PATH` lookup. `path` is left in place as a fallback, not removed.

Separately: this shell's own persistent `pw-dump --monitor`/`pw-cli`
children were spawned with `.ok()` swallowing any spawn error with no log
line at all -- exactly the kind of silent failure that makes "is the
persistent helper actually starting?" unanswerable from a journal alone.
Both spawns now `eprintln!` (captured into this unit's own journal, the
same convention every other early-startup failure in `main.rs::serve`
already uses) before discarding into `.ok()`.

## The rtkit/session-bus warnings

`module-rt` logged that it could not reach a session bus at all (not just
"no RTKit registered on one"), because none of the three units set
`DBUS_SESSION_BUS_ADDRESS`. All three now connect to the same
`shell-session-bus` every other per-session daemon in this file already
uses. `security.rtkit.enable` remains deliberately unset (design.md); the
expected outcome after this fix is `module-rt` reaching a real bus and
getting a clean "no such service" from it, not "no bus at all" -- still
harmless, per the coordinator's own acceptance of that outcome. No other
WirePlumber module this image actually enables (ALSA monitor, default
policy/routing) needs D-Bus for basic sink/source management; only the
optional Bluetooth and MPRIS-style modules would, and neither is enabled
here (`pipewireLean`'s `bluezSupport = false`; no MPRIS module configured).

## What this file does not establish

None of the fixes above have themselves been re-verified on the board yet
(that needs another board test cycle this worktree cannot run). Task 1.4
stays open until that happens. This file records the *diagnosis* and the
*fix*, both grounded in the coordinator's direct board report and this
change's own re-inspection of the exact unit file that was tested, not a
claim that the fix has been confirmed working on hardware.
