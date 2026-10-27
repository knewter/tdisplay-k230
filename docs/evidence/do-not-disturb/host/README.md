# Do Not Disturb host renders

Evidence class: **host render** (cairo, no compositor, no board, no glass).

Command, from `nix/rust-shell-client`:

```
cargo run --offline --example render_do_not_disturb_evidence -- ../../docs/evidence/do-not-disturb/host
```

Files: `shade-<modem|no-modem>-dnd-<off|on>-<100|200>-1232x568.png` and
`settings-<modem|no-modem>-dnd-<off|on>-<100|200>-1232x568.png`. `200` is the
largest vision text step (`accessibility.text-scale` 2.0, delivered through a
fixture theme, as `render_settings_about_evidence` does). Notification rows,
battery and modem values are fixtures. The clock is the host's at render time.

What the renders show (2026-10-27):

- Three tiles across, two rows deep, with and without the modem; the sliders
  stay on the 568 px panel at both steps (also asserted by
  `the_wide_shade_tiles_stay_three_across_and_two_deep_at_every_text_step`).
- The tile label is "Quiet", not "Do Not Disturb": "Do Not Disturb" does not
  fit a 136 px tile at the caption size. Settings keeps the full name. The
  Wi-Fi state words are "Online" and "Offline", the Keyboard state "Toggle".
- With the mode on, a moon glyph leads the glyphs at the right of the status
  line.
- At 100% every word is whole at the label/caption size. At 200% the icon is
  dropped and all tile words share one size, about 70% of the 100% size,
  because "Searching" at the full 200% size is wider than a 136 px tile. No
  word is cut off. This is below the caption size the design named as the
  gate, and is reported rather than ticked as met.

Limits: nothing here shows the banner staying away, the persisted file, or the
tile on glass.
