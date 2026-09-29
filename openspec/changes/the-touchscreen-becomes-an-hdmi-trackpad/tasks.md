## 1. Research (no board needed)

- [x] 1.1 Evaluate (a) a hand-rolled relative-pointer uinput daemon, (b)
      existing projects (`ydotool`, generic `python-evdev`/`evdev-rs`
      emulators, the wlroots `zwlr_virtual_pointer_v1` protocol), and (c)
      a compositor-side patch; recommend one with tradeoffs on latency,
      permissions, and mode switching. Recorded in `design.md` decision 1.
      *Superseded mid-task by an operator requirements update (multi-finger
      gestures — pinch/swipe — required, "like a real laptop touchpad"):
      the recommendation changed from a relative-pointer daemon to
      re-emitting the touchscreen's real multitouch contacts through
      `uinput` as a virtual touchpad, so libinput's own already-shipped
      gesture engine does the recognition instead of this program.*

## 2. Host implementation and packaging

- [x] 2.1 `nix/touch-trackpad/src/relay.rs`: the touchscreen-to-touchpad
      protocol translator (contact-count-derived `BTN_TOUCH`/`BTN_TOOL_*`
      synthesis; `ABS_MT_*` passthrough). Verify:
      `cd nix/touch-trackpad && cargo test` (20/20 passing, including
      1/2/3-finger tap/drag/lift and a 2-to-1-finger transition case).
- [x] 2.2 `nix/touch-trackpad/src/mode.rs`: DRM-sysfs-based automatic mode
      detection (`HDMI* connected` -> trackpad, else direct-touch),
      fixture-tested for panel-only, HDMI-connected,
      HDMI-present-but-unplugged, and missing/unreadable sysfs. Verify:
      `cargo test` (same command as 2.1).
- [x] 2.3 `nix/touch-trackpad/src/{devsearch,touchdev,uinput}.rs`: find the
      touchscreen by its recorded input name
      ("Goodix Berlin Capacitive TouchScreen"), read its real `ABS_MT_*`
      ranges via `EVIOCGABS` to mirror onto the virtual device, and the
      hand-bound `uinput`/`EVIOCGRAB` ioctl surface (every ioctl number and
      the two on-wire struct sizes independently checked against the
      kernel UAPI in `cargo test`). Verify:
      `cargo test` (same command), plus one live host `/dev/uinput` device
      creation (`creates_and_destroys_a_real_virtual_touchpad_if_permitted`)
      whose `udevadm` classification is captured in
      `docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/host-uinput-classification.md`.
- [x] 2.4 `nix/touch-trackpad/src/main.rs`: the orchestration loop (poll
      mode via `poll(2)` on the touchscreen fd with the mode-check interval
      as timeout, so real touch events add no latency; start/stop a
      `TrackpadSession` on mode transitions; `--force-mode`/`--device`/
      `--drm-root` overrides for manual bring-up). Verify:
      `cargo build && cargo clippy --all-targets` (0 warnings).
- [x] 2.5 `nix/touch-trackpad/default.nix` + `flake.nix`'s
      `handheld-touch-trackpad` output, packaged the same way
      `nix/rust-shell-client` is (`rustPlatform.buildRustPackage`,
      `cargoLock.lockFile`, `doCheck = false` since the cross build cannot
      run a RISC-V test binary on the x86_64 host). Verify:
      `nix build .#handheld-touch-trackpad --out-link .build-out/handheld-touch-trackpad --max-jobs 2 --cores 8`
      — produced a riscv64 ELF binary at
      `.build-out/handheld-touch-trackpad/bin/k230-touch-trackpad`
      (store path `/nix/store/sklwlg9ncxa128qs58jjxnyqj5q4930l-k230-touch-trackpad-riscv64-unknown-linux-gnu-0.1.0`).
- [x] 2.6 `nix/touch-trackpad-service.nix`: a standalone, importable NixOS
      module (`k230.touchTrackpad.enable`) defining the systemd unit,
      deliberately not imported by `nix/shell.nix`/`nix/k230.nix` in this
      change (both are under active edit by the coordinator's
      `plugging-in-hdmi-moves-the-display` work). Verify: evaluates —
      `nix eval .#nixosConfigurations.k230.config.system.build.toplevel.drvPath`
      still succeeds unchanged (module not imported, so it cannot affect
      the built system yet); a real service-enabled build is board task
      3.1 below, once the coordinator has an HDMI DTB to boot it under.

## 3. Board verification (board-gated; not run by this change)

This change had no `/dev/ttyACM0`/board access (the coordinator owns the
board) and `plugging-in-hdmi-moves-the-display`'s manual HDMI switch is
itself not yet proven on hardware — these tasks cannot start before that
one does. Left open per AGENTS.md ("keep hardware-only tasks open until
their named physical proof exists").

- [ ] 3.1 Once `plugging-in-hdmi-moves-the-display` task 3.3 has a working
      board boot into the HDMI DTB: import `nix/touch-trackpad-service.nix`
      into the booted configuration and set
      `k230.touchTrackpad.enable = true;`, flash, and confirm under the
      reserved board/serial lock that the service starts and logs
      `mode -> Trackpad` once the HDMI connector reads `connected`:
      `flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=10 "journalctl -u k230-touch-trackpad -n 20 --no-pager"`.
- [ ] 3.2 With an HDMI monitor and the panel dark, drag one finger across
      the touchscreen glass and confirm the pointer moves on the monitor;
      tap once and confirm a left click; two-finger-tap and confirm a
      right click; two-finger drag and confirm scrolling; a pinch gesture
      and confirm zoom (in whichever Wayland client is focused). Capture a
      photograph or screen-recording of the monitor showing the response,
      per AGENTS.md's evidence-class distinctions (a console transcript
      alone does not prove pixels/pointer motion reached the monitor).
      Commit under `docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/board/`.
- [ ] 3.3 Reboot back to the panel DTB (or, if no-reboot switching exists
      by then, disconnect HDMI) and confirm over the console that
      `k230-touch-trackpad` logs `mode -> DirectTouch` and that the
      coordinator's direct absolute touch mapping still works exactly as
      before this change (an `evtest`/touch check per the existing
      `display/touch` evidence pattern). This is the proof that trackpad
      mode never regresses panel-mode touch.
- [ ] 3.4 Resolve this change's `specs/display/touch/spec.md`
      `<!-- UNVERIFIED -->` marker against the outcome of 3.1–3.3: either
      remove it with the board evidence committed, or restate the
      requirement against whatever was actually observed (including a
      documented shared-GPIO23/24 interaction with the LT9611 bridge, if
      one is found).

## 4. Proposal validation

- [x] 4.1 Validate this change:
      `openspec validate the-touchscreen-becomes-an-hdmi-trackpad --strict`
      (exit code checked directly).
- [ ] 4.2 Hand off to the coordinator for an early merge to `master` per
      AGENTS.md, independent of whether group 3 has started — the
      proposal, the host-tested prototype, and the packaged binary are the
      reviewable deliverable now, not a private preface to board work that
      depends on another still-open change.
