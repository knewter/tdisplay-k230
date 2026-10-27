## Context

What shows today when an event is waiting and the shade is closed:

- **Banner.** `notification_banner` maps an overlay for the broker's preview,
  which the broker ends after five seconds (`History.snapshot`: `clock() -
  received < 5`). Then nothing remains.
- **Home** (`nix/rust-shell-client/src/home_screen.rs`, painted by
  `render::paint_home`): no notification state. `grep` for notification, count
  or unread in `home_screen.rs` finds only the remove badge and widget code.
- **Overview and card chrome** (`nix/card-shell/adapter.c`): C code in the
  compositor. It has no link to the broker (`grep -i notif` finds only
  wlroots seat notifications), and its header carries cards and a "Home · tap
  or swipe up" cue.
- **Apps:** maximised Sway windows with no chrome. `runtime/shell` says normal
  composition "SHALL NOT retain permanent Apps, Windows, Keyboard, System, Back
  or Home controls", and the shade redesign states the device has no status
  bar.

The client already has what is needed. It polls the broker every second while
idle (`sync_banner`), and each `PreviewPoll` reply is a full
`NotificationSnapshot` whose `count` is the number of retained events. Today
the reply's `count` is dropped unless the shade adopts it
(`shade_adopts_poll`).

Home is a `Layer::Bottom` surface. Its pages slide inside its own buffer while
the pager drags, and the client declares an opaque region only when a drawn
frame is entirely opaque (`bgra_frame_is_opaque`, `main.rs`). `paint_home`
clears to transparent and paints over it.

Layers: userspace, Rust client only.

## Decisions

### Smallest change: a count on Home

Home is the one surface a person looks at with no app in front, it is drawn by
the Rust client that already holds the count, and it has no permanent control
to violate. A count in the corner of Home needs one stored integer, one
painter and one redraw trigger. It does not touch the compositor, the broker,
the wire format or the gesture rules.

- **Source of the number.** The reply to each `PreviewPoll` supplies
  `snapshot.count`. It is stored as `pending_count` beside `banner_preview`.
  When it changes and Home is the visible route, Home is marked dirty. No new
  poll, no timer: the existing one-second poll is the only cost.
- **What it counts.** Events retained in history, including ongoing critical
  ones, because that is what the shade's heading counts, and "each fact is
  stated once" is an accepted rule. Read and unread is not tracked; the broker
  has no such state. Opening the shade does not clear the count; dismissing
  does, as it clears the heading.
- **Label.** Digits only, `99+` above 99. Zero draws nothing.
- **Look.** A pill in the theme's accent with the shell's Caption type, a
  filled shape plus the number so it does not depend on colour alone. High
  contrast and the text step apply through the same metrics the other Home
  text uses. <!-- UNVERIFIED: that the accent and Caption type read at arm's length on the panel; decided by the host render and the board capture. -->
- **Place.** The top-right corner of Home, inside the margin the page-count
  dots and the widget grid leave clear, never over a plate, widget or dock.
  The exact rectangle is chosen from the host render of a full Home page with a
  Clock widget in the top row, and the pure helper that returns it is tested
  to lie outside every occupied cell on the default layout.
  <!-- UNVERIFIED: that the top-right of the 1232x568 Home has clear room beside the default layout's top row; the host render settles it, and a user-rearranged layout may differ, so the helper must clamp rather than assume. -->
- **Not a target.** It is painted text. A touch that begins on it is handled
  as the Home surface already handles it; a pull from the top edge still opens
  the shade, which is the action the count invites.

### Privacy

The broker has already applied its rules to the `preview`, and the history
rows carry private text by design. The glance reads only `count`, an integer,
and never a row or the preview, so no source, summary, icon, body or priority
can leak into it. The log line for a change carries the number only. An
unknown sender and a trusted source both add one.

### No opaque region on a sliding surface

The count is drawn into the buffer Home already owns. It adds no layer surface
and no `set_opaque_region` call, and `paint_home` still clears to transparent,
so Home's frame stays non-opaque exactly as before, whether or not the count
shows. The rule in `runtime/shell` ("A surface that slides SHALL NOT declare an
opaque region while it moves") is therefore unchanged. A frame test asserts
that a Home frame with the count is still reported non-opaque by
`bgra_frame_is_opaque`.

### Where it will not appear

Not in apps (no permanent chrome), and not in the overview (compositor
code with no broker link). A person inside an app still sees the banner for
five seconds and the count when they go Home. Review gap 7's transient glance
pill over an app is a separate, larger change and stays unbuilt here.

## Rejected

- **A persistent dot or strip on the top edge over apps.** It would be a
  permanent control, which the shell forbids, and a layer over a client that
  may be sliding.
- **A count in the overview header.** It needs the compositor to open the
  broker socket and parse JSON in C, or a new client-to-compositor channel. The
  Home count covers the idle case for far less.
- **A glance pill when a top-edge touch begins (gap 7's closure).** It paints
  a new overlay that appears under a touch that is about to become the shade
  drag, so it would sit on a moving surface and must not be opaque; it also
  spends a repaint on every top-edge touch on a one-CPU board. Worth its own
  proposal after the Home count is seen on glass.
- **Per-icon badges.** Notifications are not tied to app icons in the broker
  (`target` is a window id, and delegated apps have none).
- **Unread tracking.** It needs a broker field and a rule for when an event
  is seen. The shade's count and the glance would then disagree until the
  person opened every event.
- **A new broker field or poll for the count.** The snapshot already has it.

## Risks

- The corner may collide with a user-rearranged Home layout. The helper is
  tested on the default and on a full page, and clamps to the free margin.
- The count includes ongoing critical events, such as low battery, that
  cannot be dismissed, so it may stay above zero. This matches the shade.
