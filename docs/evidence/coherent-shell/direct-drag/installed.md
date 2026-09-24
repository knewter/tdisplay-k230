# Corrected direct drag installed

Source `bbdbff5b3537cb0fa98b78978a1ec93833791d52` cross-built with:

```sh
nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel \
  --max-jobs 1 --cores 4 --no-link --print-out-paths
```

PASS, installed system: `/nix/store/vcy57djhmvagwmvc8z7ml8xmd0riqp4l-nixos-system-nixos-26.11.20260919.20b1ddd`. A 23-path,
10,552,336-byte closure delta imported with exit 0. A five-minute systemd
fallback to the previous working preview was confirmed active before
`switch-to-configuration test`; activation returned 0.

Under the coordinator's exclusive board/serial reservation,
`python3 tools/console.py /dev/ttyACM0 --wait=3` ran these observations (activation log excerpt):

```text
tail -12 /run/k230-direct-drag-activation.log
K230_ACTIVATION_EXIT=0

readlink -f /run/current-system
/nix/store/vcy57djhmvagwmvc8z7ml8xmd0riqp4l-nixos-system-nixos-26.11.20260919.20b1ddd

systemctl is-active shell shell-ui shell-session-bus shell-notifications k230-wifi
active
active
active
active
active
```

The fallback timer was stopped only after the exact target and all five
units were confirmed healthy. This is still a test activation: the original
boot profile is retained for reboot recovery. The update also includes the
landed Rust Settings/notification UI; those controls have synthetic QEMU
proof, not new physical acceptance in this record.

See `docs/evidence/coherent-shell/direct-reveal-drag-qemu/README.md` for
the old 100→135 pixel failure and corrected 100→100 pixel result, plus hold,
lateral movement and reversal. App-entry geometry and release behavior are
covered by `docs/evidence/coherent-shell/card-entry-direct-drag-host.md`.
These injected checks do not prove real-finger alignment, panel latency or
smoothness. The user was invited to retry slow drag, hold and reverse on
the installed device; that acceptance remains pending.
