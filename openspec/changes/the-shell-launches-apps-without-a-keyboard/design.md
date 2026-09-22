## Context

The persistent 56-pixel swaybar is the proven click route for Apps, Windows,
Keyboard, and System. Its prior Apps row made useful actions reachable, but a
fourth 128-pixel block cannot present an attractive handheld launcher. See
`proposal.md` for the user-facing motivation.

## Goals / Non-Goals

**Goals:**

- Open a full portrait launcher beneath the persistent bar.
- Make Terminal, Monitor, New terminal, and Back large named touch targets.
- Retain focus-or-start recovery and avoid adding a long-lived service.
- Keep the implementation small enough for the Pixman RISC-V session.

**Non-Goals:**

- A general desktop environment, GTK/Qt widget stack, shell evaluation of
  desktop entries, or session/onboarding framework.
- Replacing swaybar controls, changing keyboard/window/system behavior, or
  claiming physical-touch proof from host tests.

## Decisions

**Use a local Wayland SHM layer-shell client.** The client creates an overlay
surface with exclusive zone zero and no extra top margin. Sway already
subtracts the persistent bar's 56-pixel exclusive area; adding another margin
would expose a second strip of the underlying app, as the first board trial
showed.
It draws a title and four high-contrast portrait cards into one ARGB SHM
buffer and listens for both `wl_touch` and `wl_pointer` release events. This
uses `wayland-client` and protocol XML already available through the pinned
Wayland/wlroots stack. It does not need a widget toolkit, GPU, font catalogue,
or extra daemon. The fixed bitmap labels are deliberately local and
predictable.

**Retain swaybar as the entry point.** Apps launches the client in the session;
Windows, Keyboard, and System retain their current status-command state
machine. The surface's Back card closes it, returning to the bar's home
controls.

**Use a narrow action bridge.** The client invokes one wrapper-owned helper
with `terminal`, `monitor`, or `new-terminal`. The helper contains the same
known app IDs and Foot profiles as the bar path; it never accepts arbitrary
commands. Terminal and Monitor query Sway then focus-or-start. New terminal
always starts another readable Foot window.

**Use GLib for installed applications and Pango/Cairo for text.**
GDesktopAppInfo applies XDG precedence, Hidden/NoDisplay/TryExec filtering,
and parses/launches Exec without shell evaluation. The service exports the
shell profile XDG data directories and a Sway desktop identity. Pango/Cairo,
already in the closure, renders arbitrary application names. Entries refresh
at each Apps open and paginate after the built-ins. Terminal=true is routed
through the existing Foot bridge; unsupported launches show an in-surface
error.

## Risks / Trade-offs

- [Layer-shell input/configuration differs on the board] → fail clearly when
  required globals are absent; leave the bar controls available and record
  real-glass results separately.
- [The fixed bitmap text is less flexible than a toolkit] → labels are short,
  large, high contrast, and source-controlled; no font dependency is added.
- [An action helper duplicates small focus-or-start logic] → it accepts only
  three fixed action names and shares the same Nix-provided binaries/configs.
- [A Wayland client adds a small closure] → build the named package separately
  and report its closure before image integration.

## Migration Plan

Deploy via the normal shell system closure. Apps starts the launcher only in
the Sway session; closing it or an unavailable client leaves the bar usable.
Removing the package/wrapper restores the bar-only Apps path and leaves no
state or privilege change.
