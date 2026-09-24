# Opt-in Qt Quick software probe

This package is a transient test client for the existing Sway session, not a
shell or compositor. `Probe.qml` uses only Qt Quick primitives: a bounded
`Flickable`, tap feedback, editable `TextInput`, an installed PNG, and a
reversible position/opacity animation. `--negative-effect` adds a
`ShaderEffect` bound to the installed PNG `Image` (a valid texture provider)
beside an always-visible solid reference. The software scene graph documents
the effect as unsupported, so its visual absence is an expected negative
control to capture, not a passing rendering feature.

The package wrapper fixes `QT_QPA_PLATFORM=wayland`,
`QT_QUICK_BACKEND=software`, `QSG_INFO=1` and clears inherited RHI forcing.
The future bounded trial must record those effective values with mapped libraries,
backend logs, actual buffer identity and presented pixels. The binary prints
its Qt version, QPA platform, requested Quick backend and control mode. The
source does not select a graphics API. Incidental Qt graphics libraries in the
closure remain subject to inspection. No Qt Multimedia, Qt Virtual Keyboard,
Quickshell, Controls, or external services are imported by the QML scene.

The 568×1232 initial window is a test viewport matching the panel pixels;
it is not a claim about the eventual scaled logical UI size. Real touch,
keyboard/input-method behavior, animation continuity and performance require
the reserved-board trial. The binary is not added to the normal image.
