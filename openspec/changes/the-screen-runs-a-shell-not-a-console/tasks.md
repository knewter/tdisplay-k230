# Tasks

**This change cannot start until `the-screen-comes-up-under-linux` is done.**
It needs `/dev/dri/card0` with a mode set on a real panel, and touch events
with coordinates. Neither exists today.

Group 2 is the only **build-host claim** here — it can be answered on
`solomon` with the board in pieces. Everything else is a **hardware claim**:
QEMU's `k230` machine models no display pipeline, so no compositor running on
this panel can be proven under emulation, and a task in groups 1 or 3-6 that
cites a QEMU run is wrong.

Groups 1 and 2 are independent of each other and both come before group 3.
Group 1 is first in order because it is the cheapest way to find out the whole
approach is wrong.

## 1. Find out what the DRM device actually is

The compositor choice rests on dumb buffers existing and the primary plane
speaking a format Pixman speaks. Both are currently assumptions. Answer them
before building anything.

- [x] 1.1 Capture the full DRM capability dump from the booted board: driver name, whether a `/dev/dri/renderD*` node exists, and the `DRM_CAP_DUMB_BUFFER` capability. Verify with `./tools/console.py /dev/ttyACM0 --wait=3 "drm_info"` and commit the output to `docs/evidence/drm-info.txt`
- [x] 1.2 Record the pixel formats the primary plane advertises, and state explicitly whether `XR24` (XRGB8888) and `AR24` (ARGB8888) are among them. Verify by extending `docs/evidence/drm-info.txt` with the plane format list and a one-line verdict on whether wlroots' preferred format is available
- [x] 1.3 Confirm a dumb buffer can actually be allocated and scanned out, independently of any compositor. Verify with `./tools/console.py /dev/ttyACM0 --wait=3 "modetest -M <driver> -s <connector>:568x1232"` plus a photograph of the test pattern, both committed

**Proves group 1 — hardware claim.** `drm_info` and a photographed `modetest`
pattern, committed under `docs/evidence/`. If 1.1 shows no dumb buffer support,
stop: the design's premise is wrong and the fallback is a direct DRM or LVGL
shell, which is a different change.

## 2. The stack cross-builds, and costs what we said it would

- [ ] 2.1 Add a Nix module for the shell stack — sway built with `enableXWayland = false`, plus `foot`, an on-screen keyboard and `seatd` — behind an option that is off by default, so the existing minimal closure is unaffected until it is switched on. Verify with `nix eval .#nixosConfigurations.k230.config.system.build.toplevel.drvPath` succeeding with the option off and with it on
- [ ] 2.2 Cross-build sway alone before the rest, because it is the derivation most likely to fail. Verify with `nix build .#shell-compositor` and record the store path
- [ ] 2.3 Cross-build the whole closure with the shell enabled and measure it. Verify with `nix build .#nixosConfigurations.k230.config.system.build.toplevel`, and commit the wall-clock time, the derivations-built count and the resulting closure size to `docs/evidence/shell-build.txt` against the 89-derivation / 875 MiB estimate in `docs/display-environment-options.md`
- [ ] 2.4 Record any derivation that refused to cross-compile and what was done about it. Verify by extending `docs/evidence/shell-build.txt`; if the list is empty, say so explicitly rather than leaving the section out

**Proves group 2 — build-host claim.** `nix build
.#nixosConfigurations.k230.config.system.build.toplevel` on `solomon`, with the
measurement committed. This says nothing whatsoever about the board.

## 3. First light: does a Pixman compositor start on this device at all?

`cage` is 68 derivations against sway's 89 and answers the one question that
could invalidate everything. It is a probe, not a destination — it has no
layer-shell and so can never host the keyboard.

- [ ] 3.1 Build a throwaway system with `cage` and `foot` and start it on the board. Verify with `./tools/console.py /dev/ttyACM0 --wait=3 "cage -- foot"` and a photograph of a terminal on the panel
- [ ] 3.2 Capture which renderer and which allocator wlroots selected, and confirm it reached the Pixman renderer and the DRM dumb allocator rather than failing over to them noisily. Verify by committing the `WLR_DEBUG`-level log to `docs/evidence/compositor-first-light.txt`, showing the `Trying to create drm dumb allocator` line and no GLES or GBM error

