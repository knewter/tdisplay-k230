# Reserved-board theme trial procedure (source checkpoint)

This procedure is for the sole board/serial operator after an integrated image
has been built and installed. The initial helper completed a reserved-board dark/light activation and metadata restoration on 24 September 2026. Its immediate restored capture preceded the managed Foot follower's next one-second poll; the helper now waits 1.25 seconds before each static capture. This is a capture settling allowance, not latency proof. Reviewed board records are linked as they are committed.
`python3 tests/test_handheld_theme_trial.py` exercises its failure recovery
against host fakes. It neither proves physical touch nor runs a performance
workload. OpenSpec theme tasks 5.3–5.5 remain open.

Stage `tools/handheld-theme-trial.py`, `tools/theme_transaction.py`,
`tools/theme_preferences.py`, `tools/app_appearance.py`, and
`docs/evidence/omarchy-themes/trial-workload-v1.json` together in a private
board directory. Run as the `shell` user inside the active Wayland
session with its `XDG_RUNTIME_DIR` and `WAYLAND_DISPLAY`. The operator retains
the board reservation and normal system rollback mechanism throughout.

Create a private candidate manifest from the **installed** image, not a
worktree guess. Its exact fields are:

```json
{
  "schema": 1,
  "source_revision": "40 lowercase Git hex digits for the installed source",
  "system": "/nix/store/EXACT-nixos-system-nixos-...",
  "theme_command": "/nix/store/EXACT-handheld-theme-command/bin/k230-theme",
  "capture_command": "/nix/store/EXACT-grim/bin/grim",
  "default_generation": "/nix/store/EXACT-handheld-theme-default/generations/0d16475245f13b3d7d3f036f",
  "state_root": "/home/shell/.local/state/omarchy/current",
  "rust_socket": "/run/shell/k230-shell-rust-appearance.sock",
  "deck_socket": "/run/shell/k230-card-appearance.sock",
  "workload": {
    "id": "cards-shade-static-v1",
    "sha256": "b9b330e66cbbd694839e8096d9ff626d66e3b7c737376b6d107e2a218947f195",
    "artifact": "/run/shell/theme-trial-tools/trial-workload-v1.json"
  },
  "themes": {"dark": "catppuccin", "light": "catppuccin-latte"}
}
```

Replace every `EXACT` value with the realized store path. `system` must equal
`readlink -f /run/current-system`. Include an optional `community` theme name
only after an unchanged clone is staged; that name stays in the private
candidate, while the public result records only the role and opaque IDs.
Stage `trial-workload-v1.json` beside the private trial tools and verify its
listed SHA-256. The helper checks the artifact bytes before touching theme
state, then repeats one public ID/hash for baseline and all themed arms. It does not fabricate CPU,
RSS, latency, or budget results. The manifest may contain a private clone
name, so keep it outside the public evidence tree.

With a fresh public output directory and a fresh private raw directory under
the shell user's `XDG_RUNTIME_DIR`, run:

```sh
python3 tools/handheld-theme-trial.py \
  --candidate-manifest /run/shell/theme-candidate.json \
  --output /run/shell/theme-evidence-UNIQUE \
  --raw-private-dir "$XDG_RUNTIME_DIR/k230-theme-trial-UNIQUE"
```

The helper refuses a non-RISC-V host, the wrong installed system, an existing
output directory, unpinned commands, or a raw directory outside the private
runtime. It calls the installed `k230-theme` list/preview/activate JSON
interface and records only schema, role, public generation/theme/background
IDs, arm identity, bounded status, timestamp, and native capture hashes in
`result.json`. It never copies command stdout/stderr, user clone paths, SSIDs,
notifications, or screenshot pixels into the public directory. Original PNGs
and `recovery.json` remain mode-0600 under the private raw directory. Review
images there before selecting any non-sensitive capture for publication.

`finally` restores the preceding active generation, wallpaper preference
bytes and app appearance pointer. If no active generation existed, both
receivers are asked to restore their pinned default and the active pointer is
removed. A failed acknowledgement leaves `restoration: "FAILED"` in the
fixed result; do not claim recovery. If the process is interrupted before
`finally`, use the private recovery record while the same image and session
are still active:

```sh
python3 tools/handheld-theme-trial.py \
  --candidate-manifest /run/shell/theme-candidate.json \
  --restore-private-dir "$XDG_RUNTIME_DIR/k230-theme-trial-UNIQUE"
```

After restoration, compare the reported restored generation with the saved
baseline and confirm the normal shell/launcher still respond. Keep raw
transport and unreviewed PNGs outside Git. The result's
`physical_observation: "UNVERIFIED"` intentionally requires a separate
operator note, panel capture review, and real-finger/video evidence before
task 5.3 can be checked. A killed process has no independent watchdog in this
checkpoint, so the operator must run the explicit recovery command.

Host command on source:

```sh
python3 tests/test_handheld_theme_trial.py
# 5 tests passed: prior/default restoration, failed rollback visibility,
# manifest and changed workload identity rejection.
```
