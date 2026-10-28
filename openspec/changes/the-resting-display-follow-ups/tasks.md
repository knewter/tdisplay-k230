## 1. Idle timeout setting (from idle 4.1)

- [ ] 1.1 Add the Settings row for the timeout (Off / 1 min / 5 min), persisted beside the
  existing settings and read by `shell-idle` at start. Needs its own Rust service request.
- [ ] 1.2 Host: unit tests for the pref read and the swayidle arguments it produces.
  Proof: `python3 -m pytest tests/ -k idle` and `cargo test` for the settings request.
- [ ] 1.3 Board, injected: pick 5 min; the panel dims at 150 s and turns off at 300 s; pick
  Off; neither happens in 6 min. Proof: journal `output * power` and DCS brightness lines.

## 2. HDMI unplug wake (from idle 4.2)

- [ ] 2.1 The HDMI-unplug wake in `nix/touch-trackpad/src/shell_ipc.rs` powers the display on
  without reporting activity; make it run `k230-idle-dimmer wake` so the panel does not stay
  dim. Proof: `cargo test` in `nix/touch-trackpad`.
- [ ] 2.2 Board: dim the panel, then unplug HDMI (operator); brightness returns to the saved
  value and the next dim comes a full timeout later.

## 3. Decisions (from idle 4.3)

- [ ] 3.1 Decide whether charging should defer idle off, and whether the wallpaper video should
  stop decoding while the display is off. Record the decision and any measurement here.

## 4. Clock screen follow-ups (from exhibition 5.1–5.5)

- [ ] 4.1 Notification-count dot on the card (needs the broker count).
- [ ] 4.2 A separate Exhibition brightness, and a setting for the two-hour cap and the effect
  interval.
- [ ] 4.3 Close the card on pointer-only activity (HDMI mouse) as well. Board proof with a
  mouse: the card closes and the app beneath gets nothing.
- [ ] 4.4 A shade tile or a Home action to start the exhibition on demand.
- [ ] 4.5 Camera (exhibition 4.7, moved 2026-10-28 when the operator reassigned the webcam;
  optional, gates nothing): the webcam on the panel records a clock minute change, one
  position drift and one effect. Look at consecutive raw frames first. Camera evidence, not
  glass, not injected.

## 5. Closeout

- [ ] 5.1 Archive when every task above is done, or after an explicit, user-approved split.
  Proof: `openspec validate the-resting-display-follow-ups --strict`.
