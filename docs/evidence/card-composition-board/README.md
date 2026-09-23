# Live card capability probe on the K230

Recorded 2026-09-23. Evidence class: **IPC-injected interactions on the physical
board, native captures, actual Wayland clients and virtual keyboard events**.
No real-finger, optical cadence, product card UX or GPU acceptance is claimed.
The root coordinator held `/tmp/k230-board.lock` for every serial operation;
no subagent accessed the board.

## Artifact and ownership

- Probe source/package revision: `310dbf131e81bcb5f455299a61baf4ad19a1ea53`.
- Probe: `/nix/store/wjzw7jw21p8qq4dsbc8b3fky9233pgqq-k230-card-composition-probe`.
- Unwrapped Sway: `/nix/store/bkzw3m5c9j53583ki80zf5d5nbkrqv9v-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`.
- Final harness revision: `260197de09edfed54cc451a46ac815cad229b00c`.
- Installed normal system: `/nix/store/nz82q373yj1hp2k4qm85xa3c328jli8j-nixos-system-nixos-26.11.20260919.20b1ddd`.
- Boot ID: `9407bae0-fe1a-4a05-8062-edbe8a110859` throughout these sessions.

The opt-in package was imported into the existing Nix store. No image was
flashed and no normal-service default changed. The harness stopped normal
`shell`, started one transient Sway session as user `shell`, and restored the
normal service. The checker observed normal `shell` inactive and exactly one
Sway process during the probe. Seatd remained the device broker.

## Procedure and observed result

On the reserved board, copy the committed harness to `/run/card-session.sh`,
this directory's `check.py` to `/run/card-board-check.py`, and
`tests/card_virtual_keyboard.py` to `/run/card_virtual_keyboard.py`. Use the
installed Python executable (recorded below) to run the checker while the
bounded harness is active:

```sh
K230_CARD_DURATION=90 bash /run/card-session.sh \
  --probe /nix/store/wjzw7jw21p8qq4dsbc8b3fky9233pgqq-k230-card-composition-probe/bin/card-composition-probe \
  --restore-shell
# In the same reserved operator session, while the harness runs:
/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3 /run/card-board-check.py
# Collection is read-only and also works after restoration:
K230_CARD_JQ=/nix/store/fy9xmga7mbqqiqp6gaj79239a98ssy9g-jq-riscv64-unknown-linux-gnu-1.8.2-bin/bin/jq \
  bash /run/card-session.sh --collect
bash /run/card-session.sh --verify-restored
```

`result.json` and `check.log` record ten passing checks: sole compositor,
partial-allocation fallback, both animated parent and desynchronized child
surfaces updating while shrunk, second-contact cancellation, stream cancellation,
continuous motion, adjacent selection/expansion with keyboard focus, refused
close recovery, accepted close/exit with focus fallback, and presentation signals.
Expansion means restoration of the original floating app window, not a promise
of fullscreen product animation. The coordinator inspected all six retained
PNG captures; the fixture content and restored shell match the claimed states.

The final run began at 07:22:21 UTC. After the checker completed, the coordinator
sent SIGTERM to the specifically recorded harness PID 6227. Its cleanup stopped
the complete probe cgroup and restored normal `shell`; `telemetry.txt` records
`normal_services_active` and `shell_restored`. An earlier successful 60-second
run also restored automatically at its deadline; its result and telemetry are
retained as `card-board-first-pass*`.

After each successful restoration, the separate injected uinput checker tested
normal Apps Next/Previous/Back, keyboard toggle/reservation and Terminal focus.
`restore/result.json` records PASS for the final interruption case, and
`card-board-first-restore.json` records PASS after the deadline case. Both match
the original system and boot ID. To repeat the restoration checker, also install
`docs/evidence/launcher-gestures/metadata-budget/check.py` as
`/run/rollback_check.py` and provide the existing injected touch device and
`tools/inject-tap.sh` at `/run/inject-tap.sh`. This checks keyboard visibility and
focus; it does not repeat or replace the user's earlier physical typing proof.

## Rendering, lifetime and cost observations

The observed output is DSI-1 at 568×1232 with logical scale 1. The committed
`scanout-format.txt` was read from DRM debug state while the probe was active:
`RG16 little-endian (0x36314752)`, RGB565. Sway's selector is `render_bit_depth 6`.
The mode's 52190 mHz value is advertised mode data, not measured frame cadence.

The source verifies Pixman at entry, and the emitted attachment records name
`renderer=pixman`. Client buffers are SHM XRGB8888 (`34325258`), with 520×1040
stride 2080 or 480×720 stride 1920 parent buffers, and 128×96 stride 512 child
buffers. Mirror buffers remain owned by wlroots scene surfaces. The log records
references, mirror releases, commits, sampling, frame-done and output-presented
separately. The final close/exit restoration recorded 386 commits, 568 samples,
568 frame-done signals and 142 output-presented signals. These counters are not
interchangeable and do not measure optical latency or prove zero-copy.

The final mixed interaction/recovery run collected 22 session samples and 22
Sway process samples over 32.08 seconds. Session CPU increased by
19,030,008,000 ns; sampled session memory peaked at 19,550,208 bytes. Sway process
CPU increased by 10 integer seconds and RSS peaked at 29,593,600 bytes. Process
CPU uses procps `cputimes` and therefore has one-second quantization. Session
memory accounting and process RSS count shared memory differently. The run
includes allocation failure, captures and changing app count, so these are
resource observations, not a steady-state benchmark or product performance
acceptance. The product's one/multiple-card benchmark remains required.

## Rejected attempts and remaining limits

The retained rejected JSON files document failures rather than being replaced
with the passing result:

- Missing D-Bus daemon and then shell utilities prevented standalone startup;
  the Nix wrapper now declares D-Bus, bash and coreutils paths.
- Sway's default error-only logging hid required info-level lifecycle records;
  the harness now requests `--verbose`.
- Automatic output scale 2 made the original 568×1232 test coordinates miss the
  second card. That run failed, despite a weak intermediate focus-only check.
  The harness now sets scale 1 and the checker requires the actual
  `selected-expanded card=1` event before accepting expansion.
- An intermediate externally stopped service required explicit
  `--restore-shell` after cleanup reported `restore_failed`; its cause was not
  established. The final harness-owned deadline and SIGTERM paths both restored
  automatically and passed separate control checks. Do not treat arbitrary
  external service manipulation as verified interruption coverage.
- `jq` exists in the image's Nix closure but not its interactive PATH. Collection
  now accepts the explicit `K230_CARD_JQ` path above.

Continuous real-finger tracking, physical OSK use inside the probe and optical
presentation remain UNVERIFIED. Native screenshots and virtual keyboard events
cannot prove them. The capability evidence permits continued product adapter
work; the horizontal product deck, privacy policy, persistent controls, measured
cost and refined webOS-style feel retain their own acceptance gates.
