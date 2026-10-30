# Notification actions: host renders

Evidence class: **host render**. It proves paint and layout only. It is not
board or glass evidence. Task 2.3 of
`pending-timers-survive-restarts-and-apps-hear-dismissals`.

Rendered 2026-10-30 on the worktree branch off `7fac14ad`, with:

```sh
cd nix/rust-shell-client
cargo run --offline --example render_notification_actions_evidence -- <out>
```

The example draws the shade with three FIXTURE notifications: "Calculator"
with two actions (Open, Snooze), "Messages" with one (Reply), and "Mail" with
none. It renders the landscape panel (1232x568) and the native portrait panel
(568x1232), at the 100% and 200% vision text step.

| File | Shows |
| --- | --- |
| `shade-actions-{100,200}-{WxH}.png` | The shade at rest (list scrolled to the top). The first row carries two buttons side by side. |
| `shade-actions-200-568x1232-scrolled.png` | The 200% portrait list is 247 px tall and the first row with its buttons is 362 px, so at rest the buttons are below the list. This twin is scrolled until they show. |

Observations and limits:

- Every action button is 99 px tall (the shell's `TOUCH_FLOOR`), checked by
  `service_ui::tests::an_apps_actions_are_touch_floor_tall_and_a_tap_names_the_action`
  at both steps and both orientations, as is the tap-to-action mapping.
- A row with actions is taller by 115 px (the 99 px button, 8 px above and
  8 px below). Rows without actions keep their old height.
- At most two actions are drawn. Labels are centred and ellipsised in their
  button; "Snooze" fits at 200% on the portrait panel.
- Nothing here shows a tap, a signal reaching an app, or the panel's glass.
  Those are tasks 3.2 and 3.3.
