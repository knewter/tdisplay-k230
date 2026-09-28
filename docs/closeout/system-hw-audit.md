# System/hardware closeout audit — 2026-09-28

Branch `close/system-hw`, base `master` at `38c264e4`. Scope: the nine
system/hardware OpenSpec changes named below. `theme-picker`,
`the-power-key-controls-the-display-and-power-menu`,
`the-system-runs-on-both-cores`/second-core and heartbeat changes are out of
scope and untouched.

Classification key:
- **(a)** done, evidence committed — task ticked, cited below.
- **(b)** superseded/obsolete — marked per the rules, replacement cited.
- **(c)** host-doable — done in this session, cited below.
- **(d)** needs the board, a physical action, or hardware this project does
  not own — left open, listed in `docs/closeout/board-checklist-system.md`.
- **(e)** unimplemented scope — genuine engineering work remains; left open.

No board or `/dev/ttyACM0` access was used to produce this audit. Every (a)/(c)
item below was proven by a command that does not touch the board.

## the-compositor-renders-ahead-of-scanout (1 open)

| Task | Classification | Citation / next step |
| --- | --- | --- |
| 1.4 Board, real finger: confirm no bottom-band flicker on the patch-free kernel | (d) | `nix/kernel.nix:56` confirms the vblank-latch patch is "deliberately NOT applied" in the current default kernel — the running board's kernel already *is* the patch-free kernel this task calls for. Needs an operator at the board with the camera; see checklist §A. |

## the-clock-survives-a-reboot (1 open)

| Task | Classification | Citation / next step |
| --- | --- | --- |
| 4.2 Full power-off (not just warm reboot) survival, left explicitly `UNVERIFIED` | (d) | Genuinely needs main power removed and restored on the physical board; no substitute. See checklist §A (piggybacks on the same session's reboot). |

## the-handheld-talks-bluetooth (1 open) — scope split staged, needs authorization

| Task | Classification | Citation / next step |
| --- | --- | --- |
| 4.1 Plug in a USB dongle, confirm `lsusb`/`bluetoothctl show`/`scan on`/`btmgmt info` | (d), hardware this project does not own | This project has no USB Bluetooth dongle at all, and `docs/research/bluetooth-onboard.md` confirms the board has no on-board Bluetooth of any kind — a dongle is the *only* path, not one option among several, so this is the "blocked on hardware the user doesn't have" case. **A successor change, `openspec/changes/the-handheld-pairs-over-a-usb-bluetooth-dongle/`, has been drafted and validates `--strict`** (`openspec validate the-handheld-pairs-over-a-usb-bluetooth-dongle --strict` → "is valid"), carrying task 4.1 and the `radio/bluetooth` requirement it grounds verbatim. **Not archived — needs your authorization** before the parent's finished Kconfig/BlueZ scope can be split off from this hardware-only gate (`the-handheld-talks-bluetooth/tasks.md` now notes this at 4.1). |

## the-handheld-configures-wifi-from-settings (4 open) — coordinate with `fix/wifi-password-keyboard`

Per instructions, this change was **read only** — no edits, no ticks, no builds run against files this other agent owns (`nix/rust-shell-client/src/wifi_ui.rs`). This table is audit-only.

| Task | Classification | Citation / next step |
| --- | --- | --- |
| 1.4 Package/confine the broker alongside `k230-wifi.service` | Appears complete; not ticked here | `nix/wifi-settings-broker.nix` + `nix/hardware.nix`'s `systemd.services.k230-wifi-settings` (root:shell socket, dedicated `RuntimeDirectory`, `UMask 0077`) exist and match the design. Ran (read-only, no repo changes) `nix build .#wifi-settings-broker --no-link --print-out-paths` → succeeded, and `bash tools/test-k230-wifi-persistent-service.sh` → "Persistent Wi-Fi service host checks passed" (confirms `k230-wifi.service`'s `LoadCredential` path is unchanged). The recovery timer the broker arms (`k230-wifi-settings-restore`) is a *transient* `systemd-run --on-active=35s` unit created at runtime (`tools/wifi_settings_broker.py:330-334`), not a static Nix unit — there is no missing-unit gap, despite first appearances. Recommend the wifi agent re-run these two commands and tick 1.4 itself. |
| 2.5 Cross-build `handheld-shell-rust` + coherent-shell toplevel, record identity | Not attempted here (read-only) | Build-only; leave to the owning agent since it's mid-edit on `wifi_ui.rs` in the same closure. |
| 3.1 Real-glass scan/connect/Forget acceptance | (d) | Needs board + the in-flight `wifi_ui.rs` rework to land first. |
| 3.2 Reboot, verify auto-reconnect and Forget-then-no-reconnect | (d) | Needs board; see checklist §A once 3.1 is ready. |

