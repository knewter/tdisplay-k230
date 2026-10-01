# Panel recovery after unplugging HDMI, 2026-09-30

Evidence classes: operator-reported disconnect failure; physical-board serial
inspection; controlled reboot and userspace reactivation. This record does not
prove automatic hotplug switching, visible panel pixels or real-finger input.

Source audit: master `75445cc19801a1d497c87b02af81a4e7db16e42c`.
The sole coordinator held the shared board/serial lock throughout.

## Observed failure

The operator unplugged HDMI and reported that the monitor went off but the
built-in panel did not come on. The running device-tree model was
`LILYGO T-Display-K230 (HDMI)`, and the only DRM output was `HDMI-A-1`.
There was no `DSI-1` connector for the compositor to enable. The HDMI sysfs
status still read `connected`; it therefore did not establish live cable state.

Sway PID 45627 had process state `Dsl`. An explicit two-second Sway IPC query
did not return. Its kernel stack was:

```text
modeset_lock+0xe2/0x150
drm_modeset_lock_all_ctx+0x2e/0x14c
drm_mode_obj_get_properties_ioctl+0xb6/0x1a4
drm_ioctl_kernel+0xb8/0x13e
drm_ioctl+0x21a/0x434
__riscv_sys_ioctl+0xb6/0xc4
do_trap_ecall_u+0x132/0x144
_save_context+0xba/0xba
```

This establishes a blocked kernel DRM ioctl after the reported unplug. It does
not identify the lock owner or prove which disconnect path caused the blockage.
No live connector teardown/rebind was attempted.

## Recovery performed

Preflight confirmed the normal boot DTB still named `LILYGO T-Display-K230`
without the HDMI suffix. Its SHA256 was
`ffeb528bba1b4c3ab5e6b6f63047cd9ae9512ed853126616853367e93dba2035`.
Boot selectors still pointed at `k230-tdisplay.dtb`. No DTB, kernel, initrd or
boot selector was replaced. A fresh host-only `nix build .#deviceTree --no-link
--print-out-paths` also succeeded; that new DTB was **not deployed**.

The existing panel boot arguments pointed at the older `x1xbs5qd…` system,
while the live userspace had been test-activated to the newer `r0knnb72…` system.
The board was synchronized, then rebooted with
`systemctl reboot --force --force` to avoid waiting on the blocked compositor.
The normal boot used the panel DTB. Its log showed the `universal` DSI device
attached, both canaan DRM components bound, and the framebuffer initialized.

Serial inspection then showed `DSI-1` connected and the old shell services
active. The latest already-installed userspace was reactivated using:

```sh
systemd-run --unit=k230-panel-shell-restore --no-block /nix/store/r0knnb72k3p3mpmbsnfgrk66yg8gl144-nixos-system-nixos-26.11.20260919.20b1ddd/bin/switch-to-configuration switch
```

The activation exited with `Result=success`, `ExecMainStatus=0`. The current
system and system profile resolved to `r0knnb72…`. The shell, shell UI and
trackpad relay were active; Sway was sleeping normally rather than blocked.
Sway IPC returned `DSI-1`, 568×1232, transform normal, active/power/DPMS true,
scale 1, and `max_render_time=8`. DRM state showed the Sway-owned RGB565
framebuffer on the panel CRTC, and backlight brightness was 254.
These are connector/scanout observations, not an optical image acceptance.

A subsequently collected and visually reviewed [native capture](native-panel.jpg)
shows Foot on the panel output. [Capture identity](capture.json) preserves the
exact command, timestamp, executables and SHA256. The serial base64 transfer
was framed and decoded into the original JPEG bytes; it was not cropped or
reconstructed. The native capture does not establish physical panel emission.

## Remaining gates and limits

- **UNVERIFIED:** visible recovered panel pixels and real-finger navigation;
  the coordinator requested an operator observation. The camera view did not
  supply usable visible-screen evidence and was not published.
- **Unimplemented:** automatic HDMI-to-panel switching without reboot. The
  installed kernel boot selects one downstream DSI device. Switching requires
  the separate live-driver/connector work in the HDMI proposal, not merely a
  Sway output stanza.
- **Open defect:** unplugging left Sway blocked in `modeset_lock`. Capture the
  lock owner and bridge/DRM worker stacks in a reserved, recoverable reproduction
  before choosing a kernel fix.
- **Not reconciled by this recovery:** the boot arguments still select the older
  panel system. The latest userspace was reactivated after boot. This record
  does not claim a fresh reboot persistently selects the latest shell.
- The HDMI Settings switch and one-shot restoration UI remain incomplete. No
  HDMI proposal task was checked or archived based on this recovery.

This recovery is separate from the six proposal-closeout acceptance gates.
It does not certify a patch-free kernel or any physical UX/performance budget.
