## Context

Display power today: `nix/power-keyd/power_keyd.py` grabs the PMU key and runs
`swaymsg output * power on|off`, syncing from `get_outputs` before each press.
logind ignores the key. Brightness is the single backlight's `brightness`
file; `k230-settings` and `ServiceRequest::BrightnessLive` write it as the
`shell` user. Sway (1.12 here) supports ext-idle-notify-v1 and `inhibit_idle`.

## Decisions

### swayidle drives timers; a small Python helper owns the state

`swayidle -w timeout 30 <dim> resume <resume> timeout 60 <off>` is event
driven (no polling) and honours Sway's idle inhibitors for free. Each hook runs
`k230-idle-dimmer dim|off|resume|wake`, one short process that reads and writes
`/run/shell/idle-dimmer.json`. The logic is a class tested on the host with a
fixture backlight and a fake `swaymsg`.

### Dim is relative, restore is conditional

`dim` writes `max(1, round(25% of the current raw value))` and records the
saved and written values; if that would not lower the value (raw 0 or 1) it
does nothing. `resume` restores the saved value only when the backlight still
holds the value `dim` wrote, so a slider change made while dim is never
overwritten. Dim twice is a no-op, so the dimmed value is never dimmed again.

### Off is the power key's command

`off` runs `output * power off`, the same command power_keyd uses. power_keyd
re-reads Sway's output state before every press, so after an idle blank the next
short press correctly turns the display on.

### The power key's wake must tell the idle machinery

power_keyd grabs the key, so Sway sees no activity and swayidle would stay idle
after a power-key wake, leaving the panel dim. After lighting the display (short
press, or hold from dark) power_keyd runs `k230-idle-dimmer wake`: resume, then
`seat * cursor move 0 0`, which Sway counts as pointer activity and which makes
swayidle resume and re-arm. The zero move is a workaround for having no
"activity" command; UNVERIFIED that it re-arms on the board. A wake that bypasses
both (the HDMI-unplug wake in the touch relay) leaves the panel dim until the
first input; accepted and listed as a follow-up.

### Inhibit with Sway rules, on focus

`for_window [app_id="^k230-timer$"] inhibit_idle focus` and the same for
`^k230-video-` (the mpv ids `k230-video-software` / `k230-video-mvx`). `focus`
rather than `visible`: cards stack as floating full-size windows, so "visible"
may hold for a card that is covered. Whether `focus` tracks the card-shell's
Home and overview transitions is UNVERIFIED. The Rust shell's wallpaper video
(`video_visibility.rs`) is not an inhibitor: it plays on Home, and inhibiting
there would mean Home never sleeps.

### A dark-panel touch is consumed in the compositor

The touch hooks in the Sway patch call `card_shell_down/motion/up` first; a
true result stops delivery. A header-only `wake_gate` (host-tested) tracks
contact ids: a down while Sway's output power is off (`wlr_output->enabled`
false on the enabled output, the "power" of `get_outputs`) opens a swallowed
sequence, lights the display with `execute_command("output * power on")`, and
consumes that contact, contacts that join it, and their motion and release.
Contacts that began while lit are never swallowed. `card_shell_cancel` clears
the gate. Sway calls `seat_idle_notify_activity` before the seatop hook (cursor.c),
so the swallowed touch also makes swayidle resume and restore brightness.
Whether libinput/wlroots still delivers touch to Sway on a powered-off output
is UNVERIFIED and is the first thing the board run checks.

### Settings row deferred

A timeout choice needs a persisted value the swayidle command line can read at
start, plus a Rust service and Settings row. That is separable and not needed to
make the display rest; it is a task, not part of this slice.

## Risks / Trade-offs

- The compositor edit is not compiled here; a card-shell build is the first
  gate. `execute_command`, `modeset_is_pending`, `force_modeset` and
  `transaction_commit_dirty` are used as `ipc-server.c` uses them.
- `output * power on` from inside a touch handler runs a modeset in the input
  path; wake latency on glass is unmeasured.
- Fixed 30/60 s is also the policy while charging; no charger exemption.
