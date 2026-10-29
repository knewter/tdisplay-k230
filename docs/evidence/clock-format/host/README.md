# Clock format: host renders

Evidence class: **host render**. It proves paint and layout only. It is not
board or glass evidence. Task 2.1 of `settings-chooses-a-12-or-24-hour-clock`.

Rendered 2026-10-29, from the worktree on top of `69ce212d`, with:

```sh
cd nix/rust-shell-client
cargo run --offline --example render_clock_format_evidence -- <out>
printf '12-hour\n' > <prefs>/clock-format
python3 nix/term-apps/k230_exhibition.py --render-once 100x30 --prefs-dir <prefs>
python3 nix/term-apps/k230_exhibition.py --render-once 40x60  --prefs-dir <prefs>
```

The example sets the 12-hour flag and renders at the landscape panel
(1232x568) and the native portrait panel (568x1232), at the 100% and 200%
vision text steps.

| File | Shows |
| --- | --- |
| `date-time-{100,200}-{WxH}.png` | Settings > Date & time. The Clock format card has its switch on and reads `12-hour`, and the Time row reads `9:05:09 PM`. The rows are FIXTURE values. |
| `home-{bubble,thin,dot-matrix}-{100,200}-{WxH}.png` | Home's three digit clocks on a solid teal fixture backdrop. The hour has no leading zero, and the date line starts with the half day (`PM · Thu, Oct 29`). These use the host clock at render time. |
| `shade-{100,200}-{WxH}.png` | The shade. In landscape, its time reads `5:48 PM` (the host clock at render time). |
| `idle-clock-{100x30,40x60}.txt` | The idle clock screen's ANSI text frame. The hour is `5`, and the date line reads `PM · Thursday 29 October`. |

Observations and limits:

- The portrait shade draws no clock, at either text step. That is the
  existing portrait shade layout, and this change does not touch it. The
  shade's 12-hour form is shown in landscape only.
- In the portrait shade, "Loading preview" overlaps "Loading notifications".
  The fixture view has no notification data, so both placeholders draw. The
  overlap is outside this change's scope and is not a claim about the board.
- At 200%, the Date & time Date and Time zone values are elided in landscape.
  That is the accepted 200% layout from `settings-has-about-and-date-time-pages`.
- The Clock app uses the same `clock_digits`/`clock_date_line` helpers as the
  idle clock screen, and `tests/test_term_apps.py` covers it. It has no
  separate render here.
