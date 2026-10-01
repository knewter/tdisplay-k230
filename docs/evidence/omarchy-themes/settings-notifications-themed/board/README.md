# Settings and Notifications: physical theme and rollback proof

On 2026-10-01 at 20:33:41 UTC, the physical handheld presented dark Catppuccin,
light Catppuccin Latte, then the restored dark generation through the actual
Rust Settings and notification Shade surfaces. All six native `grim` captures
were reviewed. Their hashes, resolved sections, compatibility reports and
transaction acknowledgments are recorded in [result.json](result.json).

| Surface | Dark | Light | Forced rollback to dark |
| --- | --- | --- | --- |
| Settings | [capture](dark-settings.png) | [capture](light-settings.png) | [capture](rollback-settings.png) |
| Notifications | [capture](dark-shade.png) | [capture](light-shade.png) | [capture](rollback-shade.png) |

Source: `288535289172c8465c4fa408eaa8ba2c7ab8a5ac`.
Tested Rust executable:
`/nix/store/zjlcmhxqkhchysmjj9sk53hks1h5wc3l-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust`.
Tested theme helper:
`/nix/store/l6qm7fykcf6bmlhp3wcj7va4v2k4v2fg-handheld-theme-command-0.1`.
The helper's fourteen Python modules were byte-compared with the final full
closure's helper and all match; its packaged default/wallpaper store references
can differ. The trial used the exact tested pair named above.

## Commands and recovery

[trial.py](trial.py) preserves the running wrapper's environment, changes only
its Rust executable and theme helper through two owned runtime unit drop-ins,
and arms an independent 480-second root restoration timer before restarting
those services. The candidate paths are imported into the store first. On the
reserved serial console the invocation was:

```sh
/run/current-system/sw/bin/env PATH=/run/current-system/sw/bin:/run/current-system/sw/sbin \
  /nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3 \
  /root/tmp/k230-settings-themed/trial.py "$PROTECTED_TRANSFER_URL" 77f76b2f
```

`PROTECTED_TRANSFER_URL` is supplied at runtime through the protected transfer
configuration; its value and transport logs are excluded from this repository.
The script contains the exact preparation, presentation, capture and rollback
commands. It prepares both built-in generations with `omarchy-theme-set
<name> --prepare-only`, activates through the real Rust/deck receiver transaction,
opens `k230-shell-rust --surface settings` or `--surface shade`, waits for the
service snapshot, then captures with `grim`.

An isolated instance of the actual notification daemon carries only the known
fixture text. The shell user's emission is correctly labeled Unknown source;
operator notification history is untouched. The trial then deliberately fails
the second receiver's commit after Rust has changed appearance. Both receivers
acknowledge rollback, and the active pointer returns to the dark generation.
Settings panel, control/notification and Home dock pixel samples return to their
original dark values. The Settings rollback capture is byte-identical to its
dark capture. Shade retains the notification text emitted under the light theme,
while its colors and the dock return to dark.

Normal shell, UI and theme-helper services were restored and active; the
original theme pointer and executable were restored. System profile, current
system and boot files remained unchanged. The coordinator's later transport
interruption happened after restoration; the already completed board artifacts
were retrieved by their recorded hashes without rerunning the trial.

## Build proof and limits

The affected Rust and card-shell outputs and the full coherent system built
successfully from the same source revision. Full-build invocation, where
`REPO` denotes the checkout:

```sh
nix build "git+file://$REPO?rev=288535289172c8465c4fa408eaa8ba2c7ab8a5ac#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel" \
  --no-link --print-out-paths --max-jobs 1 --cores 6
```

Full system: `/nix/store/ija989s4f2la7ms4zbr9dnirpnnp8qyg-nixos-system-nixos-26.11.20260919.20b1ddd`.
Derivation: `/nix/store/1amf1x8fn715v2qx6gb2wrnkann7accv-nixos-system-nixos-26.11.20260919.20b1ddd.drv`.
Its closure contains the tested Rust output and helper
`/nix/store/wcv2wmxgpm53dcw0awd5pf125i6mgf3k-handheld-theme-command-0.1`.
Card shell: `/nix/store/gp9gv2nh0zf4bgryk8qp4dbprnfycya2-k230-card-shell`.

This is native presentation and transaction rollback on the physical board,
not injected-touch, real-finger, boot or persistent full-system activation proof.
The trial restored the working system. It does not close the larger theme-picker,
reboot, motion or polished-shell scopes. Unsupported roles remain explicitly
unavailable. The existing volume-row text/slider overlap remains part of the
open shell polish scope; these captures establish theme behavior.
