## Context

Three processes share display power:

- `k230-power-keyd` (`nix/power-keyd/power_keyd.py`) toggles
  `output * power off|on` on a short press and caches the result in
  `Actions.dark`.
- `k230-touch-trackpad` (`nix/touch-trackpad/`) polls DRM connector status. It
  switches between trackpad mode (HDMI is the output) and direct touch (the
  panel is the output). On direct touch it maps touch to DSI-1 over Sway IPC.
- Sway stores the power state for `output *`, so an output created later
  (DSI-1 after an unplug) inherits a stored "off".

## Decisions

1. **The relay sends the wake on a real unplug.** The relay polls DRM sysfs.
   It now also watches the HDMI connector's `status`, and when that changes
   from `connected` to anything else it sends `output * power on` ahead of the
   touch mapping. This reuses the mapping's existing retry, with no new
   hotplug watcher. Sway stores the `*` power state even before DSI-1 exists,
   so the order against output creation does not matter. The wake is sent
   once per unplug: it is cleared after a successful mapping, and the first
   reading after a relay restart never counts as an unplug.

   The Trackpad → DirectTouch mode edge is **not** used. Board journal
   2026-10-16 13:36:29–31 shows why: a power-key blank on HDMI disables HDMI
   scanout (`enabled` → `disabled`) with the cable still in, so the relay left
   trackpad mode at 13:36:30, one second before HPD reported the unplug.
   Waking on that edge undid every power-off of the monitor. The first
   implementation (`0051c34b`) did this; the connector-status edge replaces it.
2. **The power key reads Sway's state.** A cached flag goes stale once another
   process changes power. Before each action the daemon reads `get_outputs`:
   the display is dark when no active output reports `power: true`. If Sway is
   unreadable or lists no active output, the daemon keeps its cached flag, so
   a transient IPC failure never inverts a press.
3. **No wake on plug-in.** The operator asked only for unplug. Plug-in keeps
   the stored state, so the monitor stays dark if the person darkened the
   panel first.

## Risks

- An unplug while the person deliberately keeps the display dark now lights
  the panel. This is the operator's stated intent.
- If Sway rejects `output * power on`, the mapping retries on the next poll
  with the wake still pending.
