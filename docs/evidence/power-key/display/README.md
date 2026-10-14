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
