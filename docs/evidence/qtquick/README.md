# Qt Quick evaluation: operator commands and evidence index

Change: `openspec/changes/the-handheld-evaluates-qtquick-and-quickshell`.
Everything here is opt-in; the default shell image is unchanged and neither
client is in any system closure.

## Evidence classes used

| Class | Meaning in this directory |
|---|---|
| host build/test | `nix build`, `tests/test_qtquick_probe_scene.py`, `tests/test_qtquick_trial_recovery.py`, `tools/qtquick-trial.py --self-test` |
| board, injected touch | taps and drags from the uinput device `qtq trial injected touch` (held-frame ranges, like `k230-touch-trackpad` output) |
| native capture | `grim -o DSI-1` on the board |
| real glass / camera | **not obtained.** The operator replaced glass taps with injected events plus `grim` captures (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`). That is a recorded waiver, never real-finger evidence. |

The common timing boundary of both clients is `client_commit`: the client's own
`wl_surface.commit` (baseline) or finished scene-graph frame (Qt `frameSwapped`).
It is a submission timestamp, not presentation and not optical input-to-photon.

## Locks and reservations

* Builds: `flock /tmp/k230-nix-build.lock nix build ...` (the Qt closure is built in chunks so the lock is released between them).
* Board: the host controller takes `flock /tmp/k230-board.lock` around each arm (about 2 minutes) and releases it between arms. Nothing reboots the board, changes the boot default, stops `shell`, or touches user settings.
* Transient board state lives only in `/var/tmp/qtq/<run id>/`; units are named `qtq-<run id>.service` and `qtq-guard-<run id>.{timer,service}`.

## Bounded lifetime and restoration (three independent layers)

1. The client exits by itself (`--exit-after-ms`).
2. systemd kills its cgroup at `RuntimeMaxSec` even if the controller or the SSH link is gone.
3. A transient `qtq-guard-<id>` timer runs `runner.py restore --id <id>` after the deadline plus 25 s, from on-disk state (`spec.json`, `pre.json`), even if the runner was SIGKILLed.

`restore` stops only this run's unit, kills only a surviving window with this run's `app_id`, refocuses the window that held focus before, and requires the same Sway PID, the same focused `app_id`, `shell` active and no `qtq-*` unit. Host simulation of the launch-failure, timeout, focus-capture, controller-loss and SIGTERM paths: `python3 tests/test_qtquick_trial_recovery.py`. That is host simulation, not physical restoration; the board runs record their own restoration results under `restoration/`.

Manual recovery, if ever needed (as root on the board):

```sh
PY=$(ls -d /nix/store/*python3-riscv64*/bin/python3 | head -1)
for id in $(ls /var/tmp/qtq | grep '^qtq-'); do $PY /var/tmp/qtq/runner.py restore --id $id --reason manual; done
```

## Commands

```sh
# 1. build (shared build lock; --max-jobs 1 --cores 4)
flock /tmp/k230-nix-build.lock nix build .#qtquick-software-probe --max-jobs 1 --cores 4 --no-link --print-out-paths
flock /tmp/k230-nix-build.lock nix build .#qtquick-shm-baseline   --max-jobs 1 --cores 4 --no-link --print-out-paths

# 2. host checks
python3 tests/test_qtquick_probe_scene.py
python3 tools/qtquick-trial.py --self-test
python3 tests/test_qtquick_trial_recovery.py

# 3. pin the manifest (reads the running system and compositor from the board, read-only)
python3 tools/qtquick-trial.py prepare --qt PROBE_OUT --baseline BASELINE_OUT --output docs/evidence/qtquick/qt/manifest.json

# 4. board stage (needs the system in the manifest to be the running one)
python3 tools/qtquick-trial.py board --manifest docs/evidence/qtquick/qt/manifest.json --stage qt --output docs/evidence/qtquick/qt

# 5. decide
python3 tools/qtquick-trial.py decide --stage qt --evidence docs/evidence/qtquick/qt
```

Measurement definitions (frozen in `manifest.json` before any run): three
alternating matched pairs per toolkit; 30 s idle then 30 s active (at least 24
scripted drags and taps); startup is the controller's launch time to the
client's first frame (a warm process restart, **not** a cold-after-boot claim);
client CPU is the unit cgroup's `usage_usec`, compositor CPU is the Sway
process's utime plus stime; incremental memory is the rise in
`MemTotal - MemAvailable` from before launch to the largest sample during the
active phase.
