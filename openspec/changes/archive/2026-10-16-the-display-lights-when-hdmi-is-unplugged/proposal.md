## Why

If the display is dark when the HDMI cable is unplugged, the panel comes back
dark too. Nothing then shows that the unplug worked; the person sees a black
handheld and has to guess that a power-key tap will wake it. On 2026-10-16 the
board did exactly this. A power-key press at 12:18:10 sent
`output * power off`, HDMI reported disconnected at 12:18:11, and DSI-1 was
created with the stored "off" and stayed dark until the next press at 12:18:48
(journal, same boot). The accepted power requirement asks for this: a short
press keeps its state "across an HDMI hotplug". The operator asked for the
opposite: "when hdmi unplugs, display should show up so you know it worked".

## What Changes

- An HDMI unplug turns the display on. The touch relay already notices the
  move from trackpad mode back to direct touch and restores the panel's touch
  mapping. It now sends `output * power on` with that mapping, once per
  unplug.
- The power-key daemon reads display power from Sway before acting on a short
  press, instead of trusting only its own cached state. The first tap after an
  unplug-wake then darkens the panel, rather than "waking" it a second time.
- Plugging HDMI in keeps today's behaviour; this change does not wake the
  monitor on plug.

## Non-goals

- Waking on plug-in, on charger events or on any other hotplug.
- Changing hold behaviour, the power sheet, brightness or the backlight driver.
- Measuring HPD latency (deferred by the operator in `display/hdmi`).

## Board

Needs the physical board for the final proof: an HDMI unplug while the
display is dark. Host tests cover the relay's command order and the daemon's
state sync.
