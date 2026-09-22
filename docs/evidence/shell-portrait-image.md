# Verified portrait shell image

On 2026-09-22 the image built from `bafb59e` was flashed over U-Boot UMS,
without removing the card. `shell-usb-flash-portrait.txt` records the complete
write, direct readback comparison, and boot:

- Image: `/nix/store/3ss2r7bwgvxy1yhspkz2g42w504wlkvw-k230-sd-image.img`
- 2,308,689,920 bytes; write 180.9 seconds, readback 184.3 seconds.
- Every written byte matched before reset.
- Booted system: `/nix/store/07qjn49hhr8m57x4afiapaxdxngl44zp-nixos-system-nixos-26.11.20260919.20b1ddd`.
- Boot ID: `3c4583d7-01ad-4138-a75c-6063a248863e`.

`shell-portrait-startup.txt` records active Sway, no service drop-ins, the
normal `/home/shell` working directory, native 568x1232 output, `/dev/uinput`,
and successful automatic Nix database registration (571 closure paths). The
[physical startup recording](shell-features/startup-portrait/demo.mp4) shows
Terminal after automatic boot. The source camera recording is retained;
the presentation copy contains its first 110 seconds, rotated for viewing.
USB cables are attached, so this does not close the battery-only boot gate.

The [Monitor recording](shell-features/monitor-integrated/native.mp4) exercises
Apps → Monitor using injected touchscreen events. Its [screenshot](shell-features/monitor-integrated/screen.png)
shows the fixed Monitor title and readable portrait columns. The adjacent
`console.txt` records the running htop process using
`HTOPRC=/nix/store/9l7x6r7fqfdbbhjln3sh0g5hs44i4pwr-k230-monitor.htoprc`.
The startup transcript explicitly confirms no local htop profile existed at
test time. This verifies the shipped menu/configuration, replacing the earlier
live-profile workaround. It remains injected-input evidence, not a finger test.

The verified image is retained by the local Nix GC root
`result-shell-portrait-verified`. The previous working image remains available.
Home files were backed up outside the repository with mode 0600; their archive
SHA-256 is `6dfdf1dd3c1012f2a98b5c943ecb20f0dbe3aa595eb27e45feba6237601b85ef`.
No private archive or network credentials are part of this evidence.

USB host coexistence source was subsequently built separately; it is not part
of this flashed image. Its physical validation remains task 6.2 in the USB
change. The real-glass and cable-free shell checks remain open; see
[the operator checklist](../shell-hands-on-check.md).

The new Monitor source archive was retrieved and matched its on-board SHA-256:
`bbaedd2437c461121860b4371e3519ae4e9a9f60833baecd2eb1ffd9b9ef162c` (2,718,075 bytes).
Its 32 PNG samples and monotonic capture times are retained in
`shell-features/monitor-integrated/native-source.tar.gz`.

After recording, the checked home archive was restored privately and its temporary
board copy removed. `shell-portrait-restored.txt` records the active unmodified
shell, Terminal focus, keyboard display, and removal of the virtual touchscreen.
The board is released for ordinary use and the pending physical checks.
