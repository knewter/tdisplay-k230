## Context

`plugging-in-hdmi-moves-the-display` establishes that HDMI is, today and
for the foreseeable near term, a *reboot-based device-tree swap*, not a
live no-reboot switch (its own task group 4 is explicitly speculative and
may never land, per that change's design.md decision 4). So at any given
moment exactly one of the panel (`DSI-1`) or the bridge (`HDMI-A-1`) is the
connector Linux is actually driving, and that fact is visible in
`/sys/class/drm/*/status` without needing Sway, a reboot marker, or
anything this change would have to invent.

The touchscreen itself is unaffected by which DTB booted: the GT9895 is
wired independently of the DSI/HDMI mux question (its own I2C bus, its own
GPIO23/24 lines — shared with the LT9611's reset/interrupt per
`plugging-in-hdmi-moves-the-display`'s `display/touch` delta, but that
sharing is about *power/interrupt contention*, not about whether the touch
*driver* is loaded; nothing in that change's device-tree work removes the
GT9895 node from either DTB). The touchscreen keeps producing ordinary
`ABS_MT_*` events regardless of which display output is live; the only
thing that needs to change is what consumes them.

## Goals / Non-Goals

**Goals:** let a person use the touchscreen glass as a laptop-style
trackpad for the HDMI session — relative pointer motion with acceleration,
tap-to-click, two-finger scroll, pinch-zoom, and multi-finger swipes — with
no manual mode switch; keep the coordinator's direct absolute-touch path
for panel mode completely unaffected; prove the design's mechanism on the
host to the extent host evidence can reach.

**Non-goals:** implementing or depending on no-reboot HDMI hot-plug
automation; tuning libinput's gesture/acceleration defaults; a hardened
non-root permission model (see "Permissions" below); wiring the resulting
NixOS module into the shipped configuration (left for the coordinator once
an HDMI session exists to try it against); any change to the touchscreen's
existing direct-mode behavior or its `display/touch` digitizer-range
requirement.

## Decisions

### 1. Re-emit as a virtual *touchpad*, not a synthesized relative-pointer stream

Three designs were evaluated for turning the touchscreen into something
HDMI-session-useful:

**(a) A uinput daemon that grabs the touchscreen and itself computes
relative pointer motion + buttons + scroll**, i.e. the daemon *is* the
gesture recognizer (tracks finger count and velocity, decides tap vs.
drag vs. scroll, emits `REL_X`/`REL_Y`/`BTN_LEFT`/`REL_WHEEL` on a virtual
mouse device). This is the most common pattern for "make an unusual input
device act like a mouse" (it's what most touchscreen-as-trackpad hacks and
several `evdev`/`python-evdev`-based tools online do). *Rejected as the
primary design*: it means re-implementing, by hand, a worse version of
tap-timing, palm rejection, multi-finger disambiguation, scroll-vs-pointer
arbitration, and acceleration curves that libinput already ships,
extensively tuned, in the exact code path Sway already runs. Pinch-zoom
and arbitrary multi-finger swipes specifically are libinput *pointer
gesture* frames (`libinput_event_gesture_*`, delivered to Wayland clients
via `wp_pointer_gestures_v1`) — a hand-rolled relative-motion daemon would
have to reimplement that protocol surface entirely to get pinch/swipe at
all, which the operator explicitly asked for ("like a real laptop
touchpad").

**(b) Existing projects** (`ydotool`, generic `python-evdev`/`evdev-rs`
touchpad emulators, or driving input via the wlroots
`zwlr_virtual_pointer_v1` Wayland protocol from a client instead of
`uinput`). *Rejected*: `ydotool` and the common `evdev`-based emulators are
all instances of design (a) — same reimplementation problem. The
`zwlr_virtual_pointer_v1` route moves the synthesis from kernel-level
`uinput` to a Wayland client talking directly to Sway/wlroots, which
removes the `uinput` permission question but *only* exposes a relative/
absolute pointer protocol (motion + buttons + optional discrete scroll) —
it has no multitouch/gesture-frame surface at all, so it cannot deliver
pinch-zoom or swipe gestures to Wayland clients either; it would still
need this program to invent gesture recognition, and would additionally
tie the whole design to one Wayland compositor's client library instead of
a device any compositor's libinput already understands.

**(c) A compositor-side patch** (recognizing gestures from raw touch
events inside Sway/wlroots itself, bypassing libinput's touchpad path
entirely). *Rejected*: this is strictly more invasive than either uinput
option (patching and tracking a wlroots/Sway fork) for no capability this
project doesn't already get for free from libinput once it's *shown* a
touchpad-shaped device; also removes the "grab the raw device, everything
else is unaffected" isolation the other two options have.

**Chosen: (a')**, a variant of (a) that does not compute motion or
gestures at all. The re-emission device declares itself as a touchpad
(`INPUT_PROP_POINTER` + `INPUT_PROP_BUTTONPAD`, no `INPUT_PROP_DIRECT`,
`BTN_TOOL_FINGER`/`_DOUBLETAP`/`_TRIPLETAP` capability) and forwards the
touchscreen's real `ABS_MT_SLOT`/`_TRACKING_ID`/`_POSITION_X`/`_POSITION_Y`
stream through unchanged, synthesizing only the finger-count-derived
`BTN_TOUCH`/`BTN_TOOL_*` transitions a real touchpad's own driver would
also be reporting. libinput's own `evdev_configure_device()` then
classifies the device as a touchpad from those bits alone — verified on
the host (not the board; see "What this design does and does not prove"
below) via udev's identical classifier:
`docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/host-uinput-classification.md`
shows `ID_INPUT_TOUCHPAD=1` on the created device, no
`ID_INPUT_TOUCHSCREEN`. From there, pointer acceleration, tap-to-click,
two-finger scroll, and pinch/swipe gesture frames are entirely libinput's
existing, already-shipped code paths — identical to what a real laptop
touchpad gets. `nix/touch-trackpad/src/relay.rs` is the whole translator;
it is deliberately *not* a gesture state machine, and its host tests
(`cargo test`, 20/20 passing) check exactly that narrow claim: given a
synthetic 1/2/3-finger contact sequence, does it emit the right
`BTN_TOUCH`/`BTN_TOOL_*` transitions at the right point in the frame,
without ever touching position data.

### 2. Mode detection: poll DRM sysfs, not Sway IPC

`swaymsg -t get_outputs` was considered and rejected as the *primary*
signal: it requires `$SWAYSOCK`/a running Sway session, so a daemon
started before or independent of the shell session couldn't decide its
mode, and it adds a JSON-parsing dependency for a fact `/sys/class/drm`
already states directly. `nix/touch-trackpad/src/mode.rs` reads
`/sys/class/drm/*/status` (matching the operator's own suggested
mechanism, "Detect via DRM/Sway outputs, e.g. HDMI-A-1 active"), polled
every 750ms via `poll(2)` on the touchscreen fd with that same value as
the timeout — so a real touch event is handled with effectively zero added
latency (the poll returns immediately when data is ready) while mode
changes are still noticed within one poll interval when the touchscreen is
otherwise idle. This works unchanged whether HDMI switching stays
reboot-only (the common case today: mode is decided once, at boot, and
never changes until the next reboot) or `plugging-in-hdmi-moves-the-display`
group 4's live hot-plug switching later lands (the poll would then notice
the connector flip within 750ms of it happening) — this daemon does not
need to know or care which regime it's running under.

### 3. Grab semantics: exclusive, not shared

`EVIOCGRAB` is taken only while in trackpad mode, and released
(`EVIOCGRAB(0)`) the instant the mode check sees the panel become active
again — there is never a window where both this daemon and Sway's direct
touch path see the same physical touch. The virtual touchpad uinput device
is created fresh on entering trackpad mode and destroyed
(`UI_DEV_DESTROY`, via `Drop`) on leaving it, rather than kept alive idle,
so libinput never has to reconcile a touchpad whose contact slots didn't
reset across a mode boundary.

### 4. Permissions: root, for this prototype

The service (`nix/touch-trackpad-service.nix`) runs its `ExecStart` as
root. `EVIOCGRAB`-ing another process's input device and creating a
`uinput` device both normally need `CAP_SYS_ADMIN`-adjacent privilege
without a udev rule; this image has no `uaccess`-style ACL rule for
`/dev/uinput` or `/dev/input/event*` (unlike the interactive development
host this was prototyped and host-tested on, where a seat ACL already
grants the logged-in user write access to `/dev/uinput` — see
`docs/evidence/.../host-uinput-classification.md`). `DevicePolicy = "closed"`
plus an explicit `DeviceAllow` still bounds the unit's device access to
exactly `/dev/uinput` and `/dev/input/event*` even running as root.
Narrowing this to a dedicated non-root user plus a purpose-built udev rule
is real, identifiable follow-on work, not done here — this prototype
optimizes for "provably correct protocol translation," not for hardening a
service the coordinator has not yet decided to ship.

## What this design does and does not prove

Host-provable and proven in this change: the ioctl sequence is accepted by
a real Linux kernel and produces a device udev's own classifier calls a
touchpad; the protocol-translation state machine emits the right
transitions for synthetic 1/2/3-finger contact sequences; the mode
detector resolves correctly against DRM-sysfs fixtures covering
panel-only, HDMI-connected, HDMI-present-but-unplugged, and
missing/unreadable sysfs; the crate cross-builds for riscv64-linux with
the same toolchain the rest of the shell already cross-builds with.

Not provable without the board, and left open in `tasks.md`: whether the
real GT9895, grabbed this way, still reports usable contact data through
this relay; whether libinput really does classify and drive the resulting
virtual device correctly when Sway is the one running it (host `udevadm`
evidence is real but is not the same code path as Sway's own libinput
context); whether tap-to-click, two-finger scroll, and pinch/swipe
actually feel right, or feel at all, under a monitor session on this
specific slow RISC-V core; and the interaction between this daemon's
`EVIOCGRAB` and any GPIO23/24 contention `plugging-in-hdmi-moves-the-display`
documents between touch and the LT9611 bridge. `tasks.md` group 3 names
the exact board commands for each of these once an HDMI session exists to
try them against.

### 5. Response to the first board run: validate axes, bound the loop, handle signals

The first board run (`docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/board-hang-2026-09-29.md`)
hit a real bug and hung the board badly enough to need a hardware reset.
Three changes came out of it, none of them claiming to be *the* single
proven cause (board access was not available to isolate that) but each
closing off a real, identified failure mode:

- **`uinput::axis_plan`**: the real GT9895 reports `ABS_MT_PRESSURE` with
  `minimum == maximum` (`0 == 0`) -- confirmed the direct cause of the
  logged libinput error ("kernel bug: device has min == max on
  ABS_MT_PRESSURE"), and this crate's own `read_ranges()` fallback for a
  *failed* pressure ioctl was equally degenerate, so the bug could not
  have been avoided by "just handle the ioctl failure case." `axis_plan`
  now validates every axis before it reaches `/dev/uinput`: a degenerate
  *load-bearing* axis (`slot`/`tracking_id`/`position_x`/`position_y`,
  none of which a touchpad can function without) refuses device creation
  outright; a degenerate *optional* one (`pressure`, which `relay.rs`
  never reads -- slot occupancy, not pressure, drives `BTN_TOOL_*`) is
  silently omitted, matching how real pressure-less touchpads report
  themselves. Position-axis `resolution` is also sanitized (a fallback
  applied only when the source reports `<= 0`), addressing the
  "sane resolution values" half of the same request even though it was
  not implicated in the logged error. Host-verified end to end, including
  a live `/dev/uinput` creation using the board's exact degenerate-pressure
  fixture, re-confirmed still `ID_INPUT_TOUCHPAD=1` via `udevadm`:
  `docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/board-hang-2026-09-29.md`.
- **Bounded, signal-aware, non-busy-looping main loop**: `wait_readable`
  previously returned "readable" for *any* `poll()`-reported event,
  including `POLLERR`/`POLLHUP`/`POLLNVAL` with no `POLLIN` -- a device
  that reached a state where the kernel reports one of those on every
  `poll()` call without ever legitimately blocking again would turn this
  into an unbounded tight loop (`poll()` returns instantly forever). It
  now checks `revents` explicitly and treats those three as a hard error,
  tearing the session down (which does sleep before retrying) instead of
  looping. The event-drain loop in `main.rs` also gained a hard cap
  (`MAX_EVENTS_PER_DRAIN`) so *any* bug that made `pump_one` never report
  idle degrades to "drains up to 2048 events, then yields back to the
  mode/shutdown check" rather than never yielding at all. `SIGINT`/`SIGTERM`
  handlers (setting an atomic flag only, per async-signal-safety rules)
  let an operator interrupt a run cleanly from the console instead of
  needing `kill -9` or a reset. Host-verified: a FIFO-based test proves
  `wait_readable` genuinely blocks for its timeout on idle data and
  returns promptly once data exists (a real `/dev/input/event*` node
  cannot be opened unprivileged in this sandbox, unlike `/dev/uinput`, so
  the FIFO exercises the same underlying `poll(2)` code path instead).
- **`--dry-run` / `--log-events`**: `--dry-run` runs the real grab and
  read/relay logic but never opens `/dev/uinput` at all, so a re-test on
  the board cannot repeat the libinput/Sway interaction that preceded the
  hang, no matter what it turns out to have been. `--log-events` traces
  every raw and translated event to stderr. `tasks.md` group 3's revised
  re-test procedure leads with `--dry-run --log-events` under a `timeout`
  wrapper before ever creating a real uinput device again.

What this explicitly does *not* claim: that the degenerate-pressure axis
was *the* mechanism that hung the board (as opposed to, say, a busy loop
independently triggered around the same moment) -- `board-hang-2026-09-29.md`
records that as unestablished. The fix set is deliberately broader than
"patch the one confirmed bug" because board time to iterate is scarce and
precious (AGENTS.md's single shared board/serial reservation), and each
addition here is independently justified and host-tested on its own
terms, not speculative padding.

## Risks / Trade-offs

- [libinput's default acceleration/tap/scroll tuning is designed around
  typical laptop touchpad physical dimensions (~10cm), and this glass is
  smaller and a different aspect ratio] → the `ABS_MT_POSITION_X/Y`
  `resolution` (units/mm) fields are mirrored from the real device rather
  than hardcoded, which is what libinput's size-dependent heuristics key
  off; if the feel is still wrong on the board, tuning is a `libinput`
  config-file change (`nix/shell.nix`'s Sway `input` stanza), not a change
  to this relay.
- [A slow single RISC-V core doing per-event translation adds latency a
  fast host wouldn't show] → the relay does no heap allocation beyond a
  small `Vec` per `SYN_REPORT` frame (at most 3 synthesized events) and no
  parsing; the real cost floor is two syscalls (a `read` and a `write`,
  each already a poll-then-io round trip today for the touchscreen's
  existing consumer) per event, which this design does not add to, only
  redirects. Not yet measured on the board — a follow-on task, not claimed
  here.
- [Root service is a real, if narrow, escalation] → accepted explicitly
  for this prototype (decision 4); `DeviceAllow`/`DevicePolicy` bound the
  blast radius even so, and the module is enabled only in the explicit coherent-shell HDMI
  profile after its standalone safety trial.
- [`plugging-in-hdmi-moves-the-display`'s shared GPIO23/24 net between
  touch and the LT9611 could mean touch's interrupt behaves differently or
  less reliably while the HDMI DTB is the one booted] → this change cannot
  observe that without the board and does not assume otherwise; it is
  named explicitly as an open board-verification question in `tasks.md`
  rather than folded into a confident requirement.

## Board contact checkpoint and tap configuration

The real bounded contact capture contains both one- and two-finger frames.
It revealed that the original hand bindings emitted `BTN_TOOL_TRIPLETAP`
for two fingers. The corrected codes now have an independent C/Linux-header
regression check; relay synthesis and advertised capabilities share those
bindings. The operator confirmed pointer movement in the live virtual-device
trial, but tapping did not click. Sway disables tapping by default, so the
image explicitly enables tapping and two-finger scrolling for
`1:1:K230_Virtual_Touchpad_(HDMI_mode)`. Direct-touch input keeps its existing
configuration. See the committed board contact checkpoint for provenance and
limits; physical click/scroll/pinch and panel restoration are still required.

## Persistent HDMI profile integration

After the corrected standalone relay remained active without the original
libinput pressure error, the explicit `k230-coherent-shell-hdmi-trial` profile
imports this service and enables it. Other configurations do not import it.
Systemd bounds shutdown to two seconds, and normal unit-change restarts ensure
future rebuilt relay packages replace the running binary. The persistent unit
replaces the transient trial so only one process grabs the glass. Installation
and enabled-unit observations establish the deployed profile, not an actual
reboot or panel-mode acceptance; those remaining gates stay explicit.

## Pointer input must reach shell actions

The operator reports that pointer movement works but clicking shell icons
opens nothing. Source inspection finds that the Rust client subscribes only
to touch and keyboard capabilities: it never obtains a `wl_pointer`.
The relay/libinput path cannot deliver mouse actions to a client that never
requests them. Subscribe to normal SCTK pointer frames and share the existing
contact down/motion/up/cancel actions between touch and primary pointer drag.
Keep a pointer contact owned by its initial surface, ignore hover/secondary
buttons for activation, and cancel on leave or capability loss. This uses
normal Wayland client paths and does not change the compositor or touch mapping.
Physical launcher activation remains a separate evidence gate from injected
mouse delivery or host model tests.

## Four-finger trackpad navigation

The board's touchscreen glass remains the input while its built-in display
is inactive and HDMI presents the image. In relay mode its contacts reach
libinput as touchpad events, so the direct-touch compositor edge-swipe path
does not apply. The operator requests a four-finger inward pinch to enter app
overview. Sway's pinned `sway/sway.5.scd` documents `pinch:4:inward`; its
`sway/input/seatop_default.c` routes matching pinch gestures to bindings.
Use `bindgesture --input-device=1:1:K230_Virtual_Touchpad_(HDMI_mode) pinch:4:inward card_shell enter`
in the generated Sway configuration. A live IPC binding provides immediate
availability; the image configuration makes it persistent. Actual four-finger
recognition/overview appearance remains a physical evidence gate.
