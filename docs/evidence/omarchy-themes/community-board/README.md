# Unchanged community theme: board failure isolated

Observed 2026-09-24 UTC against source `dcfbdb0b`, installed system
`/nix/store/48x70j3df8ksiyab0sdgas5nzmgx69nz-nixos-system-nixos-26.11.20260919.20b1ddd`.
The sole operator reserved `/tmp/k230-board.lock` and the serial console.
This checkpoint records a failed community activation and successful recovery;
it does not accept community support or physical touch behavior.

The unchanged public [Fuchsblau source](https://github.com/fuchsblau/omarchy-fuchsblau-theme/tree/aa7fde043ae60603c3ecc6fd6ac3b6674cacab04)
was staged as an ordinary checkout, with its Git metadata, beneath the shell
user's Omarchy theme directory. Host Git HEAD was exactly `aa7fde043ae60603c3ecc6fd6ac3b6674cacab04`
and `git status --porcelain` was empty. `theme_sources.source_digest` was
`f72ece7c9eead4fb049ebead18d918b4b11be6f35dcc861b8862e5c8f0693e75`
before transfer and again on the board after all trials. Source content was
not edited. See the [source/license inventory](../source-fixtures.md).
No community artwork is redistributed in this checkpoint.

The [trial procedure](../trial-operator.md) used a private candidate manifest
pinning the installed system, default generation and immutable command paths,
plus dark, light and community roles. Invocation as shell user:

```sh
XDG_RUNTIME_DIR=/run/shell \
PYTHONPATH=/nix/store/wz5m2pb3300zhand0z0r4nx519hzh2is-handheld-theme-command-0.1/libexec/handheld-theme \
/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3 \
  /run/shell/theme-trial-tools/handheld-theme-trial.py \
  --candidate-manifest /run/shell/theme-candidate.json \
  --output /run/shell/theme-community-evidence-03 \
  --raw-private-dir /run/shell/k230-theme-community-03
```

`WAYLAND_DISPLAY` was the active session socket. Attempts 1 and 2 used the
same command with corresponding `01`/`02` output suffixes. Both failed at
community discovery because this operator's staging command created root-owned
0700 parent directories. The first correction missed the `.config` ancestor;
after all created parent directories belonged to shell, readable source and
catalog discovery were independently confirmed. These are staging failures,
not claims about the product importer. Both attempts restored the baseline.

[Attempt 3](attempt-3.json) then prepared the community preview successfully,
but live activation failed. [Attempt 4](attempt-4.json) repeated it using a
private copy of the helper that additionally wrote command stderr and exception
class to a private log. This diagnostic changed no activation/restoration logic.
Its bounded error was `fanout prepare failed; both receivers restored`.
Both attempts restored the starting generation and byte-identical native pixels.

A separate operator-observed prepare-only diagnostic isolated the same generated community
appearance: Rust rejected its prepare acknowledgement; the deck accepted it.
The [fixed diagnostic outcome](endpoint-diagnostic.json) is a transcription
of the private log, distinct from the trial helper’s machine-produced results.
No commit was sent. The initial diagnostic rollback named the immutable default
explicitly; the deck rejected that path. Repeating rollback with the actual
prior pointer (`None`) acknowledged on both endpoints and cleared staged state.
This diagnostic error is retained rather than counted as successful recovery.
The agent's host reproduction identified a valid upstream `rgba(...)` border
palette value rejected by the Rust parser. Its correction is separate source
work and was not installed for these attempts.

| Current installed scene | Reviewed native board capture |
| --- | --- |
| Dark drawer, actual desktop-entry icons and live terminal | [Dark](dark.png) |
| Light drawer, icon variant and wallpaper | [Light](light.png) |

These unedited 568×1232 PNGs came from attempt 3's pinned `grim` capture
command, using the trial helper's 1.25-second app-color settling allowance.
They were transferred over the reserved console with base64 and visually
reviewed. They are compositor pixels from the real board, not camera footage
or finger input. The fixed JSON retains `native-unreviewed` from collection;
this human visual review is separate. Baseline/dark/restored hash identically.

After diagnostics, the drawer was hidden, `swaymsg card_shell back` restored
the terminal, and wvkbd was shown with USR2. Shell, Rust UI and keyboard services
were active. The board was released. No reboot, persistent boot selection,
performance workload or physical acceptance was performed. Full theme-role
coverage, real chooser gestures, videos and boot persistence remain open.

Diagnostic calls used the installed `theme_transaction` module under the same
packaged Python/PYTHONPATH above. `generation` came from the community preview’s
`appearance_path.parent`; `previous` was the manifest’s immutable default
because `_pointer(state_root)` returned `None`:

```python
exchange(Path(manifest['rust_socket']), 'prepare', generation)
exchange(Path(manifest['deck_socket']), 'prepare', generation)
# In finally, each endpoint was attempted separately:
exchange(endpoint, 'rollback', previous)
# Explicit corrective call after the deck rejected the default store path:
exchange(Path('/run/shell/k230-shell-rust-appearance.sock'), 'rollback', None)
exchange(Path('/run/shell/k230-card-appearance.sock'), 'rollback', None)
```

The trial’s capture executable was
`/nix/store/hjllbawb3xs65bmcnyy66yf6g9hdaxk8-grim-riscv64-unknown-linux-gnu-1.5.0/bin/grim`,
with the single output argument `/run/shell/k230-theme-community-03/dark.png`
or `light.png`, in the shell user’s active Wayland session.
