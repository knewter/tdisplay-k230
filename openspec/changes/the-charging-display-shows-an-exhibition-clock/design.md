## Context

Idle today: `shell-idle` runs `swayidle -w timeout 30 dim resume resume
timeout 60 off` against `k230-idle-dimmer` (`nix/idle-dimmer/idle_dimmer.py`),
which is event driven and never polls; Sway's idle inhibitors (Timer, video)
veto the timers. Terminal apps are Python in `nix/term-apps/k230_term_apps.py`
run in Foot as `k230-foot terminal --app-id=... -e ...`; the Clock app redraws
every second. The charger is the bq25890 `power_supply` (`ONLINE=0` read on
battery, `docs/evidence/battery-details-widget/board/README.md`; the shell's
`home_widgets.rs` `Input.online` already reads that attribute). The shell's own
preferences live as one-word files in `/var/lib/k230-shell-prefs`
(`shell_prefs.rs`). The board has one online CPU, so every wake-up counts.

Layers: userspace Python (idle step, card), Rust shell client (Settings row),
Nix (packaging and wiring). No kernel, device tree or compositor change.

## Decisions

### When it runs: charging and idle, otherwise nothing changes

At the 30 s hook `k230-idle-dimmer dim` still dims, then, when the preference
is Clock and a non-battery `power_supply` reports `online` 1, launches the
exhibition. At the 60 s hook `off` does nothing while the exhibition is up and
the charger is still online. Charger state is read from sysfs at each hook, not
watched: swayidle fires each hook once per idle period, so a charger change
after the hook ran must be noticed by the exhibition process, which rechecks
every 10 s (a sysfs read; no uevent listener, no D-Bus). On unplug the card runs
`k230-idle-dimmer exhibit-end`, which runs the normal `off` after the card has
closed. That may blank before 60 s of idleness (a person unplugging at 40 s sees
the panel go off at once); accepted as simpler than re-arming a timer.
"Online" means any supply that is not the Battery and has `online` 1; the
bq25890's `type` string and whether a keyboard base or HDMI source changes it
are UNVERIFIED until read on the board.

### The exhibition is a window, so touch and keys land in it

Alternatives were a compositor overlay (a second consumer of the touch gate,
needing a card-shell build) and a Home view in the Rust shell (a new mode for a
client that has no idle state). A Foot card needs neither: it takes focus when
launched, so touch and keys are delivered to it and to nothing else. The program
treats the first byte of input as dismissal; when that is a mouse press it then
waits up to 0.4 s for the release, so the whole contact stays inside the card
and the app underneath never sees an orphan release. Then it exits and Foot
closes. `swaymsg exec` starts it (`k230-foot terminal --app-id=k230-exhibition
-e k230-exhibition ...`). Which card Sway or the card shell puts in front when it
closes, and whether Foot turns a touch into mouse reports, are UNVERIFIED.

`resume` is not told to close the card: the same input that wakes the display
reaches the card, and killing it first would drop the release. The one case it
handles is waking from dark (the power key, or a swallowed touch on a blanked
panel), where nothing reached the card; `resume` then terminates it. Pointer
motion alone (an HDMI mouse) restores brightness and leaves the card up;
accepted, a follow-up.

### Pacing: one redraw a minute, an effect every five

The clock has no seconds and no progress bar, so it changes once a minute and
the card sleeps in `select` otherwise (10 s ceiling for the charger and display
checks). Effects run through `ttfx --frame-rate 15` with the text centred, for
at most 20 s, then the banner holds 4 s and the clock returns. Effects come from
a fixed rotation of finite ones, not `--random-effect`, so the cost is bounded
and the sequence testable. Foot draws on a pixman compositor with no GPU, so
every ttfx frame is a CPU repaint of the card on the only CPU. Budget,
UNVERIFIED until measured: clock-only phase under 1% of the CPU over 60 s; effect
phases may take most of it for their duration but each ends within 20 s. If the
measurement is worse, lower the frame rate to 10, then remove effects from the
rotation, before shipping a default of Clock. While the display is off (read from
the DRM connector's `dpms`; that path is UNVERIFIED) the card does not redraw.

### Burn-in: a bounded wander each minute

`drift(minute, ...)` picks the clock's offset from a fixed sequence of
(column, row) steps, so successive minutes never sit in the same spot and the
clock never leaves the screen. The digits use the dim attribute on top of the
25% backlight. The card never shows a static element for more than a minute.

### Text: a committed banner file

`nix/exhibition/K230.txt` is a hand-set six-row banner of the four characters
in the "ANSI Shadow" figlet style Omarchy's own branding uses: full blocks and
box-drawing lines, which foot draws itself, so no font has to carry them. It is
fed to `ttfx -i` on a full-width canvas one row short of the terminal, both
anchors at the centre (Omarchy's screensaver invocation), with
`--no-restore-cursor` so the cursor stays hidden after the effect. No figlet
dependency. The first board run used a five-row `#` banner anchored at the
default `sw` corner; it drew at the top left with a cursor under it.

### Preference: one word, default Clock

`/var/lib/k230-shell-prefs/idle-on-charger` holds `clock` or `sleep`. Missing or
unrecognised means Clock, unlike Do Not Disturb, because the user asked for the
feature and a stale file should not silently remove it. The idle step reads it
at each hook. The Settings row writes it. Python and Rust each read the same
file and each has tests for the missing and corrupt cases.

### Cap: two hours

A clock lit all night is the burn-in risk the drift only reduces. After two
hours the card ends as an unplug does: close, then `off`. A setting for the cap
is a follow-up.

### On battery: no screensaver

Considered: an exhibition of 10 to 20 s before the dim on battery. Rejected: the
AMOLED draws power in proportion to lit pixels and the animation repaints on the
only CPU, so it spends battery to show a person nothing they asked for. The same
reasoning makes the exhibition conditional on the charger.

### Rejected

- `--random-effect`: unbounded cost; some effects run until the terminal is
  resized or killed.
- Running the Clock app: it redraws each second and has a progress bar, both bad
  for burn-in and CPU.
- Always on (no cap, no unplug exit): the display never rests.
- A new `shell-exhibition` service: the work is a one-shot started by an existing
  hook and ended by input or the charger; a daemon would be a second idle clock.

## Risks / Trade-offs

- The card takes focus. If the card shell treats it as an ordinary app, the
  overview may list it while it runs. It closes on any input, so this is brief.
- `swaymsg exec` inherits Sway's environment; Foot started from there may differ
  from the launcher's. UNVERIFIED.
- Timer and video veto idle, so they also veto the exhibition; correct.
- The dismissing touch is consumed, so a person who wanted Home must tap again.
  That is the stated requirement.
