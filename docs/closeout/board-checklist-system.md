# Board checklist — system/hardware closeout (2026-09-28)

For the coordinator/operator. Nothing in this file has been run against the
board by the closeout audit — it was produced without touching
`/dev/ttyACM0`. Commands use
`flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=N '<cmd>'`
per the shared-board rule in `AGENTS.md`; say when you take the board and
when you release it. Camera is `/dev/video0`.

Two sessions. **Session A** is one flash of the already-current
coherent-shell image and covers seven of the nine changes in one reboot
cycle (plus a full power-off at the end for the clock). **Session B** is a
separate candidate-image flash/recover cycle for the C908/RVV trial, which
must not be left as the persistent image.

---

## Session A — coherent-shell image (compositor, clock, bluetooth, speaker, wifi, keyboard, vglite)

The current `nix/kernel.nix` already carries the RTC, Bluetooth, backlight
and speaker-route patches together, and is already the "patch-free" kernel
the compositor change's task 1.4 needs (see `nix/kernel.nix:56`). One image
covers all of the below.

### A.0 Build (host, before taking the board)

```sh
nix build .#kernel --max-jobs 1 --cores 6 --no-link --print-out-paths
nix build .#deviceTree --max-jobs 1 --cores 6 --no-link --print-out-paths
nix build .#sdImage-coherent --max-jobs 1 --cores 6 --no-link --print-out-paths
nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel --max-jobs 1 --cores 6 --no-link --print-out-paths
```

Record all four store paths in the handoff.

### A.1 Flash and confirm

Per `docs/uboot-ums.md` / `docs/evidence/usb-host-validation.md`: flash
`sdImage-coherent` via `ums 0 mmc 1` + `tools/flash-latest.sh --ums`, or the
card-reader fallback. Reboot, then:

```sh
flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=3 'uname -a'
flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=3 "readlink -f /run/current-system"
```

**Pass:** the reported kernel/build and `/run/current-system` match the
store paths from A.0. Evidence: `docs/evidence/keyboard-gestures/installed-preview/` (append a new dated entry, or start a fresh one if this is a later build).

### A.2 Compositor — real-finger bottom-band flicker (`the-compositor-renders-ahead-of-scanout` 1.4)

With the camera on the bench (not touch — this is a visual check):

- Operator performs bottom-edge app switching and opens the card overview
  with a real finger, repeatedly, while the camera records consecutive
  full-resolution frames.
- **Pass:** no one-frame bright/dark spike in the bottom band across the
  sequence, matching the 720-frame injected-gesture result already on file
  (`docs/evidence/card-shell/bottom-band-flicker/kernel-patch-boot-panic.md`).
- **Fail signature:** a one-frame spike at the bottom edge during a
  transition — record the frame pair and re-open task 1.4 rather than
  guessing at a fix from this single session.

Evidence: `docs/evidence/card-shell/bottom-band-flicker/` (new operator
report, system path, camera frames).

### A.3 Bluetooth (`the-handheld-talks-bluetooth` 4.1) — only if a USB dongle is available

**Skip this step if no dongle is on hand — that is the expected state per
this audit; do not force it.** If a dongle becomes available, this is
exactly `the-handheld-pairs-over-a-usb-bluetooth-dongle`'s task 1 (staged,
not yet authorized):

```sh
flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=2 'lsusb'
flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=3 'bluetoothctl show'
flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=12 'bluetoothctl scan on'
flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=3 'btmgmt info'
```

**Pass:** `lsusb` lists the dongle; `bluetoothctl show` reports a powered
controller; `scan on` prints `[NEW] Device ...` lines; `btmgmt info` shows
`powered`/`running`. **Fail signatures:** see
`docs/evidence/backlight-bluetooth-rtc-board-test-plan.md` §3 (the
LILYGO-quirk failure mode: dongle enumerates but never reaches
`powered`/`running`). Evidence: `docs/evidence/bluetooth/` (sanitized — no
MAC addresses/SSIDs of nearby devices).

### A.4 Speaker (`the-handheld-plays-through-its-speaker` 2.2b, 4.2b, 5.1-5.5)

