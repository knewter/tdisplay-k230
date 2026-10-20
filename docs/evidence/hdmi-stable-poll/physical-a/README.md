# Partial physical candidate check, 2026-10-20

The operator reported: “panel returnes, bottom swipe works. it's great. everything smooth. when i drag down the top drawer it's a bit stuttery, perhaps worth figuring out why”. This confirms physical panel return and a bottom-edge swipe, with subjective smoothness apart from the top notification shade. It does **not** explicitly confirm HDMI reconnection or the four-finger trackpad gesture, so task 2.3 remains open. The shade report is investigated separately under `the-shell-profiles-reported-interaction-jank`.

Before the action, instructions asked the operator to unplug HDMI, check panel return and bottom-edge Overview, then reconnect HDMI and use a four-finger inward pinch on the handheld touchscreen to open Overview on the monitor. A follow-up asks only for the remaining reconnect/pinch result. No result has been inferred from elapsed time.

The read-only watcher ran 19:08:45.509–19:15:37.650 UTC, took799samples and observed17state changes. Its boot/current/persistent guards stayed unchanged. At19:09:06.642 the HDMI connector became disconnected; at19:09:07.170 DSI-1 was active with transform270, scale1 and logical1232×568, retaining landscape. Subsequent software scene changes include Overview and Home, correlated with the operator's physical report. These scene states alone are not proof of finger movement, glass latency, or HDMI replug success. The final observed output remained the panel with HDMI disconnected.

The watcher generated no input. It was stopped before a separate shade performance trace so its repeated IPC requests would not run during that measurement. No camera or serial capture was collected. `manifest.json` pins the source hash, complete `states.jsonl` hash, boot/system identities, interval and counts. `watcher.py.txt` is the exact source; its protected SSH invocation was:

```
python3 /var/tmp/k230-hdmi-stable-poll-candidate-a/stable-poll-physical-watch.py --directory /var/tmp/k230-hdmi-stable-poll-candidate-a/physical-a --system /nix/store/hpmzja32mncizz7s49ylr8pj9cy5npvg-nixos-system-nixos-26.11.20260919.20b1ddd --fallback /nix/store/j30yag05ic9k68n9dzbzindgf4ardp08-nixos-system-nixos-26.11.20260919.20b1ddd --boot-id c17ee483-0191-48ea-986a-9738a274393e --seconds 600
```

Exit0 and all three unchanged guards pass. The normal boot files and persistent profile still select the previous image; promotion awaits the remaining physical gate.
