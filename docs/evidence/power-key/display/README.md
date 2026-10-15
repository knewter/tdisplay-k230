# A tap turns the panel off and on (task 2.3), 2026-10-14

Board-read plus operator, on the landscape image with
`shell-power-key.service` running. A recorder on the board polled Sway's
`DSI-1` power state once a second and logged uptime and boot ID:

```
start 2026-10-14T16:22:41-05:00 boot_id=ccd3f704-478b-4eff-b187-1c7bde3ae50f uptime=7611.10
16:22:41 uptime=7611.20 DSI-1 power="power": true
16:24:12 uptime=7702.22 DSI-1 power="power": false
16:24:16 uptime=7705.45 DSI-1 power="power": true
end 2026-10-14T16:24:18-05:00 boot_id=ccd3f704-478b-4eff-b187-1c7bde3ae50f
```

Operator, 2026-10-14, after tapping off and tapping on again: "it worked"
(the panel went dark and came back to the same session and brightness).
Uptime is continuous and the boot ID unchanged, so there was no reset.

Limits: no camera frame (camera waived by the operator, who took the bench
camera for other use) and no serial log (`/dev/ttyACM0` is not the K230 on
this bench). Brightness after the second tap is the operator's report only.

## The display in effect, with HDMI (2026-10-14)

The short press now sends `output * power off/on` (master `6e963323`). Before,
it always named `DSI-1`; with HDMI holding the one CRTC that stored "off" for
the absent panel, and after an HDMI unplug at 23:16:11 (boot `ce466eed…`) the
panel came back dark until another press.

Boot `1212fd5d13da43489234aed00b283490`, system
`/nix/store/cn5bc5bkd3xylm8c3bf8mbpwv8kba9b7-nixos-system-nixos-26.11.20260919.20b1ddd`,
from `journalctl -b 1212fd5d… -o short-precise | grep -E "INT0|Handling command .output|HDMI HPD"`:

```
23:44:01.124817 kernel: canaan-mipi-dsi 90850000.dsi: HDMI HPD: connected
23:44:32.128436 kernel: k230-pmu-pwrkey 91000000.pmu-pwrkey: INT0 press
23:44:32.304707 kernel: k230-pmu-pwrkey 91000000.pmu-pwrkey: INT0 release
23:44:32.317150 sway: Handling command 'output * power off'
23:44:37.434821 kernel: k230-pmu-pwrkey 91000000.pmu-pwrkey: INT0 press
23:44:37.664914 kernel: k230-pmu-pwrkey 91000000.pmu-pwrkey: INT0 release
23:44:37.676958 sway: Handling command 'output * power on'
23:44:59.860414 kernel: k230-pmu-pwrkey 91000000.pmu-pwrkey: INT0 press
23:45:00.517431 kernel: canaan-mipi-dsi 90850000.dsi: HDMI HPD: disconnected
23:45:00.525433 kernel: k230-pmu-pwrkey 91000000.pmu-pwrkey: INT0 release
23:45:00.531919 sway: Handling command 'output * power off'
23:45:01.800365 kernel: k230-pmu-pwrkey 91000000.pmu-pwrkey: INT0 press
23:45:01.953763 kernel: k230-pmu-pwrkey 91000000.pmu-pwrkey: INT0 release
23:45:01.964878 sway: Handling command 'output * power on'
23:45:16.164456 kernel: canaan-mipi-dsi 90850000.dsi: HDMI HPD: connected
```

Operator: "power key blanks the monitor and wakes it, unplug works". Limits:
the operator's word on the monitor and panel, no camera; the dark/lit state
after the 23:45 unplug is not captured separately.
