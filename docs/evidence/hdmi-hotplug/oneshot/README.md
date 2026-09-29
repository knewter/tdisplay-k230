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

## Boot 3: monitor on (`boot3-monitor-on.txt`)

The operator reported the monitor had been off during boot 2. I repeated
the same one-shot boot with the monitor on and got the same result:
`card0-HDMI-A-1` read `disconnected`, the EDID was 0 bytes, `0x825e` read
`0x78` (bit 2 clear), and the lt9611 IRQ count was 0.

What the schematic `T-Display K230_V1.0_NEW.pdf` shows:

- Page 7: connector pin 18 (+5V) is fed from `VDD_5V` through D13. The DDC
  SDA/SCL pull-ups (R71/R72 10k) go to `VDD_5V`. HPD has a 100k pull-down
  (R70) and goes to LT9611 pin 13.
- Page 6: `VDD_5V` is the board's main rail. It comes from `PRE_VDD_5V`
  through a PMU-enabled MT9700 switch (U10), so it should be live whenever
  the board runs.
- Page 7 also notes "LT9611 swap". DSI reaches port B with the lanes
  reordered and two pairs P/N-swapped:
  - `MLRXB_D0` <- DSI D3
  - `MLRXB_D1` <- DSI D2, P/N swapped
  - `MLRXB_DC` <- DSI CLK
  - `MLRXB_D2` <- DSI D0, P/N swapped
  - `MLRXB_D3` <- DSI D1

LILYGO reports that their SDK kernel reads EDID on this hardware. That points
to a driver difference (port B, lane swap, and HPD/DDC setup) rather than a
board fault, but this is not proven.
