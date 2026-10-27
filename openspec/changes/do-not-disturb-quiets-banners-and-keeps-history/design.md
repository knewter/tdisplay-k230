## Context

- The broker (`tools/notification_center.py`) records events, ranks them
  and computes a `preview` that has already had privacy applied. The shell
  client (`nix/rust-shell-client/src/main.rs`) polls it every second, or every
  500 ms while a preview shows, and maps a `Layer::Overlay` banner while
  `notification_banner::visible` says so.
- Priorities are `ordinary`, `important` and `critical` (`PRIORITIES`). The
  broker caps a delegated app at important (`History.emit`), so critical is
  reachable only by trusted shell-side sources. Today that is
  `nix/keyboard-base/battery_policy.py`'s ongoing "Battery critically low".
- The Timer posts `priority: "important"`, `private: false`
  (`timer_expiry_request`, `nix/term-apps/k230_term_apps.py`). It is not
  critical. The in-flight `apps-and-timers-can-alert-the-user` keeps it
  important, so "critical breaks through" alone would silence the Timer.
- The wide shade's tile grid is two columns by two rows (`shade_tile_rect`,
  `service_ui.rs`): tiles start at y=152, are `shade_tile_h()` tall (the
  99 px floor, grown with the text step, capped at 112) with a 12 px gap, and
  the sliders start under the second row at `152 + 2*(h+12) + 4`. At the cap
  that is 404; brightness and volume are 56 px each with a 20 px gap, so the
  column ends at 536 of 568 px, and the cap keeps that true at 200%.
- The key-backlight preference is the pattern for a persisted preference:
  `keyboard_base::write_preference` writes one word to
  `/var/lib/k230-keyboard-base/key-backlight`, a directory created by a
  `systemd.tmpfiles.rules` entry in `nix/shell.nix` owned by the `shell`
  user, and a missing file means the default.

Layers: userspace only. Broker (Python), shell client (Rust), one Nix rule.
No kernel, device tree or stage 1 work.

## Decisions

### Where quiet mode is enforced: the shell client

The client already owns the banner, and the broker's history must stay
complete either way. So the broker is unchanged except for one fact it alone
knows (below), and the client drops a non-alert preview before it reaches
`banner_preview`. The shade's own history poll is untouched, so quiet mode
cannot lose an event. Turning quiet mode on while a banner shows unmaps it on
the next sync; turning it off does not resurrect a banner that was dropped.

### Who may break through: a broker-computed `breakthrough` flag

The broker sets `preview.breakthrough = true` when the event is critical, or
is important and its source is trusted and not a delegated app. That is
exactly the Timer and the base battery, and it excludes the D-Bus adaptor's
apps (capped at important, `app: true`), SMS (ordinary), and unknown senders
(ordinary). The flag is on the preview only, not on history rows. The client
treats a missing field as false, so an older broker silences everything, which
is the safe direction for a quiet mode.

The rule lives in the broker because only the broker knows whether a source is
a delegate. The preview does not carry the source id, and the client must not
guess from the label.

### Tile grid: three columns, still two rows

