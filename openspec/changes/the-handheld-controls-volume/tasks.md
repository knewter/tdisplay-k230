All tasks below name the narrowest real command that proves them. Host
build and QEMU capture are one evidence class; a console transcript, an
audible check, or a real-finger/real-key observation from the physical
board is a different one, and no task here claims the second from the
first. Board evidence, once it exists, is stored under
`docs/evidence/volume/board/` with commands, timestamps and limits; the
host/QEMU evidence already produced by this worktree lives at
`docs/evidence/volume/`.

## 1. PipeWire/WirePlumber session layer (Nix)

- [x] 1.1 Add `systemd.services.pipewire`/`wireplumber`/`pipewire-pulse`
      to `nix/shell.nix` (`k230.shell.coherentShell`-gated, plain system
      units with `User = "shell"`, bound to `shell.service`'s lifecycle),
      and the two ALSA plugin config files that redirect mpv's existing
      direct-ALSA output through PipeWire without rebuilding mpv. Proven:
      `nix build .#nixosConfigurations.k230-coherent-shell.config.system.
      build.toplevel --max-jobs 1 --cores 6 --no-link --print-out-paths`
      (task 7.2) includes these units in the closure.
- [x] 1.2 Add hardware/keyboard volume key bindings
      (`XF86AudioRaiseVolume`/`LowerVolume`/`Mute`) to the generated Sway
      config, calling `wpctl` directly with no separate signal to the
      Rust client. Proven: same closure build; `docs/research/board-
      capability-inventory.md` cited for what this board's own inputs are
      known (and not known) to emit.
- [x] 1.3 Trim `pipewire`'s own closure: `nix/shell.nix`'s `pipewireLean`
      override disables `bluezSupport`/`vulkanSupport`/`x11Support`/
      `raopSupport`/`rocSupport`/`zeroconfSupport` (design.md Decision 9)
      -- this board has no onboard Bluetooth
      (`docs/research/bluetooth-onboard.md`) and none of the other four
      backends are used by this board's volume UX. `ffmpeg`/`gstreamer`
      support stay on (nixpkgs 1.6.8 hardcodes both, not exposed as
      override parameters); the remaining cost is recorded, not hidden,
      in `docs/evidence/volume/closure-size.md`. Proven: task 6.4's
      second toplevel build (with the override) succeeds and that
      evidence file's own before/after numbers.
- [ ] 1.4 Board proof: confirm `systemctl status pipewire wireplumber
      pipewire-pulse` all report `active` after a board boot with this
      change installed, and record `wpctl status` showing at least the
      Inno codec sink. **Partially done via the coordinator's own board
      test** (system `z3zbk6gx8j5gd2pzamrzg5vapa0bjwnd`, this branch
      before the fixes below): all three services were confirmed `active`,
      but `wpctl status` showed only a "Dummy Output" sink and `wpctl`
      itself was unreachable from the running client -- both real bugs,
      fixed here (`docs/evidence/volume/board/pipewire-services-active.md`
      has the full diagnosis): the `shell` user's missing `audio` group
      membership (blocking WirePlumber's ALSA monitor from opening
      `/dev/snd/*`), and `wpctl`/`pw-dump`/`pw-cli` not reliably reachable
      via `PATH` alone (now also passed as absolute store paths via
      `K230_WPCTL`/`K230_PW_DUMP`/`K230_PW_CLI`). **Neither fix has been
      re-verified on the board yet** -- this worktree cannot touch the
      board (AGENTS.md); still open until that round trip happens.

## 2. Volume model and shared slider component (Rust, pure/unit-tested)

- [x] 2.1 Generalize `slider.rs`'s brightness-only floor into
      `clamp_percent_with_floor`/`value_at_x_with_floor`/`Drag::
      start_with_floor`, keeping the existing `MIN_PERCENT`-floor
      wrappers unchanged for brightness's own call sites. Proven:
      `cargo test --lib` (`slider::tests::*`, including the brightness-
      floor-equivalence and volume-floor-reaches-zero cases).
- [x] 2.2 Add `volume.rs`: the cubic percent<->linear curve
      (`percent_to_linear`/`linear_to_percent`/`percent_to_db`),
      `VolumeState` (level + separate mute flag, drag-to-mute, icon-tap
      mute toggle, external-report reconciliation), `IconState`,
      `ChangeOrigin`, and `Hud` (visibility timing, expand/collapse,
      draggable position). Proven: `cargo test --lib` (`volume::tests::*`,
      27 tests covering the curve, mute semantics, HUD timing/expand/
      drag).

## 3. PipeWire graph parsing and process ownership (Rust)

- [x] 3.1 Add `pipewire_ipc.rs`: `parse_dump`/`Accumulator` (a running
      graph model that survives per-change deltas without losing
      untouched sinks/streams), `spawn_monitor`/`run_monitor_reader` (the
      persistent `pw-dump --monitor` reader thread), and `Writer`/
      `WriterHandle` (the persistent `pw-cli` writer child plus its
      command queue) and `set_volume_command`. Proven: `cargo test --lib`
      (`pipewire_ipc::tests::*`, including a real child-process round
      trip for the writer and fixture-replay tests against captured JSON
      shapes).
- [x] 3.2 Capture real `pw-dump`/`pw-dump --monitor`/`wpctl` output on a
      development host's own PipeWire session (not this board) to ground
      the parser's object schema and the cubic-curve claim, and record it
      in `docs/evidence/volume/wpctl.md` and the fixtures under
      `tests/fixtures/pipewire/`. Proven: the recorded captures plus the
      `application.icon-name` (not `-icon_name`) key confirmed directly
      against this machine's installed `pipewire/keys.h`
      (`PW_KEY_APP_ICON_NAME`).
- [ ] 3.3 Board proof: capture this board's own `pw-dump` output once
      task 1.3 passes, and confirm the Inno codec sink's real
      `node.name`/`node.description` match (or update) the assumption
      the fixtures in 3.2 encode. **Not done in this worktree.**

## 4. Touch dispatch, gesture disambiguation, and rendering

- [x] 4.1 Add the volume slider's touch band to `service_ui.rs`
      (`slider_band`'s existing Settings-row/Shade-header convention,
      shifted for the added row) and fold it into
      `shade_panel_close_zone`'s existing carve-out, so a horizontal drag
      on the volume slider is never promoted into a close drag, matching
      the brightness slider's own guarantee. Proven: `cargo test --lib`
      (`volume_slider_band_owns_its_row_and_is_excluded_from_the_close_
      drag_candidacy`, alongside the pre-existing brightness case).
- [x] 4.2 Arm/track/finalize the volume slider drag in `main.rs`'s touch
      handlers (a sibling branch beside the existing brightness-slider
      arm), wire the speaker-glyph mute tap (own touch-id-owned zone, so
      a tap on the icon can never be read as a drag to 0) and the HUD's
      own show/hide/expand/drag touch handling, plus a `VOLUME_ECHO_
      GRACE_MS` window so this shell's own `wpctl` commits (mute tap,
      device pick) are never mistaken for an external change and do not
      spuriously raise the HUD. Proven: `cargo test --lib` (whole crate,
      283 passed / 0 failed) and `cargo clippy --lib`/`--all-targets`
      report no warning attributable to `main.rs`/`service_ui.rs`/
      `render.rs`/`service_data.rs`/`slider.rs`/`volume.rs`/
      `pipewire_ipc.rs` (the two pre-existing warnings `--all-targets`
      surfaces, in `main.rs::running_con_id` and the unrelated,
      already-broken `tests/theme_catalog_module.rs` integration test,
      are confirmed pre-existing on `master` by a stash-and-rebuild
      check, not introduced here, and are out of this change's owned
      paths).
