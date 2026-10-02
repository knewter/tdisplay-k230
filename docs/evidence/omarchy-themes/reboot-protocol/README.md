# Reboot protocol: host proof and remaining board gate

2026-10-02. Base `c5254075e531487af82841b3ae76582e5535f0fb`; source and
narrow tests are committed with this record. [host-check.txt](host-check.txt)
records timestamps, exact commands and results: `python3
tests/test_handheld_theme_trial.py` (22 passed), `openspec validate
the-shell-loads-omarchy-themes --strict` (passed), and `git diff --check`
(passed). These are host Python protocol tests with injected command, capture,
boot-ID and ACK inputs. Pointer publication, preference parsing/publication,
state directory moves, report fingerprint validation and restoration execute
the real implementation. No board, serial, cross-build, installed system,
physical reboot, QEMU, panel or full fresh-home evidence was obtained.

`--workload reboot` now has `--reboot-phase begin` and `resume`. Each invocation
finishes without rebooting. The sole operator owns the board and console across
all steps and performs the actual reboot. Begin and every resume verify the
installed system against the pinned candidate; resume requires a new Linux boot
ID and the identical manifest and workload bytes. Public results contain only
fixed status, timestamps, store/source/workload identities, opaque theme/media
IDs and capture hashes. Private source names, preferences, raw output and native
capture pixels stay outside public evidence.

The protocol backs up the **entire normal theme-state directory** by a durable
same-filesystem rename into a persistent mode-0700 directory before installing
isolated trial state at its normal path. This preserves additional consumers'
private state, including keyboard state. It only hides its own staged source
fixture; it does not rename a production clone. The installed helper daemon
ignores per-call catalog roots, so trial calls force the installed CLI fallback
with an absent private helper socket, honoring the trial `--user-themes` root.

All successful public gates are labeled `state-check-passed` with
`evidence_class: filesystem-and-cli-state-only`. A report fingerprint describes
the desired staged asset, not decoded output or photons. Capture hashes are
unreviewed native evidence until the operator checks the pixels and panel.

Startup source was read: `nix/shell.nix` exports the same `themeDefault`/
`themeDefaultId` to Rust (`K230_THEME_DEFAULT_GENERATION`) and card-shell
(`SWAY_K230_CARD_THEME_DEFAULT`) alongside the normal state-root paths.
`AppearanceReceiver::bind_with_roots` in
`nix/rust-shell-client/src/appearance.rs` uses
`selected_snapshot(...).or(default_snapshot)`;
`card_appearance_start` in `nix/card-shell/appearance.c` initially assigns the
fallback and replaces it only if the active pointer loads successfully. The
`theme-helper` service in `nix/shell.nix` only serves the catalog CLI with the
normal root; it does not certify the rendered default at boot. These source
observations motivate the no-pointer check and remain distinct from runtime
proof. The candidate manifest must match those installed default identities.

The three boot arms are:

1. Remembered theme/wallpaper: require unchanged generation, selected-background
   fingerprint and preference bytes; a preview without `--background` must pick
   the remembered opaque background ID.
2. Empty theme state: preserve the trial's selected state separately, reboot
   with no theme pointer/preferences/app appearance and capture the result.
   The state check expects the packaged default; it does not prove it rendered. This empties the theme subtree only.
   `fresh_home: UNVERIFIED` is retained: a full fresh HOME with a usable chooser
   and recovery route remains a separate physical requirement.
3. Unavailable source: restore selected trial state, hide only the private
   source fixture, then reboot. The gate requires default recovery, captures
   the observed appearance, and fails if the cached user generation persists.

There is an existing requirement/design conflict: the spec's “Boot with no
saved preferences” scenario requires the declared default when a user source
is unavailable, while design decision 1 retains the last working generation
independently of a removed clone. `theme_catalog.selected()` currently reports
`id: null` with the retained generation in this case; the receivers load that
cached generation. The protocol reports `failed-default-required` and restores
normal state. It does not change consumer policy or accept this as default
success. The coordinator must reconcile that conflict before task 5.5 can pass.

On completion or a protocol gate error, the complete normal state directory and
source fixture return to their original locations, and both receivers use the
existing acknowledged restoration protocol. Failed ACKs are public
`restoration: FAILED`; private recovery permits an explicit retry. Interrupted
steps retain the durable original directory and recovery record. After any
interruption, use recovery rather than assuming the last checkpoint describes
all intervening filesystem moves. Directory backups are single-use, retained
privately, and never overwritten. No process watchdog runs while the board is
off. Normal-session restoration on glass, including supervised consumers after
startup, still requires the final operator reboot/observation.

