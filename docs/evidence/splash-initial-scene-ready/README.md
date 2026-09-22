# Initial compositor scene with panel readiness

The corrected opt-in splash image seeds Sway before its first output commit
and retires that seed after the terminal and actual Swaybar panel are ready.
The physical warm-boot recording does not reproduce the earlier 1.1–1.2 second
dark interval in the sampled transition. This remains an opt-in candidate;
it is not cold/battery-boot or real-touch acceptance.

## Build and deployment

[Build provenance](build.txt) identifies diagnostic image source `12c1b0e`,
image SHA-256 `df47afb9a6a777c5e5c649e3829d563a6b5850443e19373e1cdc3fb44c28eb39`,
and compositor source `56b60c7`. The [integration build](integration-build.txt)
produces the same kernel and optional compositor from the carried source.
[Default evaluation](default-config.json) confirms `panelConsole=true`,
`initialSplash=false`, ordinary Sway, and no splash environment in the daily
service. [Flash transcript](image-flash.txt) records successful image write,
reset, Linux boot and USB host checks. Routine full readback was skipped;
no home backup or network credentials were restored.

## Automatic handoff

The [120-second boot video](20260922T222835Z-initial-scene-panel-ready-boot.mp4)
and [camera audit](video-audit.md) place the sampled transition around
72.6–72.7 seconds. The [physical shell frame](panel-ready-shell.png) shows
portrait controls without the earlier obvious wrap or magenta swap.
The [native frame](shell-native.png) separately records compositor output.
Camera sampling does not exclude shorter unobserved transitions, establish
uninterrupted electrical scanout, or calibrate geometry and color.

[Runtime inspection](inspection.txt) records shell, seatd and firewall active,
the flag present, no fb0, first VO/DSI preservation, and the DRM owner releasing
only after its framebuffer is replaced. Sway logs both `initial splash seeded`
and `initial splash removed`, with replacement `commit_seq=6`. The first trial
used the wrong top-layer bar predicate and never retired its seed; this image
uses Swaybar's mapped bottom-layer `panel` surface and an actual view surface.
Presentation logs alone are not proof of what appeared on the glass.

## Recovery and controls

The [65-second controls video](20260922T223311Z-initial-scene-ready-controls.mp4)
uses serial commands, not finger input. `keyboard-show.txt` and
`keyboard-hide.txt` record explicit keyboard signals; the
[keyboard native frame](keyboard-native.png) shows the complete keyboard.
The camera's oblique reflective view limits physical key-label acceptance.

[Display off/on transcript](display-off-on.txt) records a deliberate
three-second power-off and normal full panel prepare afterward. Shell,
seatd and firewall remain active. The diagnostic panel-ID and power-mode
reads still report errors; this is not proof those reads work.
The [post-recovery native frame](after-dpms-native.png) records the recovered
shell. The [controls camera audit](controls-audit.md) observes the deliberate
dark interval around 29–32 seconds and the returning shell around 32–33
seconds, while leaving physical keyboard-label acceptance unresolved.

The unchanged asset loader was tested with a missing path and three-byte file
in the [preceding scene trial](../splash-initial-scene-trial/README.md): both
produce specific diagnostics and a usable shell. Its temporary overrides
were removed. The same kernel's missing-logo console and later full-prepare
regressions are recorded in the [preservation trial](../splash-preserve-trial/README.md).

## Keyboard visibility follow-up

The [focus-30 recording](20260922T224622Z-keyboard-visible-focus30.mp4)
resolves the repeated lower-panel key pattern while it is shown, followed by
its disappearance after hide. See the [camera audit](keyboard-visibility-audit.md),
[shown frame](keyboard-visible-shown.png), and
[hidden frame](keyboard-visible-hidden.png). This is visibility evidence;
individual label readability, calibrated geometry and real-finger accuracy
remain outside this result. The keyboard theme and image were unchanged.
`keyboard-visible-show.txt` and `keyboard-visible-hide.txt` identify the serial
signals. The [restored native frame](keyboard-visible-restored-native.png)
records the terminal back in its tiled layout with the keyboard hidden.

Tasks 5a.1–5a.3 now have build, review and physical regression evidence:
automatic boot and first shell, keyboard visibility, and display off/on.
Task 5.4 still requires its specified complete power-on evidence. No animation
or persistent simulation state is implemented here.
