## Context

The broker (`tools/notification_center.py`) is a Unix-socket service. It names
a sender from `SO_PEERCRED` and `/proc/PID/exe` looked up in a Nix-written map
(`notificationSources` in `nix/shell.nix`), never from the request. Only the
Rust shell is in the map, so only it gets a name, an icon and a priority.
Everyone else is "Unknown source", ordinary, text hidden.

The Timer (`nix/term-apps/k230_term_apps.py`, `run_timer`) is a TUI in a Foot
card. On expiry it writes `\a`. Closing the card ends the process.

Layer: all of this is userspace (Nix packaging plus Python). No kernel, device
tree or stage 1 work.

## Decisions

- **D-Bus binding: `jeepney`.** It is pure Python with no dependencies and
  ships in nixpkgs, so the riscv64 cross build needs no C extension and no
  GLib. Its blocking API has a `receive()` that sleeps in the socket read, so
  the adaptor is event-driven with no timers. The repo has no D-Bus Python
  binding today (checked `nix/` and `flake.nix`); every other D-Bus user is C
  or Rust. UNVERIFIED: that `python3.withPackages (ps: [ ps.jeepney ])` builds
  under the cross toolchain and fits the closure budget; it is not yet built.
- **The adaptor is a delegate, not a source per app.** The broker can only
  name peers by executable. All apps share the adaptor's process, so the
  broker trusts the adaptor and the adaptor passes the app as a claim.
  The broker, not the adaptor, enforces the rules, so a bug or a compromised
  adaptor still cannot forge the Shell:
  - app id is namespaced `app:<id>`; tags and replacement are per app;
  - the label is sanitised, and anything that reads as shell, system,
    notification, settings, recovery or "unknown source" becomes
    "Application";
  - the icon must be a plain theme-name; paths are dropped;
  - priority is capped at important, `ongoing` and `target` are ignored, and
    the text is always private in the preview.
- **Trust by interpreter plus script.** All Python programs share one
  interpreter, so trusting `/proc/PID/exe` would trust any Python the user
  runs. The map accepts `"<exe> <script>"` keys. The broker compares the
  resolved executable and the first non-option argument from
  `/proc/PID/cmdline`. This is the same-user threat model the broker already
  has, not a stronger one: a same-user process can still fake `argv`. The
  broker's socket and the session bus are already private to the `shell` user.
- **Urgency mapping.** `urgency` 2 becomes important. 0 and 1, and a missing
  hint, become ordinary. The adaptor never sends critical, because critical
  is the broker's retained, recovery-oriented class.
- **Replace and close.** The adaptor issues ids and records which app owns
  each (bounded at 256). `replaces_id` from another app gets a new id. The
  broker already de-duplicates by source and `tag`, so the adaptor tags every
  event `dbus-<id>`. `CloseNotification` sends a new broker operation,
  `withdraw`, usable only by the delegate and scoped to one app and tag. A
  person's dismissals are unchanged.
- **Timer posts directly.** The Timer is a trusted source ("Timer",
  `k230-timer`), keyed on interpreter plus its script, rather than a client of
  the D-Bus adaptor. That path has no bus dependency and works if the adaptor
  is down. The notification is important, with `private: false`: the summary
  is the Timer's own text, not user content.
- **Surviving the card.** When the card closes while the timer runs, the app
  starts `k230_term_apps.py timerd <deadline> <initial> <state>` in a new
  session and records its pid and deadline in `$XDG_RUNTIME_DIR` (falling back
  to `/tmp`). The helper does one `sleep` to the deadline on `CLOCK_MONOTONIC`,
  posts once, and removes its record. Reopening the Timer finds a live helper,
  stops it, and resumes the countdown from the recorded deadline. No polling.
- **CPU.** The adaptor and an idle helper block in the kernel. A post is one
  short Unix-socket exchange. There is one online CPU, so no extra wakeups
  were added.

## Rejected

- **`dbus-next`.** Asyncio-based; a loop for a service that has one blocking
  read adds code and a dependency chain for nothing.
- **GLib/Gio (`pygobject`, `gdbus` server).** C extension and GLib in the
  Python closure; `gdbus` cannot export a service by itself.
- **A hand-written D-Bus wire parser.** Marshalling `a{sv}` correctly is the
  part that goes wrong. Reuse jeepney.
- **One broker entry per app executable.** The adaptor owns the bus name, so
  every app arrives from the adaptor's pid.
- **Trusting the claimed `app_name` as a source.** Any app could label itself
  "Shell". The reserved-name rule and the namespaced id exist to stop that.
- **A systemd user timer or transient unit for the Timer.** The `shell` user
  has no `systemd --user` instance on this image (there is no login manager;
  see the PipeWire note in `nix/shell.nix`).
- **A resident `k230-timerd` service.** An always-on daemon costs memory on
  every boot to serve a feature used a few times a day; a helper that exists
  only while a countdown is pending costs nothing otherwise.

## Risks

- A same-user process can forge `argv` and be taken for the delegate or the
  Timer. Accepted: the same user can already write to the broker's directory.
- `CLOCK_MONOTONIC` stops across suspend. If the board suspends with a timer
  pending, it will alert late. UNVERIFIED: whether this image suspends with
  the shell running.
- The helper lives in `shell.service`'s cgroup. A shell restart or a force
  kill ends it, and the timer is lost silently.
- Apps that use GTK's built-in `GNotification` fallback when no server is
  present may behave differently once a server exists.
  UNVERIFIED on the board.
- The adaptor cannot report to an app that the person dismissed its
  notification, so apps that wait for `NotificationClosed` wait forever.
