## 1. Design check (board, read-only)

- [x] 1.1 Settle the privileged path and persistence. Record on the board
  whether `timedatectl` and polkit are present, what `/etc/localtime` points
  at, and whether `timedatectl set-timezone` fails with the current
  configuration. Then update design.md's Decisions. Proof (board, read-only):
  the console transcript under `docs/evidence/time-zone/board/`.
  *Board, read-only, 2026-10-30, on `p393r76c…`: no polkit, and the link is
  managed. `set-timezone` run as `shell` is denied. The decision is a
  socket-activated root helper with two commands (design.md).*

## 2. Host

- [x] 2.1 Implement the Nix change and the privileged path chosen in 1.1.
  Proof (host build):
  `nix build .#nixosConfigurations.k230-mainline-drm-shell-landscape-hdmi.config.system.build.toplevel`.
  *Host build, 2026-10-30: `sqd58h8c…`. `time.timeZone = null` with a
  first-boot America/Chicago link (`nix/k230.nix`); `k230-time.socket` and
  `k230-time@.service` (`nix/time-settings.nix`) run
  `tools/k230_time_helper.py`, and `python3 tests/test_time_helper.py`
  passed (11). Running clocks re-read the zone through `tzset`
  (`home_widgets::clock::reread_zone`, `k230_term_apps.local_time`).*
- [x] 2.2 Add the zone list and the network-time switch to the Date & time
  page. Proof (host): `cargo test --offline --lib` in `nix/rust-shell-client`,
  and renders at 100% and 200% under `docs/evidence/time-zone/host/`.
  *Host, 2026-10-30: `cargo test --offline` passed (687 lib tests and every
  integration test), including the chooser's area/zone/back walk, paging at
  every text step, and floor-sized targets. `python3 tests/test_term_apps.py`
  passed (40). There are 20 renders with a README.*

## 3. Board (hardware-only)

- [x] 3.1 Test-activate the build. Change the zone and network time with
  injected touch, and record `timedatectl` and a grim capture. Then run
  `switch-to-configuration test` and reboot, and record both again. Confirm
  that the shell user cannot set anything else through the path. Proof
  (board, injected): `docs/evidence/time-zone/board/`.
  *Board, injected, 2026-10-30, on `sqd58h8c…`: Europe/London was applied
  in 1.5 s, and the shade and Clock app followed with no restart. Network
  time off stopped timesyncd. Both held across `switch-to-configuration
  test` and across a reboot after promotion. Six other requests from `shell`
  were refused, `nobody` cannot open the socket, and root gets
  `error peer`. Restored to America/Chicago with network time on.*
- [x] 3.2 Glass: the operator changes the zone and reads the clocks. Physical
  proof: a timestamped operator report tied to the installed build.
  *Replaced by the operator on 2026-10-30 ("land them just test yourself you
  don't need my fingers on the glass just do virtual events and watch
  screenshots or whatever",
  `docs/evidence/glass-checklist-2026-10-29/operator-report.md`). Closed by
  task 3.1's injected run on `sqd58h8c…`, the installed boot default. That
  run changed the zone and read the clocks from `grim` captures. No glass
  reading is claimed.*

## 4. Closeout

- [x] 4.1 Archive once 3.2 is done. Proof:
  `openspec validate settings-sets-the-time-zone-and-network-time --strict`.
  *2026-10-30: valid before archive; the specs were synced and
  `openspec validate --specs --strict` passed after.*
