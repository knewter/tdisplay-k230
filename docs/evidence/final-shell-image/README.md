# Final installed video and launcher regression

The coordinator built and flashed source `f76754c` on 2026-09-23. Later
opt-in experiment packages do not change this normal system: evaluation after
their integration still resolved the same system path.

- Image: `/nix/store/a63jc34vd9ahi51lf45z4qr7cch4542v-k230-sd-image.img`
- Image SHA256: `4bacda66b71837cfe8bedc58c7012fb84a66a537ab0e7b7404418e67effc60c0`
- System: `/nix/store/nz82q373yj1hp2k4qm85xa3c328jli8j-nixos-system-nixos-26.11.20260919.20b1ddd`
- Boot ID: `9407bae0-fe1a-4a05-8062-edbe8a110859`

`nix build --no-link --print-out-paths .#toplevel .#sdImage --max-jobs 1
--cores 8` succeeded. `tools/ums-session.py --flash IMAGE --expected-sectors
249872384 --out PRIVATE_LOG` held the board lock throughout the flash. Its
write returned zero: 2,308,960,256 bytes in 181.3 seconds including sync. The
Linux login prompt appeared and the console reported the system path above.
Full-image readback was skipped by the established policy. Only the protected
Wi-Fi file was restored, with matching bytes and root:root mode 0600; no home
directory was restored. Raw flash/network transcripts remain private.

## Executed checks

[Result](result.json) records an **injected-touch physical-board** regression.
This is not a real-finger test, optical timing or performance benchmark. The
Python native-frame assertions deliberately impose load; their elapsed time
must not be read as UI latency. The [installed status](installed-status.txt)
identifies the actual installed wrappers, services and touch device.

The check covers Apps Next/Previous, Help/Back, Terminal and Monitor focus,
keyboard show/hide with the expected 400-pixel reservation, overview up/down
and Back, System reboot-confirmation cancellation without reboot, and Apps
recovery after forced allocation failure. For the latter, `prlimit --as=1`
constrained only the identified launcher process; Next made it exit. A new
Apps invocation rendered, its Next/Previous changed and restored the canvas,
and Back closed it. [Recovery frame](after-render-failure.png),
[shown keyboard](keyboard-visible.png), and [Help](help-header.png) are native
`grim` captures of this installed image. They are not camera images.

Each of three Video trials was launched through Apps. The checker required
the actual software video surface and media time beyond one second, then
injected Windows followed by Stop, Back or Home. It waited for the state file
and tracked controller/player processes to disappear, checked that no session
socket or video surface remained, and checked Home focused Terminal. A final
Apps/Back interaction and active shell/seatd/Wi-Fi services passed. The public
BBB 480x270 software profile and disabled audio were the image defaults.
Earlier committed comparison, error, EOF and fallback evidence remains linked
from `docs/evidence/network-video/`; this run adds final-image integration and
cleanup, not new sustained-presentation or audio claims.

## Procedure and rejected checker runs

The source is [check.py](check.py). Transfer it to `/run`, copy
`docs/evidence/launcher-gestures/metadata-budget/check.py` as
`/run/rollback_check.py`, and provide the repository's `/run/inject-tap.sh` plus
a reserved evemu touchscreen at `/dev/input/event1`. The image's Python is
`/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3`.
Run the checker from the normal home bar with its keyboard hidden. The script
sets the normal Wayland/Sway environment and records no window titles.

The first run used a fixed 400ms pause between bar actions and missed Apps
after System cancel. It was rejected; [its result](rejected-v1.json) remains.
The next run waited for the rendered bar state and passed all shell controls
and allocation recovery. It then rejected an immediate process-existence
assertion after Stop: the controller had removed its state before fully exiting.
[That result](rejected-v2.json) is also retained. The corrected checker waits
up to 12 seconds for actual process exit. It resumed the three video cases
with `--video-only` on the **same verified boot ID**, retaining the prior
successful control checks. [The two logs](shell-check.log) and
[video continuation log](video-check.log) preserve which checks ran in each
phase. No failed assertion was changed into a success without rerunning its
corresponding interaction.

The forced allocation test complements the separately committed
[gesture-disabled rollback](../launcher-gestures/rollback/README.md). These
checks close the integrated-image and failure-recovery gates. The existing
real-finger gesture clip remains insufficiently sharp for its separate final
camera task; that proposal stays open.
