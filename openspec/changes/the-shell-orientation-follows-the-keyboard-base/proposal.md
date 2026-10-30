## Why

A person holding the board bare sees a landscape shell only if the image was built for the keyboard case, and a person who clips the board into the case sees portrait unless a different image was built. Today the shell's rotation is a build-time choice (`k230.shell.panelTransform`), so moving between holding the board like a phone and typing on it with the base means flashing another image. The user's rule is: "should orient like a phone if no keyboard, rotated for keyboard default if keyboard".

The boot text-effects change already applies this rule to the boot animation (design D15), picking portrait or landscape at power-on. It records, as a cost, that a stage 1 "portrait" followed by a landscape shell, or the reverse, is a visible change at the hand-off, because the shell does not rotate by itself. This change makes the shell follow the same rule, and follow it while running.

## What Changes

- The running shell is in portrait (Sway `transform normal`, 568x1232) when no keyboard base is present and in the existing keyboard-case landscape (`transform 270`, 1232x568) when it is. It rotates when the base is attached or detached at runtime.
- "Base present" is decided by a read-only probe of the base's I2C chips, with hysteresis, by a small orientation service. Design D1 records why the TCA8418 input device is not the signal.
- The shell's first frame and the boot animation use the same decision, taken once before the compositor starts, so there is no rotate at the stage 1 to Linux hand-off when the two agree.
- Touch keeps landing under the finger after a rotation, in both orientations.
- Running apps are handled by the compositor's configure path; the proposal says what each client class is expected to do and which of those expectations are still unobserved.
- The build-time `panelTransform` stays as the rule when following is off, so every existing profile and its evidence is unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `runtime/shell`: the panel orientation can follow the keyboard base at run time; running surfaces and apps are re-laid out; rotation is debounced.
- `display/keyboard`: the system reports whether the base is attached, continuously, from a read-only probe that survives a hot attach.
- `display/touch`: touch mapping follows the active panel orientation.
- `display/boot-splash`: the boot animation and the shell's first frame share the orientation decision.

## Impact

Nix and userspace only: a new orientation service and option in `nix/shell.nix`, the Sway startup config, `nix/textfx-service.nix`, `nix/touch-trackpad-service.nix`, and any other consumer of `panelTransform` that needs a run-time value (the on-screen keyboard height default, the `initialSplash` assertion). Possible compositor work in `nix/card-shell/adapter.c` and the wlroots output-turn patch if a live transform change is not already handled (design D5). Rust shell client changes only where a live geometry change is shown not to re-lay out.

Needs the physical board for the acceptance evidence. The detection logic, debounce and state machine, the Rust relayout and the Nix wiring can be proved on the host and under QEMU first; the injected-event, touch and physical attach/detach evidence cannot.

Non-goals: rotating HDMI (its transform stays as `hdmiTransform`); a user-facing "lock rotation" setting or accelerometer rotation (the board has no IMU in use here); portrait-upside-down or 90 degree landscape; changing stage 1 (the probe there belongs to the boot text-effects change); detecting the base from a GPIO or a device-tree change; changing what the base's keys, backlight or battery do.
