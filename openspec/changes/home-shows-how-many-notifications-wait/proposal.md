## Why

A person cannot tell that a notification is waiting without pulling the shade
down. A banner stays five seconds and then nothing on the device says an event
came in: not on Home, not in the overview. A text received while the handheld
sat on a desk is invisible until the person thinks to look. Review gap 7 of
`docs/design/shell-ux-review-webos-firefoxos-2026-10.md` records that webOS
and Firefox OS both kept a status bar for this, and that this shell
deliberately has none.

Today the only "pending" indication is inside the shade itself ("N
notifications" in the list heading), which is what the person is trying to
decide whether to open.

## What Changes

- **A count on Home.** When the broker holds at least one event, Home shows a
  small count, in its top-right corner, painted into Home's own surface. At
  zero it draws nothing. The number is the same count the shade's list heading
  states, so the two agree.
- **Content stays private.** The count carries no source, summary, icon or
  priority. A text message, an unknown sender and an app read the same.
- **Nothing is added to apps or to the overview.** Apps stay chrome-free, and
  no permanent control is added to any composition. The compositor-side
  overview (`nix/card-shell/adapter.c`) has no broker connection and is left
  alone.
- **No new surface, no opaque region.** The count is pixels in Home's existing
  buffer, never a layer of its own, so it cannot make a sliding surface
  opaque.
- **Do Not Disturb stays visible.** The count does not change while quiet mode
  (`do-not-disturb-quiets-banners-and-keeps-history`) is on; it is how a person
  who muted banners sees that something arrived.

## Non-goals

- A status bar, a glance pill over apps, a count in the overview, or a badge
  per app icon.
- Read and unread tracking. The count is events retained in history, exactly
  as the shade counts them.
- Showing time, battery or Wi-Fi (the rest of review gap 7).
- A new broker operation, wire field or poll.
- The count being a tap target. A pull from the top edge still opens the shade.

## Capabilities

### Modified Capabilities

- `runtime/home-screen`: Home shows how many notifications wait.
- `runtime/notification-center`: the glance reveals a count and nothing else.

## Impact

- `nix/rust-shell-client/src/main.rs`: keep the count from each
  `PreviewPoll` reply and redraw Home when it changes.
- `nix/rust-shell-client/src/render.rs` (`paint_home`, and its callers
  including `evidence_render.rs`): paint the count.
- `nix/rust-shell-client/src/home_screen.rs` or a small helper: the pure
  placement and label rule, so it is host-tested.

No broker, Nix or compositor change. Host work needs no board. The Home look
on the panel needs the board, and glass needs the operator.
