## 1. Host: readers, rows and pages

- [x] 1.1 Add `device_info.rs` (readers, page state, layout, Back hit-test) and
  the Date & time and About rows after Cellular and Location, with their
  intents, paint, scroll extent and wiring in `main.rs`. Proof:
  `cargo test --offline` in `nix/rust-shell-client` (625 lib tests passed, and
  every integration test including the 568x1232 pixel-identity check). This is a
  host proof.
- [x] 1.2 Tests for the readers (fixture tree), the hit regions and the layout
  at 100% and 200%, in both orientations. Proof: `device_info::tests` and
  `service_ui::tests::settings_ends_its_rows_with_date_and_time_then_about`,
  inside the same `cargo test --offline` run.

## 2. Host renders

- [x] 2.1 Render Settings, About and Date & time at 1232x568 and 568x1232, at
  100% and 200%. Proof: `docs/evidence/settings-about/host/` from
  `cargo run --offline --example render_settings_about_evidence`, and
  `python3 tools/blob-scan.py` (ok). Host render with fixture values only.
- [x] 2.2 Regenerate `docs/evidence/shell-responsive/settings-*.png`, which
  gained two rows. Proof: `cargo test --offline --test responsive_pixel_identity`.

## 3. Board (hardware-only)

- [x] 3.1 Test-activate the build and capture Settings, About and Date & time
  with grim at both orientations. Proof: `docs/evidence/settings-about/board/`.
  Operator command: `./tools/msh.py` session on the board, then
  `grim` per `docs/evidence/help-refresh/` practice, after
  `nix build .#nixosConfigurations.k230.config.system.build.toplevel --out-link <scratch>/system`
  and a live `switch-to-configuration test`.
  *Done: About and Date & time in landscape on `kllh24ww…` (2026-10-27). Settings in both orientations, and About and Date & time in portrait, on `vf91pbq6…` (2026-10-28, live output rotation, not a portrait image). `docs/evidence/settings-about/`.*
- [x] 3.2 Record on the board whether `/run/systemd/timesync/synchronized`
  exists after sync, and that About's system hash equals
  `readlink /run/current-system` there. Proof:
  `./tools/console.py /dev/ttyACM0 --wait=3 "ls -l /run/systemd/timesync/ /run/current-system; cat /etc/hostname /proc/sys/kernel/osrelease"`
  saved under `docs/evidence/settings-about/board/`. Until then the sync row stays
  UNVERIFIED.
  Done 2026-10-27T03:53:32Z over SSH (build `kllh24ww…`): `/run/systemd/timesync/synchronized` exists (22:45 local), and About's System reads `kllh24ww · nixos-system-…`, matching `readlink /run/current-system`. `docs/evidence/settings-about/README.md`.
- [ ] 3.3 The operator reads both pages on glass. Physical proof: a timestamped
  operator report tied to the installed build.

## 4. Follow-ups, recorded and not started

- [ ] 4.1 A 24/12-hour preference: state in the settings broker and every clock
  consumer reading it. Needs its own proposal.
- [ ] 4.2 Changing the time zone and NTP from the device: needs a design for
  privilege and persistence, since `time.timeZone` is build-time. Needs its own
  proposal.

## 5. Promotion

- [ ] 5.1 After review, merge to `master`, push, check CI, and archive with
  `openspec archive` only once tasks 3 and 4 are decided (4 may move to a
  successor proposal; see AGENTS.md on scope splits).
