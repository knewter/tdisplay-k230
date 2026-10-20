# Accepted native Settings default: ordinary startup and cleanup

The operator said “top drawer's good to go what's next go on”. A fresh protected query matched the exact normal runtime candidate, including RustPID3724, before promotion. [Summary](summary.json), [promotion](promotion.json), [ordinary boot](ordinary-boot.json) and [final normal controls](final-control.json) distinguish persistent file selection from an actual fresh ordinary boot.

The accepted system is `/nix/store/p501mchy0dq9lyjnaxwkx5s2pdm4i2yj-nixos-system-nixos-26.11.20260919.20b1ddd`; current, booted and persistent paths all match after ordinary `systemctl --no-block reboot`. Fresh boot ID9cc88abc-dc62-490e-8035-5d4832558a41 replaces69e90426; GNU kernel buildID7a61d8cea3e26df94695189b766de3fd66fa6860 remains the same. Sway1062 and Rust1076 retain their accepted executable hashes. The default native Settings wrapper is selected normally without a runtime override or tracing. Landscape DSI1232×568/transform270/scale1 at52.19Hz, CPU0, original Pixman flags, max_render_time8, active services, physical touch and idle Foot are verified. New Sway config7khi8238 has expected wrapper references; no configuration-byte-identity claim is made across the userspace closure update.

[Host artifact audit](host-boot-plan.json) rejected an initial assumption that initrd would change: actual initrd/Image/logo are identical. Only the generated DTB `/chosen/bootargs` and `bootargs.txt` change, each by exactly one old→new init system path. Source DTB hardware configuration is unchanged. Both small files were backed up to a root-owned rollback directory, copied with checksum/fsync/atomic rename (bootargs last), and protected boot files were verified unchanged before selecting the persistent profile. Existing hpmz and j30 recovery roots/backups remain; the new accepted root and hpmz rollback root are retained. No large boot payload or stage1 write occurred.

The ordinary reboot request exited0. SSH took about98s to return; early connection/timeout observations stay in the observer receipt. Success requires the new boot ID, all three system paths, actual GNU note and exact init token, not just the request or a disconnected transport. No UART or filmed boot is claimed.

The fresh status command as the shell user returned0/schema1 with the four expected control keys. Finalizer checks normal services/output/flags/idle/control hashes before and after removing only two checksum-matched staging duplicates. Preboot trace/source directories and both runtime UI overrides disappeared with RAM at reboot; the finalizer's own new namespace was removed after checking source bytes. Nine root tracing hashes were identical around cleanup in the new boot, nop/events0/no instances, no owned timer remained, and the initial tracefs mount state was retained. Root has176,742,400unprivileged bytes available. Board lease58851 released0; no build slot is held.

Exact drivers are committed here. Commands used the protected SSH config outside Git:

```sh
ssh -F "$PROTECTED_SSH_CONFIG" k230 "$BOARD_PYTHON /run/pane23-shade-status/shade-status-promote.py"
ssh -F "$PROTECTED_SSH_CONFIG" k230 systemctl --no-block reboot
python3 ordinary-boot-observer.py.txt
ssh -F "$PROTECTED_SSH_CONFIG" k230 "$BOARD_PYTHON /run/pane23-shade-final/shade-status-finalize.py"
```

The full private kernel journal is hashed in summary.json; only Linux version, machine model and command-line lines are public. The executed finalizer asserts the status subprocess returned0 before reusing its local variable during file cleanup; its final status field retains that asserted value. This is runtime/deployment proof, separate from the operator's qualitative acceptance and the earlier software latency distributions. The134.129ms diagnostic outlier remains, with no universal smoothness or optical claim.