A third row does not fit: it adds `shade_tile_h() + 12`, at least 111 px, and
pushes the volume slider's end to about 647 px on a 568 px panel at every
text step. Rows cannot shrink under the 99 px floor ("Shade tap targets meet
the shell's 48dp-equivalent floor"). So the grid goes to three columns.

- Width: `(480 - 48 - 2*12) / 3 = 136` px per tile, from the existing 480 px
  controls column and 24 px margins. Height and the slider top are unchanged,
  so the sliders still end at 536 px at every text step.
- Order, row-major: Wi-Fi, Keyboard, Do Not Disturb; Location, Cellular. The
  second row exists only once the modem has answered, as now, and the slider
  top still does not move with the modem.
- `shade_tile_rect` takes the column count from one `SHADE_WIDE_TILE_COLUMNS`
  constant so paint and hit-test read the same value. `shade_tiles` gains
  `ShadeTile::DoNotDisturb` after Keyboard, and `shade_tile_at` needs no new
  geometry. The tap arm in `service_ui.rs` gains one intent.
- A 136 px tile holds less text than today's roughly 210 px one. Each tile
  stacks its icon over its label and one state word ("On", "Off", "Fix",
  "Searching", "Connected", "Offline"), and an on tile also takes the accent.
  `fitted_size` shrinks text that still does not fit. How far text may shrink
  is an acceptance gate of the host render, not a number guessed here.
  <!-- UNVERIFIED: that "Searching" and the Wi-Fi state words fit 136 px at the largest vision step without shrinking below the caption size; decided by the 100% and 200% host renders. -->
- The sixth slot is empty with no modem; a later quick control fills it
  without another layout change.

### Status indicator

A moon glyph is painted among the glyphs at the right of the wide status line,
before the Location and signal glyphs, at the same size and colour. The glyph
carries the state and the tile says "On" or "Off", so the status line does not
repeat a label. The portrait shade has no status line today; there the
Settings row is the indicator.
<!-- UNVERIFIED: the wide status line has room for a third glyph at the largest step; widths come from `icon_size` and the line is `hw - 56` wide, with the battery text fitted into what remains. -->

### Settings row

Settings carries one row per preference, and the portrait and HDMI shades have
no tile. A Do Not Disturb switch row, built like Reduce motion's, reads and
writes the same preference as the tile, so the two cannot disagree.

### Persistence

A new `do-not-disturb` file holding `on` or `off`, written by the shell
client the way `keyboard_base::write_preference` writes the key backlight. The
directory is new, `/var/lib/k230-shell-prefs`, created by one
`systemd.tmpfiles.rules` entry `d /var/lib/k230-shell-prefs 0700 shell shell -`
beside the existing one, because the keyboard-base directory is named for the
base and a Do Not Disturb file there would mislead. Reading happens at client
start and the in-memory value is authoritative afterwards. A missing file, an
unreadable file or any other content means off, so a bad file can only let
banners through. A write failure is logged without the value and the tile still
flips for this session, as the key-backlight path does.
<!-- UNVERIFIED: that /var/lib is persistent on the installed SD image across a reboot; the key-backlight preference relies on the same assumption and no reboot proof of it was found. Task 3.4 records it. -->

## Rejected

- **Broker-side mute with a `set-quiet` operation.** It would put the state in
  the broker process, which has no state directory and restarts independently
  of the client, and it adds a request type. The only consumer of the preview
  is the client.
- **A third row of tiles, or shorter tiles.** The first overflows the panel;
  the second breaks the 99 px floor.
- **Replacing the Keyboard tile.** It is the shade's existing quick-toggle
  contract and not ours to remove.
- **A status-line text segment, "Do not disturb".** It spends width the
  battery text needs at 200%, and the glyph already carries the state.
- **Treating only `critical` as break-through.** It silences the Timer, the
  one alert a person sets on purpose.
- **Raising the Timer to critical.** The wide shade refuses swipe-dismiss for
  `Priority::Critical` rows (`service_ui.rs`, the swipe start; `render.rs`, the
  cue), so "Timer finished" could be cleared only by Dismiss all. It would
  also contradict the apps-and-timers delta, which keeps the Timer important.
- **Auto-expiry.** A forgotten quiet mode is a risk, covered by the glyph and
  the break-through rule. A timed mode needs its own design.

## Risks

- A person who forgets quiet mode misses SMS banners. The shade count and the
  companion Home count (`home-shows-how-many-notifications-wait`) keep the
  fact visible; nothing is lost.
- Three tiles across is tight at the largest text step. The renders decide
  whether the copy is short enough.
- `the-shade-leads-with-time-and-quick-tiles` must archive first, since this
  change's tile requirement refines its grid.