## the-handheld-plays-through-its-speaker (9 open) — no scope split needed

The user has no MAX98357A add-on and will test the Inno line-out path later.
Unlike Bluetooth, this change's own spec was written to close cleanly either
way: task 5.4's scenario is graded against "the recorded outcome, not a
source-level plausibility argument," and 5.5 explicitly says finding no
add-on "is the expected, honest outcome to record — not a bug in this
change." So **no successor is needed here** — every open task is completable
on the board this project already has; it is simply pending a board session.

| Task | Classification | Citation / next step |
| --- | --- | --- |
| 2.2b `dmesg` shows the External I2S Output Switch control bound | (d) | Needs `/boot` install + reboot. Checklist §A. |
| 4.2b `k230-speaker-test status` runs on the board | (d) | Checklist §A. |
| 5.1 `/proc/asound/cards`, `dmesg`, `aplay -l` after install/reboot | (d) | Checklist §A. |
| 5.2 `k230-speaker-test status` + `gpioinfo gpiochip1` | (d) | Checklist §A. |
| 5.3 `k230-speaker-test internal` — Inno regression check (line-out) | (d) | This is the "test line out later" the user named. Checklist §A. |
| 5.4 `k230-speaker-test external` — record which of the 3 documented outcomes occurs | (d) | Expected outcome given no add-on: "No add-on present" (only `CANAAN-K230-I2S` in `/proc/asound/cards`, command runs without error, nothing audible). This is a fully valid, gradeable result per the spec — not a failure. Checklist §A. |
| 5.5 Record whether the nRF52840 add-on is physically present | (d) | The operator's own statement in this session ("no speaker add-on") is a strong prior, but per this project's grounding rules (board observation over inference), the actual `aplay -l`/`k230-speaker-test status` reading during the §A session is what should ground this, not a chat statement — so left open rather than ticked from hearsay. |
| 6.1 `openspec validate --strict` + `render_work_board.py` | (d), gated | Blocked on 5.1-5.5 recording their evidence files first. |
| 6.2 Keep open if group 5 remains open | (d), gated | Same as 6.1; do not tick 5.1-5.5 without the evidence files existing (per this change's own group-6 rule). |

## the-system-enables-proven-c908-extensions (6 open)

| Task | Classification | Citation / next step |
| --- | --- | --- |
| 2.2 Bounded targeted implementation per additional useful extension (Zbb/Zba/Zbs etc.) | (e) | Genuine engineering work (runtime dispatch + physical benefit proof per extension); not started. Left open. |
| 3.1 Candidate image boots under QEMU (`tools/qemu-k230.sh`) | (c), not attempted this session | QEMU-only, no board needed — but the candidate (`sdImage-rvv-trial`) is an uncached riscv64 cross-build competing for the same Nix store as other agents' concurrent builds observed running on this machine during this session (`handheld-shell-rust`, `k230-coherent-shell` toplevel). Time-boxed out of this pass rather than risk a multi-hour background build; a legitimate quick win for a future session with a clear build slot. |
| 3.3 Board: candidate vector context + 192-case pixel checks | (d) | Checklist §B. |
| 3.4 Board: console/shell/Wi-Fi/card results on the candidate | (d) | Checklist §B. |
| 3.5 Board: return to known-good image, verify recovery | (d) | Checklist §B — mandatory after 3.3/3.4, same session. |
| 3.6 Board: select the proved image persistently, verify `/run/current-system` | (d), gated | Only after 3.3-3.5 all pass. Checklist §B. |

## the-screen-lights-before-linux (7 open)

| Task | Classification | Citation / next step |
| --- | --- | --- |
| 3.6 Hardware: second-card flash, photograph splash before `Starting kernel` | (d) | Checklist §A (needs a *second* card, kept separate from the known-good one). |
| 3.7 Hardware: `tools/panel-measure.py` on the U-Boot-lit image, check for roll | (d) | Same session as 3.6. |
| 4.3 Hardware: boot with nothing opening the display, confirm `/chosen` flag + no fbdev | (d) | Same session as 3.6/3.7. |
| 5.2 `boot.plymouth` if 5.1 is within budget | **(b) superseded/obsolete** | 5.1 measured 897.3 MiB vs. an 875 MiB budget (22.3 MiB over) — the file's own note says this "select[s] task 5.3 rather than 5.2." The conditional branch was not taken; 5.3 (the DRM splash program) was built and passed instead. Left unticked per this repo's existing convention for a not-taken conditional branch (see `the-shell-has-a-card-composition-plan/tasks.md` task 1.3's identical treatment) rather than falsely ticked. No further action needed. |
| 5.4 Hardware: film complete boot, splash → shell, no dark frame | (d) | Checklist §A. |
| 6.1 `k230.panelConsole` option, both states build, `true` omits `logo.xrgb` | (c), partially done this session | The option already exists exactly as specified: `nix/panel-console.nix` (default `false`), wired at `flake.nix:76` (`splashImage = if cfg.k230.panelConsole then null else bootSplashImage`), `nix/hardware.nix` and `nix/shell.nix`. This session re-ran and confirmed both `nix eval .#nixosConfigurations.k230.config.system.build.toplevel.drvPath` (false) and `...k230-console...` (true) succeed. The second half — `nix build .#sdImage` with the option flipped to `true` and inspecting the boot partition for `logo.xrgb`'s absence — was not run: a build slot was busy with concurrent agents' builds at the time, and the command implies a temporary source edit + revert. Noted in `tasks.md` 2026-09-28; one more quick build away from (a). |
| 6.2 Resolve `UNVERIFIED` markers against groups 3-5's captures | (d), gated | Blocked on 3.6/3.7/4.3/5.4 above. |

## the-shell-trials-vglite-composition (8 open)

| Task | Classification | Citation / next step |
| --- | --- | --- |
| 2.1 Target format/plane/stride/modifier handling | (e) | Renderer engineering; not started beyond the RGB565 case already proven in board trials (`docs/evidence/vglite-scene-board/padded/README.md`, `color-upload/README.md`). |
| 2.2 `wlr_texture_from_buffer` ownership + `WL_SHM` conversion/upload tests | (e) | Not started. |
| 2.3 Blend/clip/damage correctness vs. Pixman | (e) | Not started. |
| 2.4 Serialize VG-Lite submission, `vg_lite_finish`, cache-coherency proof | (e) | Not started. |
| 2.5 Compositor-only VG-Lite device access (no exposure to ordinary clients) | (e), partially researched | `docs/research/vglite-service-access.md` / `docs/evidence/vglite-service-access-host.md` exist (source design + host tests); the actual privileged broker/service and board device-node proof remain unimplemented. |
| 3.2 Board: repeated full-panel scene CPU comparison vs. Pixman | (d) | Checklist §A (opt-in package, no reflash — see below). |
| 3.3 Board: touch/keyboard/Apps/Back-Home/Terminal/Monitor under GPU + forced-Pixman | (d) | Checklist §A. |
| 3.4 Record results, run `openspec validate --strict` + `blob-scan.py --no-vendor` | (d), gated | Host half is quick once 3.2/3.3 land; blocked on their board data. |

These board tasks do **not** need a reflash: the opt-in VG-Lite Sway package
is a separate binary run alongside the already-installed coherent-shell
image (as the existing `docs/evidence/vglite-scene-board/*/README.md` trials
already did), so they piggyback on checklist §A's session rather than
requiring their own reboot.

## the-keyboard-follows-touch-gestures (5 open, now 4)

| Task | Classification | Citation / next step |
| --- | --- | --- |
| 1.2 Prove cancellation, keyboard-loss/output-change, and ordinary key/app isolation on the host fixture | **(a) done** | Ticked. Re-ran `python3 tests/test_keyboard_gestures.py -v`: 16/16 pass, including `test_contact_drain` (proves `kg_cancel`), `test_surface_loss` (proves `kg_surface(&p,false)`, keyboard/output loss) and `test_overlay_isolation` (an overlay-owned contact stays `KG_NONE`). Host policy evidence only, as the file already states. |
| 3.2 Board: real-finger show/type/hide/hold/reverse, camera capture | (d) | Checklist §A. |
| 3.3 Board: keyboard-gesture workload against responsiveness budgets | (d) | Checklist §A. |
| 4.1 Publish feature media + dashboard, push, inspect Pages | (d), gated | Needs 3.2's capture to exist first. |
| 4.2 Archive after all gates pass | (d), gated | Needs 3.2/3.3/4.1. |

## Summary of counts

| Classification | Count |
| --- | --- |
| (a) done this session | 2 (keyboard 1.2; screen-lights 5.2 recognized as already-superseded, not newly done) |
| (b) superseded/obsolete | 1 (screen-lights 5.2) |
| (c) host-doable, completed or partially completed this session | 2 (wifi 1.4 confirmed-but-not-ticked by audit rule since it's another agent's change; screen-lights 6.1 half-done) |
| (d) needs the board / physical action | 33 |
| (e) unimplemented scope | 7 (c908 2.2; vglite 2.1-2.5) |

Archived this session: **none**. Every change in scope has at least one
open (d) or (e) task, so per "Close OpenSpec changes deliberately," none
qualifies for archive yet. The one candidate for an early close —
`the-handheld-talks-bluetooth`, down to a single hardware-only gate — has
its scope split staged and validated, but **needs your authorization**
before the parent is archived and the successor opened in its place.
