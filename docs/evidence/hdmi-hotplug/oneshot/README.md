# One-shot HDMI boots, 2026-09-29

Evidence class: **physical board, serial console**. Both boots were one-shot:
I interrupted U-Boot and loaded the kernel, DTB and initrd by hand with
`ext4load` and `bootm`. `/boot` was never changed, and a normal reboot
returned to the panel build each time. An HDMI monitor was attached, as the
operator reported.

## Boot 1: Oops (`boot1-oops.txt`)

- Kernel: feat/hdmi-bridge 5ef406ca. DTB: `k230-tdisplay-hdmi.dtb`.
- The LT9611 probed (revision `0xe2`).
- `canaan-drm` then failed with "Failed to bind all components".
- Its error path oopsed in `kfree` <- `drm_crtc_cleanup`. The DSI component
  had been added at probe, so the DRM master bound before the bridge
  existed.
- The board hung until the operator pressed reset.

## Boot 2: probes, no picture (`boot2-probe.txt`)

- Kernel: plus the "add the DSI component from host attach" fix.
- Userland: the panel system that was on the board, `x1xbs5qd`.
- The kernel log shows, in order:
  - `canaan-mipi-dsi: Attached device lt9611`;
  - both components bound;
  - `Initialized canaan-drm`.
- `card0-HDMI-A-1` exists and reads `disconnected`. The LT9611 HPD register
  `0x825e` read `0x78`, with bit 2 clear. The chip's IRQ count stayed at 0.
- `echo on > .../status` forced the connector on:
  - the EDID was 0 bytes, so the kernel used fallback modes (1024x768 and
    lower);
  - fbcon enabled the CRTC (`enable=1 active=1`);
  - the DSI PHY came up at 396000 kbps per lane.
- The LT9611 video check still read all zeros:
  - driver log: `hactive_a=0 ... h_total_sysclk=0`;
  - a live register read gave the same result.
  - Setting `0x8303=0x40` or `0x830a=0x03` by hand changed nothing.
- **Not observed:** any image on the monitor. The operator was not asked
  during this session.

## Open questions, not resolved

- The driver can only drive the LT9611's port A from a single-DSI setup;
  port B is used only as the second half of a dual-DSI link. Per the
  schematic, this board wires DSI to port B (`MLRXB_*`). The vendor DTS uses
  `port@1`, which this kernel's `lt9611_parse_dt()` rejects without a
  `port@0`. So LILYGO's working kernel must have had a different or patched
  LT9611 driver.
- It is unknown whether `canaan_dsi` actually starts HS video with a bridge
  output, since its enable path was written for a panel.
- There was no HPD and no EDID. Either the connector's +5V or the DDC is not
  reaching the monitor, or the monitor was off or on another input.