```sh
flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=2 'dmesg | grep -iE "canaan-k230-snd-inno|External I2S"'
flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=2 'cat /proc/asound/cards'
flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=2 'aplay -l'
flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=2 'k230-speaker-test status'
flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=2 'gpioinfo gpiochip1'
flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=3 'k230-speaker-test internal'
flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=3 'k230-speaker-test external'
```

- **A.4.1 (2.2b/5.1):** `dmesg` shows the `canaan-k230-snd-inno` module and
  (if the patch bound) an "External I2S Output Switch" control;
  `/proc/asound/cards` and `aplay -l` show `CANAAN-K230-I2S`.
- **A.4.2 (5.2):** `k230-speaker-test status` and `gpioinfo gpiochip1` show
  GPIO32/33/34/35 named per `nix/dts/k230-tdisplay.dts`'s
  `gpio-line-names`.
- **A.4.3 (5.3, "test line out later"):** operator listens on headphones/
  line-out during `k230-speaker-test internal` — **pass** if audio sounds
  exactly as it did before this change (regression check, not a new
  feature).
- **A.4.4 (5.4/5.5):** operator listens (or records with a phone/mic near
  the board, per `docs/evidence/use-the-camera-not-the-user.md`-style
  discipline — don't infer the outcome, capture it) during
  `k230-speaker-test external`. **Given the user has no MAX98357A add-on,
  expect and record the "No add-on present" outcome**: command runs without
  error, only `CANAAN-K230-I2S` in `/proc/asound/cards`, nothing audible.
  That is a complete, passing result for 5.4/5.5 per the change's own
  grading rule — not a partial failure.

Evidence: `docs/evidence/max98357a-speaker/` (create it; the change's own
tasks.md group 5 proof text names this path). Then:

```sh
openspec validate --strict the-handheld-plays-through-its-speaker
python3 scripts/render_work_board.py > /dev/null
```

closes 6.1/6.2 once the group-5 evidence file exists.

### A.5 RTC full power-off (`the-clock-survives-a-reboot` 4.2)

Warm-reboot RTC survival is already proven
(`docs/evidence/rtc/mday-mask-fix.md`); only the full-power-off case is
open. Do this **last** in session A, after A.2-A.4, so the board is powered
off anyway before Session B's separate flash:

```sh
flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=2 'hwclock -r'
```

Record the time, then remove main power (unplug USB-C / disconnect
battery — not just `reboot`), wait at least 60 seconds, restore power, and
once booted:

```sh
flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=3 'hwclock -r'
```

**Pass:** the second reading is consistent with (a little later than) the
first — the clock kept running across the power gap. **Fail signature:**
the post-power-off reading jumps back to the kernel's compiled-in epoch —
the RTC has a backing supply for warm reboot (its own SoC domain) but not
across a real power-off; record this distinction explicitly, it is a
different (weaker) result than the already-proven warm-reboot case.
Evidence: `docs/evidence/rtc/` (new file, e.g. `full-power-off.md`).

### A.6 Wi-Fi Settings (`the-handheld-configures-wifi-from-settings` 3.1, 3.2)

**Coordinate with the `fix/wifi-password-keyboard` agent first** — do not
run this until that rework has landed and 2.5's cross-build is current.

```sh
# real-glass: scan, select open/WPA2, masked keyboard entry, connect, Forget — operator-driven touch, camera-observed
flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=3 'systemctl status k230-wifi-settings k230-wifi'
```

then reboot after an accepted connection and:

```sh
flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=3 '<sanitized fixed status probe, no SSID/password/MAC in output>'
```

**Pass (3.2):** automatic reconnect after the first reboot; after Forget +
a second reboot, no reconnect, and the credential file/mode show
credential-free state (never print the SSID/password/address). Evidence:
`docs/evidence/wifi-settings/` (redacted UI/console captures only).

### A.7 Keyboard gestures (`the-keyboard-follows-touch-gestures` 3.2, 3.3)

```sh
python3 tools/capture-feature.py keyboard-gestures --duration 15 --provenance real-touch --description "Two-finger show, typing, handle dismissal and reversal"
```

Real-finger: two-contact show, type on Foot, slow hide/hold/reverse,
committed hide, then app navigation. **Pass:** the keyboard tracks the
gesture smoothly, text lands in the focused app, and reversal restores the
prior state without a stuck grip. Then measure keyboard-visibility/gesture
workload against the existing shell responsiveness budgets using the
installed compositor instrumentation (do not infer motion quality from a
static screenshot). Evidence: `docs/evidence/keyboard-gestures/` (extend the
existing `installed-preview/` line).

### A.8 VGLite trial (`the-shell-trials-vglite-composition` 3.2, 3.3) — opt-in package, no reflash

Run the already-built opt-in VG-Lite Sway package (`shell-compositor-vglite`)
alongside this same installed image, the same way
`docs/evidence/vglite-scene-board/*/README.md`'s prior trials did — stop
the normal `shell` service, run the opt-in binary as sole DRM owner, then
restore the normal service.

- **3.2:** repeated full-panel scene, GPU vs. forced-Pixman, wall/process
  CPU and available system/interrupt metrics, cited with limits.
- **3.3:** touch, keyboard, Apps, Back/Home, Terminal, Monitor and system
  controls under both GPU and forced-Pixman frames; confirm recovery to
  normal Pixman shell afterward with no second DRM owner stuck.

Evidence: extend `docs/evidence/vglite-scene-board/`. Then:

```sh
openspec validate the-shell-trials-vglite-composition --strict
./tools/blob-scan.py --no-vendor
```

closes 3.4's host half.

---

## Session B — C908/RVV candidate image (separate flash, must recover)

Do this as its own session, not combined with Session A — it is a different
kernel/rootfs (`sdImage-rvv-trial`), and group 3's own task order requires
recovering the known-good persistent image afterward before declaring
anything.

### B.0 Build and QEMU pre-check (host, before taking the board)

```sh
tools/qemu-k230.sh   # candidate image boots in emulation; retain the console transcript (QEMU proof only, task 3.1)
```

Not run by this audit (see `docs/closeout/system-hw-audit.md`'s c908 row) —
do this first, since it needs no board and catches a dead-on-arrival
candidate before spending board time on it.

### B.1 Flash the candidate, verify identities

```sh
flock -w 120 /tmp/k230-board.lock python3 tools/pixman-rvv-compare.py --board --manifest <matching-candidate-manifest> --package <matching-probe-path> --output docs/evidence/cpu-extensions/candidate-identity/pixel-<date>.json
```

**Pass (3.3):** vector context probe and the 192-case pixel check both pass
on the candidate.

### B.2 Card-shell workload on the candidate

```sh
flock -w 120 /tmp/k230-board.lock python3 tools/card-shell-rvv-benchmark.py --board --manifest <matching-candidate-manifest> --repeats 3 --revision <candidate-revision> --output docs/evidence/cpu-extensions/candidate-identity/benchmark-<date>.json
```

**Pass (3.4):** console, shell, Wi-Fi and representative one-/two-card
results unchanged against existing acceptance and budget scripts. This is
an injected-input workload, not a real-finger or optical proof — say so in
the evidence.

### B.3 Recover the known-good image — mandatory, same session

```sh
flock -w 120 /tmp/k230-board.lock python3 tools/check-root-growth.py --board --phase repeat --helper <existing-helper-store-path> --target-system <known-good-system-store-path> --before <prior-after-evidence.json> --output docs/evidence/cpu-extensions/candidate-identity/recovery-<date>.json
```

**Pass (3.5):** protected hashes and root layout intact, shell and Wi-Fi
work, on the restored known-good image.

### B.4 Only if B.1-B.3 all pass: select the candidate persistently

```sh
flock -w 120 /tmp/k230-board.lock python3 tools/console.py --wait=5 'readlink -f /run/current-system'
```

**Pass (3.6):** a fresh ordinary boot on the newly persistent candidate,
`/run/current-system` matching the proved candidate's store path. **Leave
3.6 unticked if any of B.1-B.3 failed** — do not select an unproven image
persistently.

---

## After both sessions

Run once, host-side, no board needed:

```sh
openspec validate --all --strict
python3 scripts/render_work_board.py > /dev/null
```

Then, for whichever changes now have every task checked with its evidence
file committed: `openspec archive <change-name>`, sync the delta specs,
commit, push `master`, and inspect the exact-revision Pages deployment
(`AGENTS.md`'s archive guidance). For `the-handheld-talks-bluetooth`
specifically: archive it and open
`the-handheld-pairs-over-a-usb-bluetooth-dongle` in its place **only**
after you've authorized that split (see `system-hw-audit.md`).
