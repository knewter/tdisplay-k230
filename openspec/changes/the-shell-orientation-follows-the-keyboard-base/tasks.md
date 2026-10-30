## 1. Detection and state machine (host)

- [ ] 1.1 Write the probe as a small program with an injectable bus (answers for 0x20 and 0x6B, none, one, timeout) and the state machine of D2 (attach 3, detach 5, partial result holds, 10 s dwell, touch deferral capped at 2 s), no hardware access.
- [ ] 1.2 Unit tests: clean attach, clean detach, chatter, partial result, probe timeout, deferral cap, boot decision with and without error (portrait on error).
- [ ] 1.3 Proof, host only: the test command added in 1.1 (named in the commit), result recorded. Claims nothing about the board.

## 2. Nix wiring (host build, QEMU)

- [ ] 2.1 Add `panelTransform = "auto"` and `keyboardBaseTransform`; keep `"normal"` default; assertion that `initialSplash` is incompatible with `"auto"`.
- [ ] 2.2 `k230-orientation` service: initial decision before the compositor, `/run/k230-shell/orientation`, poller, `swaymsg output DSI-1 transform` on change; compositor started with the output-turn renderer under `"auto"` (D5).
- [ ] 2.3 Switch `textfx-service.nix` and `touch-trackpad-service.nix` to the file under `"auto"` (D4); keyboard-height default from the logical size.
- [ ] 2.4 Proof: `nix build .#nixosConfigurations.k230.config.system.build.toplevel` with `"auto"` evaluating, and the existing fixed profiles' derivations unchanged (`nix build` of the landscape profile's attribute).
- [ ] 2.5 Proof, QEMU: boot the image under `qemu-system-riscv64 -machine k230` with a fake bus answering and not answering; the file and the Sway transform follow. This proves the service and Sway wiring only; QEMU models no panel, touch or I2C4 chips.

## 3. Running surfaces (host, then QEMU)

- [ ] 3.1 Extend the render harness (`render_responsive_evidence`) to apply a portrait to landscape to portrait configure sequence to every shell surface and compare with the fixed renders; fix any surface that keeps a stale size.
- [ ] 3.2 Make the card shell adapter re-run its size-dependent setup on an output transform change (D5); proof with a Sway session under QEMU rotated by `swaymsg`.
- [ ] 3.3 Proof, host: the harness's byte comparison; QEMU: the rotation session with Foot and the shell clients running and still running afterwards.

## 4. Board: injected events (board, no operator)

- [ ] 4.1 Measure portrait with the output-turn renderer on against current portrait (D5) with the existing drawer-scroll workload; record in `docs/evidence/shell-follows-base/`.
- [ ] 4.2 With the base state faked (the service's test hook, not the bus), rotate live: `grim` captures of Home, Drawer, shade and Settings in both orientations and one terminal and one running video across a rotation; record whether each app survived.
- [ ] 4.3 Injected taps at the four glass corners before and after a rotation with `tools/inject-tap.sh`; compare against the recorded mapping; HDMI-active case if an HDMI monitor is available.
- [ ] 4.4 Proof: a named `tools/msh.py` invocation per capture and the files under `docs/evidence/shell-follows-base/`. This is an injected-event, native-capture claim, not a glass or finger claim.

## 5. Board: the real probe

- [ ] 5.1 Base-absent boot: `./tools/console.py /dev/ttyACM0 --wait=3 "<probe and journal>"`; record no repeated bus errors, portrait first frame, the probe's wall time. Settles the display/keyboard UNVERIFIED marker.
- [ ] 5.2 Base-present boot: landscape first frame, the stage 1 and Linux orientations logged together.

## 6. Physical attach and detach (operator, stays open until done)

- [ ] 6.1 The operator clips the powered board into the base and removes it, at least three times each way, while the shell shows Home and a terminal; record the console journal with timestamps of every probe state change and every rotation, the connector's observed bounce, and the operator's account that the display ends upright each time. Do not tick without the operator's observation; no inference from injected or faked state.
- [ ] 6.2 Revise the debounce constants from 6.1 and record the final values in the design.
- [ ] 6.3 Operator decision on open questions 1 and 2 of the design (default profile, forced rotation).

## 7. Close

- [ ] 7.1 `openspec validate the-shell-orientation-follows-the-keyboard-base --strict`; archive only when 4, 5 and 6 are done and their evidence is committed.