**Proves group 3 — hardware claim.** A photograph plus
`docs/evidence/compositor-first-light.txt`. If this fails, the failure is the
most valuable thing this change produces and it gets written down before
anything else is attempted.

## 4. sway owns the panel

- [ ] 4.1 Switch the module on, start sway at boot with no getty prompt and no display manager, with `WLR_RENDERER=pixman` set explicitly. Verify with a photograph of the board booting unattended to a sway session with a terminal, no cable attached
- [ ] 4.2 Configure the output as 568x1232, `transform normal`, scale 1, and confirm sway agrees. Verify with `./tools/console.py /dev/ttyACM0 --wait=3 "swaymsg -t get_outputs"` committed to `docs/evidence/shell-session.txt`
- [ ] 4.3 Record whether sway's built-in touch auto-mapping fired — whether the output is named `DSI-1` and whether the GT9895's `ID_PATH` starts with `platform-` — and add an explicit `map_to_output` regardless. Verify with `./tools/console.py /dev/ttyACM0 --wait=3 "swaymsg -t get_inputs"` appended to `docs/evidence/shell-session.txt`, showing the touch device mapped to the panel

**Proves group 4 — hardware claim.** A photograph of an unattended boot into
sway, plus `docs/evidence/shell-session.txt`.

## 5. A person can use the board with no cable

- [ ] 5.1 Add the on-screen keyboard as a layer-shell client that can be summoned and dismissed by touch. Verify with a photograph of the keyboard over the terminal and a second photograph with it dismissed and the terminal fully visible
- [ ] 5.2 Type a command entirely on the panel and show its output on the panel. Verify with a photograph of the typed command and its result — this task is not complete on a keyboard that appears; it is complete on a command that ran
- [ ] 5.3 Confirm a press lands on the key that was pressed, not a neighbour and not its mirror. Verify by typing a string that distinguishes the four rotations and mirrorings of the layout, photographed, with the string and the reasoning recorded in `docs/evidence/shell-session.txt`
- [ ] 5.4 If the axes are wrong, fix them in the device tree rather than in the compositor, and record which layer the fix landed in. Verify by stating in `docs/evidence/shell-session.txt` whether a `touchscreen-swapped-x-y`/`touchscreen-inverted-*` property, a libinput calibration matrix, or nothing at all was needed — and confirm that no more than one of them is in force

**Proves group 5 — hardware claim.** Photographs of a command typed on the
panel and its output, committed under `docs/evidence/`.

## 6. Find out whether it is fast enough

There is no prior art for Pixman composite throughput on a C908. The number
does not gate this change; not having it does.

- [ ] 6.1 Measure the compositor's frame time at 568x1232 under a representative load — a terminal scrolling and the keyboard shown. Verify by committing the measurement and the method to `docs/evidence/shell-performance.txt`
- [ ] 6.2 Record resident memory for the whole session against the board's 1 GiB. Verify with `./tools/console.py /dev/ttyACM0 --wait=3 "free -m; ps aux --sort=-rss | head -15"` appended to `docs/evidence/shell-performance.txt`
- [ ] 6.3 State a verdict in `docs/display-environment-options.md`: whether a compositor is viable on this board, or whether a direct DRM/KMS shell with no compositor is now the recommendation. Verify by the document saying one or the other in a sentence, with the measurement cited

**Proves group 6 — hardware claim.** `docs/evidence/shell-performance.txt`,
committed.

## 7. Ground the specs

- [ ] 7.1 Resolve the `UNVERIFIED` markers in `runtime/shell` against the committed photographs, logs and measurements, or restate precisely what remains unproven. Verify with `openspec validate the-screen-runs-a-shell-not-a-console`
- [ ] 7.2 Confirm the spec site accepts every requirement — each declaring either a marker or a grounding citation, with every cited `docs/` path committed. Verify with `./scripts/build_site.py` exiting zero
- [ ] 7.3 Record the measured build cost in the `runtime/shell` requirement that asks for it, replacing the estimate with the number. Verify with `openspec validate --all`
