# Saved theme and backgrounds resolve after package relocation

Physical board, 2026-09-27 UTC. Candidate source `433a4226`, system
`/nix/store/11y992kp7bikr5hg21i2azfvmca43i7i-nixos-system-nixos-26.11.20260919.20b1ddd`.
Both booted and running system identities matched the candidate during this
one-time boot. The exact kernel and service executables are in
[result.json](result.json).

![Saved theme and current background correctly recognized](current-theme.png)

Before the repair, the catalog returned a null active ID and the background
row stayed loading; see [the browsing observation](../working-set/README.md).
With the repair, `k230-theme list` returns an active ID, 23 catalog entries
and the preserved generation. Its saved report contains five backgrounds.
The native image shows the saved theme centered, marked “Current theme,”
and its background row populated with “Current background” on the saved
selection. The generation identity hash exactly matches the earlier runs;
no theme was activated and no saved pointer was rewritten.

## Reproduction and limits

After verifying the candidate's system and service identities, show Settings
as the shell user:

```sh
runuser -u shell -- env XDG_RUNTIME_DIR=/run/shell k230-shell-rust --surface settings
```

The coordinator injected one tap at `(480,130)` through the distinct virtual
touchscreen, using `native_touch` from the [browsing collector](../working-set/capture.py).
The fixture verifies its name and `/sys/devices/virtual/input` provenance;
the physical touch device is never written. After the picker settled:

```sh
runuser -u shell -- env XDG_RUNTIME_DIR=/run/shell WAYLAND_DISPLAY=wayland-1 grim /run/shell/picker-fixed.png
runuser -u shell -- env XDG_RUNTIME_DIR=/run/shell k230-theme list
```

Raw list output remained private; the committed result retains only counts,
booleans, a generation identity hash and approved runtime identities.

This establishes correct selection lookup and populated content on the
candidate. It is not the repeated browsing measurement, background-drag
acceptance or a verified normal-boot installation. The subsequent normal
install completion check lost its serial session; normal reboot selected
the earlier system and stopped responding. Recovery and install verification
remain with the coordinator. Task 12.2 stays open until its remaining
interaction/measurement gates are recorded; task 11.3 remains open for
swipe performance.
