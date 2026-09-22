## Context

See proposal.md — Why. What shapes the approach:

- `panel-canaan-universal.c` in the pinned kernel is fully device-tree driven,
  so a new panel is a `.dtsi`. The reference `k230-canmv-v3-lcd.dts` proves the
  pattern with `display-st7701-480x800.dtsi`.
- LilyGO's `rm69a10.c` is a working init sequence for this exact panel on this
  exact board. It is the source of truth; the datasheet is not.
- `docs/rtsmart-boot-log.txt` records the vendor bring-up order: power on,
  reset via GPIO22 three times, set backlight, `rm69a10_init`, set PHY
  frequency, DSI resolution init, `rm69a10_568x1232_init`.
- GT9895 is absent from the pinned tree, which carries only the older
  `goodix.c`. Mainline gained Berlin support around 6.7; the pin is 6.6-based.
- The panel is 568x1232 — portrait, and unusually tall. Anything assuming a
  landscape console will look wrong.

## Goals / Non-Goals

**Goals:**

- The panel lit and showing the console, proven by photograph.
- Touches reported with coordinates that track movement.
- Every divergence from the reference board written down.

**Non-Goals:**

- A UI toolkit, or any constraint on the later shell decision.
- GPU acceleration. There is no Mesa or Vulkan driver for the 2.5D block and
  everything is software-rendered; that is a known cost, not a problem to fix
  here.
- Backlight control beyond making the panel visible.
- Rotation or colour work.

## Decisions

**Transcribe the init sequence from `rm69a10.c`, not from the datasheet.**
The vendor code is observed working on this board. A datasheet sequence would
be a second source to debug against, and this project's standing rule is that
a datasheet grounds nothing — the RTL8189 datasheet described a working radio
whose enable line was never driven.

**Backport `goodix_berlin` rather than bumping the kernel.** Moving to a
mainline kernel new enough to include it was considered and rejected: the
pinned Xuantie tree carries the K230 SoC support this board boots on, and
trading a known-good SoC port for a touch driver is the wrong direction. The
cost is the first carried patch in the tree, and a record of it so a later
bump can drop it.

**Prove the panel with a photograph.** A `/dev/fb0` node, a mode set, and a
successful `ioctl` are all things this hardware can produce with nothing on
the screen. The Wi-Fi radio already demonstrated the pattern: the driver
reported `start ap successs!`, brought an interface up with an IP, and
transmitted nothing detectable by three separate receivers. A photograph is
the only evidence that cannot be produced by a pipeline that is lying.

**Bring up panel and touch as separate task groups.** They share only the
device tree. Coupling them would mean a touch failure blocks evidence that the
screen works, and the screen is the more valuable of the two.

## Risks / Trade-offs

- **The transcribed init sequence is subtly wrong** — wrong PHY frequency,
  wrong lane count, a missing delay. → Presents as a blank or corrupted panel.
  Mitigation: the vendor sequence is also *runnable* on this board by
  reflashing the RT-Smart image, so a known-good comparison is always one card
  away.
- **`panel-canaan-universal` cannot express something the panel needs.** →
  Then the decision to avoid a C driver is wrong and should be revisited
  explicitly rather than worked around in the device tree.
- **The backport does not apply cleanly to 6.6.** → Budget for adapting it;
  the input subsystem is comparatively stable, but this is the likeliest place
  for the estimate to slip.
- **Panel works, touch coordinates are rotated or mirrored.** → Common, and
  cheap to fix in the device tree once it is reported at all. Caught by
  requiring that evidence track a *deliberate movement*, not a single tap.

## Open Questions

- Whether the panel needs a regulator entry or whether the reset GPIO is
  sufficient to power it. Answerable when the first `.dtsi` is written, and it
  changes a task's contents rather than the approach.
