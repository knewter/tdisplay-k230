# Refined launcher and motion: installed board checkpoint

Source `df2c34b18e39fa2b1b5da6a024d830241d38235d` was cross-built and test-activated on the reserved physical board on 24 September 2026. [Installed identity](installed.json) records the exact system, previous preview, transfer size and observed services.

```sh
nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel --max-jobs 1 --cores 4 --no-link --print-out-paths
python3 tools/console.py /dev/ttyACM0 --wait=3 'readlink -f /run/current-system; systemctl is-active shell shell-ui shell-session-bus shell-notifications k230-wifi k230-wifi-settings'
```

PASS: `/nix/store/lxi2zx8n8mp7z1dl1i3dz7hjlbhl7f6l-nixos-system-nixos-26.11.20260919.20b1ddd`; all six named services active. The 31-path, 10,757,752-byte closure delta imported with exit 0. Activation returned 0. A five-minute root systemd fallback to the preceding installed preview was armed before activation and stopped only after this health check.

The installed Rust executable is `/nix/store/1xh02gcry343haprfrg3513r5mf18sch-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust`; Sway is `/nix/store/lmgq4hj6fxc37vp98hy1x93wnz589iyn-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`.

- [Terminal fills the panel](terminal.png): native 568×1232 capture; the coherent Foot wrapper includes `--override resize-by-cells=no`.
- [Installed launcher grid](drawer.png): Editor, Files, Monitor, Terminal and Video come from actual GIO desktop discovery, with real icons. Upstream Foot client/server IDs remain installed but use normal `NoDisplay` overrides. The grid removes the previous repeated “Installed app” labels and underlay text bleed.

Capture procedure: as `shell`, use the active `XDG_RUNTIME_DIR=/run/shell`, Wayland socket and Sway IPC socket; run `swaymsg card_shell enter`, the exact installed Rust executable with `--surface drawer`, then `grim`. Images were visually reviewed before publication; only public packaged app names and a clean terminal prompt appear. Raw serial output remains private.

The new direct horizontal carousel and velocity-seeded vertical release are in this image. Their [native QEMU motion evidence](../direct-carousel-qemu/README.md) is separate from these static board captures. **Finger feel, momentum and physical touch acceptance remain pending on this installed revision.** The oversized deck diagnostics remain visible and have a separate refinement in progress. Keyboard gestures and the Wi-Fi Settings UI are not in this image; the root Wi-Fi broker alone is present.

This is `switch-to-configuration test`, not boot-profile persistence proof. Recovery remains the earlier boot profile on reboot, or test-activate the previous system recorded in `installed.json` over the reserved console. No full-image flash/readback occurred.
