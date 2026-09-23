# Preliminary transferred-launcher check

The reviewed launcher was transferred into the existing board session before
flashing the integrated image. Exact source, package, running system and native
image hashes are in [preflight.json](preflight.json). This is two injected touch
transitions, not the full acceptance matrix or a real-finger trial.

The launcher started at Apps page 1. These commands used the virtual touchscreen
created from `evemu-describe /dev/input/event0` with `evemu-device`; the actual
Goodix device was not exercised by a finger:

```sh
/run/inject-tap.sh /dev/input/event1 430 320 130 320
/run/inject-tap.sh /dev/input/event1 284 460 284 210
```

`tools/inject-tap.sh` was copied without changes to `/run/inject-tap.sh`.
`grim` sampled the settled surface after each command. The first capture shows
[Apps page 2](preflight-apps-page-2.png); the second shows a
[two-window overview](preflight-overview.png). Neither gesture launched a card.
The observed windows remained the same two terminal containers.

The [client metrics](preflight-metrics.txt) record final submissions after
137 and 152 ms. These are client wall-clock release-to-submit measurements,
not compositor presentation or optical timing. The preflight binary predates
process-CPU, buffer-count and page-state metrics, so those newer fields are
absent. `shell`, `seatd` and `k230-wifi` remained active. The 20-per-direction
matrix, keyboard-visible resource comparison, final image and real-finger
camera evidence remain open.

Native images were created by this project's launcher via the existing Wayland
compositor; they contain no third-party movie content. They are DATA evidence,
not shipped firmware or executable assets.