- [x] 4.3 Paint the volume slider under the brightness slider in
      Settings and the Shade (reusing `paint_slider_track`, a mute-aware
      speaker glyph in place of the sun glyph), and paint the HUD
      (collapsed pill, expanded per-stream/sink list with a default-sink
      marker dot) via `render.rs`'s shared `RendererCache::
      paint_hud_overlay` (task: "render the HUD only while visible" -- an
      early return before any Cairo work when `!hud.is_visible`), reached
      two ways: `draw_hud` (its own isolated canvas, used by that
      function's own unit tests) and `draw_with_hud` (composited directly
      onto `draw()`'s live canvas -- the one `main.rs` actually attaches
      to a Wayland surface; `draw()` itself stays a thin wrapper calling
      `draw_with_hud` with a never-shown `Hud::default()`, so none of
      this module's other ~45 pre-existing `renderer.draw(...)` call
      sites needed touching). First QEMU capture attempt
      (`tests/volume_hud_qemu.py`) found `draw_hud` was written but never
      actually called from `main.rs` at all -- the HUD state machine and
      touch dispatch were real and tested, but nothing painted it onto
      the surface a person would actually see; `draw_with_hud`/the
      `main.rs` wiring above is that fix, not a pre-existing feature.
      Proven: `cargo test --lib` (`render::tests::draw_hud_*` plus the
      new `draw_with_hud_composites_the_pill_on_top_of_the_live_settings_
      scene`, which specifically catches a regression back to "painted
      but never reaches the live canvas").
      **Known, still-open gap**: `draw_with_hud` only paints while the
      overlay layer surface is already mapped (a Drawer/Shade/Settings
      sheet open) -- `main.rs`'s touch dispatch (`hud_touch_down`) is
      already fully route-independent, but nothing yet forces this layer
      surface to exist purely because the HUD wants to show while the
      Home screen alone is visible with nothing else open (`render.rs`'s
      own doc comment on `draw()` names this precisely). A hardware
      volume key pressed with nothing open would today update `service_
      view.audio`/the Settings-row slider correctly but show no HUD until
      some other route happens to open. Left open rather than
      papered over; the QEMU capture below exercises the case that does
      work (shade open) since that is what could actually be proven
      inside this remaining budget.
- [x] 4.4 Wire the PipeWire monitor/writer into `main.rs`'s own event
      loop: `pipewire_events`/`pipewire_writer` are spawned once at
      startup (`pipewire_ipc::spawn_monitor`/`WriterHandle::spawn`) and
      drained via `try_recv` on the loop's own existing wake cadence
      (the same opportunistic-drain convention `services`/`wifi_worker`/
      `themes` already use -- no dedicated polling thread or timer of
      its own). Proven: `cargo test --lib` (`apply_pipewire_event`'s own
      HUD-suppression logic exercised indirectly via `volume::Hud`/
      `ChangeOrigin` unit tests; the process-spawning half is exercised
      by `pipewire_ipc`'s own real-child-process tests).
- [x] 4.5 Settings' own device-picker entry point: the volume row's "tap
      to change output" detail line (`service_ui::settings_output_
      picker_hit`) expands the same HUD panel `tap_hud_row`'s sink rows
      already drive, rather than a second, duplicate list (design.md's
      "one picker, two entry points"). Proven: `cargo test --lib`
      (`settings_output_picker_hit_is_settings_only_and_needs_a_default_
      sink`).

## 5. Output device picker

- [x] 5.1 List `pipewire_ipc::GraphSnapshot::sinks` in the expanded HUD
      panel (`paint_hud_row`'s `ExpandedRow::Sink` arm: description text
      plus a filled/hollow default-marker dot) and reach the same panel
      from Settings (task 4.5), calling `wpctl set-default ID` on a pick
      (`main.rs::pick_output_sink`). Proven: `cargo test --lib`
      (`draw_hud_expanded_panel_is_taller_and_wider_than_the_collapsed_
      pill` exercises a sink row's own paint path; `tap_hud_row`'s sink
      branch is a direct, small function reachable from the same tests
      that cover its stream-row sibling).

## 6. Build proof

- [x] 6.1 `cargo test` for `nix/rust-shell-client`: `--lib` (284 passed /
      0 failed), plus `appearance_module`/`background_decode_module`/
      `service_data_module` (21 + 8 + 11 passed / 0 failed) -- run in
      the foreground. `tests/theme_catalog_module.rs` fails to compile
      on this branch **and on unmodified `master`** (a stash-and-rebuild
      check confirmed this before touching anything) -- pre-existing
      breakage in a file this change does not own or touch, not a
      regression from this work.
- [x] 6.2 `cargo clippy --lib` and `cargo clippy --all-targets` report no
      warning attributable to this change's files (see 4.2's own note on
      the two pre-existing warnings `--all-targets` surfaces elsewhere).
      One real regression this change itself introduced was caught and
      fixed here: adding `SettingsSnapshot::volume` pushed `ServiceResponse`
      over clippy's `large_enum_variant` threshold; `Settings` is now
      `Box<SettingsSnapshot>` (`service_data.rs`), with its two call
      sites updated.
- [x] 6.3 `nix build .#handheld-shell-rust --max-jobs 1 --cores 6
      --print-out-paths` -- run in the foreground three times across this
      work (mid-work, after the closure-trimming override, and against
      the final staged source including the `draw_with_hud` fix): final
      store path `/nix/store/7imslxpfxnam1zwmcvfng048hwl3z7a1-k230-shell-
      rust-riscv64-unknown-linux-gnu-0.1.0`.
- [x] 6.4 `nix build .#nixosConfigurations.k230-coherent-shell.config.
      system.build.toplevel --max-jobs 1 --cores 6 --no-link
      --print-out-paths` -- run in the foreground four times: three
      across the `pipewireLean`/`wireplumberLean` closure-trimming work
      (design.md Decision 9: `/nix/store/gwl36r94h1vjh0038d0nm3c7ikzlgl6m-...`
      untrimmed, `/nix/store/qcd1vqsip5ha0cdv3ag30qc8j7laxjzs-...`
      `pipewire` trimmed only, `/nix/store/2yhpy7fg6l5hl0dij41si99xfw0
      spyj5-...` both trimmed) and a fourth, final run against the fully
      staged source including the `draw_with_hud` live-canvas fix (task
      4.3): `/nix/store/s32hb4i8mfm15w7bacskjyr8spk3bgcs-nixos-system-
      nixos-26.11.20260919.20b1ddd`. `docs/evidence/volume/closure-
      size.md` has the full, honest closure-size result from the first
      three: the override is correct (every unit/process this change
      spawns runs the trimmed package) but produced **no net closure-size
      reduction**, for two independent, traced reasons recorded there (a
      pre-existing `hardware.bluetooth.enable=true` already keeping
      `bluez`/etc. reachable regardless, and a NixOS-internal ALSA-
      plugins aggregate this change does not control still pulling in the
      stock `pipewire`) -- left as a named, open follow-up rather than
      claimed solved.

## 7. QEMU host evidence

- [x] 7.1 `tests/volume_hud_qemu.py` (a narrow, purpose-built extension of
      `rust_service_surface_qemu.py`'s own harness, importing its
      `Broker`/`SETTINGS_FIXTURE`/`wait_for` rather than duplicating them)
      captures: the shade with both the brightness and volume sliders
      (`shade-both-sliders.png`), the HUD raised by a synthetic external
      PipeWire change and shown collapsed (`hud-collapsed.png`), and the
      HUD expanded to its per-stream/per-sink device-picker panel
      (`hud-expanded.png`). Screenshots and blob-inventory rows committed
      under `docs/evidence/volume/` (`README.md` has the full narrative,
      including the real `draw_with_hud` wiring gap this capture attempt
      itself found and task 4.3 above then fixed). `python3 tools/
      blob-scan.py --no-vendor` exits 0.

## 8. Close deliberately

- [x] 8.1 `openspec validate --strict the-handheld-controls-volume` and
      `python3 scripts/render_work_board.py > /dev/null` both re-run
      after task 7.1's evidence landed: both exit 0. Rerun once more
      before archiving, in case anything lands between now and then.
- [ ] 8.2 Keep this change open with groups 1.4, 3.3, 7, and every
      board/audible task in group 9 unchecked until their named physical
      proof exists; do not tick them from a host or QEMU run.

## 9. Physical acceptance (board, open; this proposal claims none of these)

- [ ] 9.1 Real-finger drag and tap-to-mute on the Settings and Shade
      volume sliders, confirming the sink's actual volume follows the
      finger live and that dragging to the bottom mutes rather than
      merely reading zero. **Not done in this worktree.**
- [ ] 9.2 A line-out/headphone audible check: play a known tone or clip
      through the Inno codec sink with headphones connected, drag the
      volume slider, and confirm the audible level tracks it, including
      down through mute. **Not done in this worktree** -- see the report
      for the exact operator command.
- [ ] 9.3 If `the-handheld-plays-through-its-speaker` has landed its
      kernel patch on this board by the time this is run, confirm whether
      its external-I2S route appears in this change's own device picker
      as a separate sink, and record whichever outcome is observed (see
      that requirement's own UNVERIFIED note). **Not done in this
      worktree.**
- [ ] 9.4 If any attached keyboard is confirmed to emit
      `XF86AudioRaiseVolume`/`LowerVolume`/`Mute`, confirm the bound key
      changes the volume and raises the HUD on real hardware. **Not done
      in this worktree** -- no such keyboard is confirmed attached.
- [ ] 9.5 Confirm on hardware that the HUD auto-hides after about 2.5s,
      can be dragged along the edge, and that its expand affordance shows
      real per-app streams (e.g. a played video's own stream) with
      correct app name/icon. **Not done in this worktree.**
