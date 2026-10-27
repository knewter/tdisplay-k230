# Modem shell UI: host renders (tasks 6.1 and 6.2)

**Evidence class: host.** These are renders of the shell client on the build
machine, made from the fake service state files beside them. They are not board
captures; those belong to task 6.3.

The renders were made with:

```
cargo run --offline --example render_modem_evidence -- <dir>
```

That command writes each surface at 1232x568 and 568x1232. Only the landscape
renders are committed, because the device runs landscape.

Each image shows:

- `settings-no-modem`: no Cellular or Location rows (`present` false).
- `settings-with-modem`, `settings-with-modem-no-sim`: the rows at the head of the Power column.
- `cellular-*`:
  - registered;
  - off;
  - no SIM (as on the fitted unit);
  - PIN entry on the page's own keypad.
- `location-*`: off, searching and fix. No position is shown.
- `shade-*`: no modem, both off (no indicators), three bars, both searching, a fix with no service, and both searching with no battery.

The tests are `cargo test --offline --lib` in `nix/rust-shell-client`: 612
pass, against 584 before. They cover:

- hidden pages;
- absent indicators;
- searching vs fix;
- the bars mapping;
- PIN digits and SMS bodies never appearing in `Debug` output;
- a fake SMS becoming a notification whose preview hides the body.

## Limits

- **How texts reach the shell.** The service writes received texts only to
  its store, `sms.jsonl`, and the shell tails that file. On the board on
  2026-10-26 the shell user could not read the store at its first location,
  `/var/lib/k230/modem/`, because `/var/lib/k230` is root-only (`0700`). The
  store now lives in `/var/lib/k230-modem/` (`0750 root:k230-modem`), and the
  service moves the old files there once.
- **Notification source.** It is "Shell". The sender's number is in the
  summary instead.
- **Not tested.** No SIM, so no real text, PIN or registration has been
  exercised.
