# Theme picker follows the contact displacement

Recorded 2026-09-27 UTC on the reserved physical board. Source `0c199c76`
changes both carousel geometries to invert the rendered card-center path and
coalesces pending picker motion before drawing. This is injected input and
native capture evidence; real-finger acceptance and persistent installation
remain open.

The old formula divided motion by the collapsed thumbnail pitch (49 pixels
for themes, 43 for backgrounds), although the expanded center moved much
farther. The new formula maps a contact displacement back through that actual
center trajectory. A held contact does not coast; a release after a stationary
hold expires the old velocity.

## Identities and commands

`manifest.json` names the exact source, candidate system and four candidate
boot artifacts. `trial-runtime.json` records the successful guarded
`switch-to-configuration test`: candidate `7hhr1fp…`, booted/installed baseline
`11y992kp…`, unchanged kernel, all four shell services active, and no failed
units. A 15-minute automatic restoration timer was armed before activation
and restarted once to allow operator testing. This did not modify normal boot
files or the system profile.

The full candidate was built with:

```sh
nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel --no-link
```

The archived `k230-picker-baseline.py` is the exact input helper imported by
`tracking-probe.py`. Both were staged under `/run/` on the board; its Python
was `/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3`.
After opening Settings → Themes and waiting seven seconds, the commands were:

```sh
python3 /run/k230-picker-tracking-probe.py --label old --output /run/picker-tracking-old.json
python3 /run/k230-picker-tracking-probe.py --label new --output /run/picker-tracking-new.json
```

Each command ran only against its corresponding verified Rust executable
(full paths in the JSON). The virtual touchscreen name and virtual sysfs path
are checked before any event is written. Four 200 ms drags move 20 pixels,
left then right in each row, with 1.5 seconds held stationary before release.
Both runs retained the same saved-generation hash throughout. Twenty motion
samples were processed in every phase.

## Observed processing backlog

| Row/direction | Old last motion after injection ended | New |
| --- | ---: | ---: |
| Theme left | 227.365 ms | 27.481 ms |
| Theme right | 219.772 ms | 18.914 ms |
| Background left | 147.354 ms | 71.993 ms |
| Background right | 151.848 ms | 0.674 ms |

The candidate committed 2–4 frames per contact/hold period for 20 motion
samples, rather than rendering every sample. Four commits followed release
to settle back to the nearby center. Journal reception timestamps approximate
userspace processing; these are not scanout latency or presentation FPS.
This is one short before/after comparison, not task 13's matched three-pair
performance test. The visible themes differed (old Hackerman, new Solitude),
so image-content cost and cache warmth are uncontrolled here.

## Held geometry

Each native pair was captured separately from timing using `grim`, then
`native_touch('/dev/input/event1',284,430,264,430,held=...)`. The callback
waited 1.5 seconds and captured before releasing the contact. The same verified
virtual input helper was used. The screenshots were visually reviewed.

![Baseline before contact](old-before.png)
![Baseline held after a 20-pixel drag](old-held.png)
![Candidate before contact](new-before.png)
![Candidate held after a 20-pixel drag](new-held.png)

The old expanded preview's center moves roughly 104 pixels; the candidate
center moves roughly 20 pixels. Card width also changes as focus interpolates,
so this demonstrates center tracking, not rigid translation of every edge.
No theme was applied by these captures. Native images do not prove the panel's
physical response, and the stationary hold does not prove fast-fling quality.

Host checks at the source revision passed 13 carousel tests and 19 route
tests. Task 14.4 still requires the operator's real-finger verdict; tasks
11.3/13 still require the broader performance and memory comparison.
