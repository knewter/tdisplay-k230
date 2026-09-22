## 1. Prerequisite and engine

- [ ] 1.1 Repair the existing static splash-to-Linux geometry and color handoff and record before/after physical evidence; verify the prior wrapped/color-swapped first-modeset case is absent before enabling animation.
- [ ] 1.2 Implement the portable C Game of Life rules, deterministic seed, glider insertion, and versioned state/checksum ABI; verify reproducible frame hashes on host for fixed seed and generation vectors.
- [ ] 1.3 Define the reserved-RAM ownership and address from the actual image memory map, including invalidation and fallback behavior; verify no overlap with stage 1, kernel, initrd, or shell allocations in the image inspection report.

## 2. Stage handoff

- [ ] 2.1 Add stage-1 frame rendering and last-frame/state publication without changing the repaired static handoff contract; verify U-Boot can render the default frames and writes a valid version/checksum record in a host or controlled image test.
- [ ] 2.2 Add early-Linux state validation and continuation after display ownership is ready; verify invalid/version-mismatched state falls back to the deterministic pattern and that logs identify the ownership pause.
- [ ] 2.3 Record a physical boot video and serial transcript showing stage-1 frames, Linux takeover, the documented pause, and first valid Linux frame; verify no uninterrupted-motion claim is made.

## 3. Touch and optional continuation

- [ ] 3.1 Add Linux touch glider insertion with no-touch fallback; verify injected touch drops a glider and the animation remains recoverable when the input device is absent.
- [ ] 3.2 Investigate U-Boot Goodix touch as an optional experiment only; verify separately whether probe, coordinates, and glider insertion work, leaving this task unchecked when hardware proof is unavailable.
- [ ] 3.3 Add optional Wayland continuation without removing persistent shell controls; verify Apps, Keyboard, Windows/Home, System, and recovery remain reachable in a shell capture.

## 4. Review

- [ ] 4.1 Run deterministic engine tests, image/state inspection, and OpenSpec validation; verify with the focused C test command, the named image inspection command, and `openspec validate --type change the-boot-shows-a-computational-game-of-life --strict`.
