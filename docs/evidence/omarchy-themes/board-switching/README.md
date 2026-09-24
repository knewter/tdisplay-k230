# Dark/light switching on the physical board

On 24 September 2026, the sole board operator ran the committed theme trial against installed source `df2c34b18e39fa2b1b5da6a024d830241d38235d`, system `/nix/store/lxi2zx8n8mp7z1dl1i3dz7hjlbhl7f6l-nixos-system-nixos-26.11.20260919.20b1ddd`. The fixed [result](result.json) records UTC times, pinned identities, both theme arms, app adapter acknowledgement and restoration.

- [Dark Catppuccin](dark.png)
- [Light Catppuccin Latte](light.png)

These are native `grim` screenshots from the real board, visually reviewed before committing. They show the installed GIO app grid, purple/blue folder icon variants, terminal colors and light wallpaper behind the deck. They are not camera footage or real-finger input evidence. The baseline, dark and restored PNGs have identical SHA256 `6d8dcad4ca99e9550f8d22bcb9a1648ce97151d72326428a81017f1b02ec382b`; only one copy is committed. The light capture differs as expected.

The helper at source `5f5fdd5c` follows the [operator procedure](../trial-operator.md). Its manifest pinned the installed system, source, default generation, two receiver sockets and actual immutable command paths. No private network or clone data is in the result. The command ran as the shell user inside the current Wayland session, using the packaged Python and theme modules:

```sh
XDG_RUNTIME_DIR=/run/shell \
PYTHONPATH=/nix/store/wz5m2pb3300zhand0z0r4nx519hzh2is-handheld-theme-command-0.1/libexec/handheld-theme \
/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3 \
  /run/shell/theme-trial-tools/handheld-theme-trial.py \
  --candidate-manifest /run/shell/theme-candidate.json \
  --output /run/shell/theme-evidence-02 \
  --raw-private-dir /run/shell/k230-theme-trial-02
```

`WAYLAND_DISPLAY` was set to the session's actual socket. The public workload identity is a fixed checklist, **not evidence that its real-finger steps were performed**. This execution exercises list, preview, activation, receiver acknowledgement, app appearance publication and restoration with the same static live-app/drawer scene. It does not measure CPU, frame latency, gesture budgets or reboot persistence. The helper waits 1.25 seconds before each static capture for the managed terminal's one-second color follower; that delay is not a latency pass.

Both theme arms report app appearance applied; restoration passed and its native screenshot is byte-identical to baseline. The original trial on the preceding installed image captured too soon after restoration, showing a still-light terminal; this was traced to the asynchronous follower and the bounded capture allowance was added before this repeat. Raw serial logs, unreviewed files and private recovery records remain outside Git.

The source retains `physical_observation: UNVERIFIED`: human glass acceptance, unchanged community clone trial, full theme-role coverage, reboot persistence and performance still require their own evidence. No theme proposal is archived by this checkpoint.