The tests exercise same-boot and candidate/workload refusal before mutation,
wallpaper/report/preference mismatch, incomplete catalog responses, actual
state preservation, interruption recovery at each prepared stage, missing-source
failure, and a failed restoration ACK followed by manual retry. One test models
the required missing-source default policy solely to exercise the successful
protocol branch; it is not evidence that the installed loader implements it.
No generated host result is offered as a physical result.

## Reserved-operator commands (not run here)

Use the existing [manifest/preflight procedure](../trial-operator.md), with the
same installed system, pinned theme/capture commands, default generation, normal
state root and both ACK sockets. Keep the manifest private and add:

```json
"reboot_trial": {
  "theme_name": "trial-fixture",
  "background_id": "24 lowercase hex digits from the installed preview"
}
```

Stage an attributed, exact-revision unchanged community fixture at
`/home/shell/.local/state/k230-reboot-trial-UNIQUE/sources/trial-fixture`.
This directory belongs only to this trial. Keep its license/revision/hash in the
operator's reviewed source record. Stage the candidate, pinned workload artifact,
trial script and its imported modules in this **persistent** private directory.
The necessary modules are `theme_preferences.py`, `theme_transaction.py`,
`runtime_trace.py`, `theme_timing.py`, `theme_background_metrics.py`,
`theme_background_status.py`, `app_appearance.py` and `theme_gtk.py`.
Resolve the fixture's theme/background IDs via the same pinned `theme_command`,
using `--user-themes` for the private fixture root and the absent
`--helper-socket` override. No `.git` metadata or private capture directory is
exported. Use a separate persistent output directory. The private directory
must be canonical, owned by the shell user, mode 0700, outside `/run`, `/tmp`,
`/var/tmp` and store/device pseudo-filesystems, outside normal theme state, and
on the same filesystem as the theme-state parent.

Replace `UNIQUE` and every candidate store identity with concrete paths in the
committed operator record. Run as `shell` inside its actual Wayland session;
retain exclusive theme activation and the board/serial reservation across all
reboots. No concurrent activation, chooser Apply, normal-helper request or
refresh may run during preparation, directory moves or restoration. Keep the
normal helper quiescent while the script prepares each arm; it retains the
normal root and could otherwise write trial state while directories move. These are operator commands, not a host invocation or a board result:

```sh
python3 /home/shell/.local/state/k230-reboot-trial-UNIQUE/tools/handheld-theme-trial.py \
  --candidate-manifest /home/shell/.local/state/k230-reboot-trial-UNIQUE/candidate.json \
  --workload reboot --reboot-phase begin \
  --reboot-private-dir /home/shell/.local/state/k230-reboot-trial-UNIQUE \
  --output /home/shell/.local/state/k230-reboot-evidence-UNIQUE
```

After each `awaiting-operator-reboot` result, the sole console operator runs:

```sh
flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=3 'systemctl reboot'
```

Once the unchanged system and shell session return, record the boot console
identity and actual panel appearance **before** resuming, since resume prepares
the next arm. Then run in the shell user's active session:

```sh
python3 /home/shell/.local/state/k230-reboot-trial-UNIQUE/tools/handheld-theme-trial.py \
  --candidate-manifest /home/shell/.local/state/k230-reboot-trial-UNIQUE/candidate.json \
  --workload reboot --reboot-phase resume \
  --reboot-private-dir /home/shell/.local/state/k230-reboot-trial-UNIQUE \
  --output /home/shell/.local/state/k230-reboot-evidence-UNIQUE
```

Repeat this reboot/observation/resume sequence for the three arms. A gate
failure restores normal state and exits nonzero; stop and retain the fixed
failure result and reviewed log. For an interruption or failed restoration,
run under the same installed candidate and active shell session:

```sh
python3 /home/shell/.local/state/k230-reboot-trial-UNIQUE/tools/handheld-theme-trial.py \
  --candidate-manifest /home/shell/.local/state/k230-reboot-trial-UNIQUE/candidate.json \
  --workload reboot \
  --restore-private-dir /home/shell/.local/state/k230-reboot-trial-UNIQUE
```

The fixed failure result remains a failure even after manual recovery; record
the separate retry observation. Reboot once more after restoration and record
the normal shell/theme/wallpaper and supervised consumers on the panel. Review
private captures before publishing selected nonsensitive images. Commit a
phase-by-phase console/panel record with actual boot IDs, installed store path,
source/workload identities, observation timestamps, chooser/recovery checks,
reviewed photograph/native-capture paths and normal-session restoration.
Separately obtain a true fresh-home physical boot with the pinned default;
the protocol's theme-state reset cannot substitute for it. Task 5.5 stays
unchecked, and this change stays open.
