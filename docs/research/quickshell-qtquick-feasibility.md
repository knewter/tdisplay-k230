# Qt Quick and Quickshell on the K230 handheld

Research snapshot: 2026-09-23. This is a source and existing-evidence assessment,
not a cross-build, board run, or performance result. Quickshell source was read
at [`fae96f1a5b7f53de9b7e40e5b53c0b7a2e97b1d7`](https://github.com/quickshell-mirror/quickshell/tree/fae96f1a5b7f53de9b7e40e5b53c0b7a2e97b1d7);
the Omarchy source was read at [`28ceaae70ebac3a0edcc21f2faa77a90dc6d404c`](https://github.com/omacom/omarchy/tree/28ceaae70ebac3a0edcc21f2faa77a90dc6d404c).
No installer or source script was run. Upstream documentation links below are
live and may change; source links and local conclusions use the stated pins.

## Decision

**Conditional go for one small Qt Quick Wayland *app* preflight; no-go for an
Omarchy shell transplant or replacing Sway now.** Qt Quick has a documented
CPU raster scene-graph adaptation, unlike the GPU-surface dependency in the
[GPUI assessment](gpui-handheld-feasibility.md). That makes a plain Qt Quick
app a credible experiment on the existing Sway/Pixman display, but does not
establish the Qt Wayland buffer route, RISC-V closure, usable touch latency, or
combined client-plus-compositor cost on this board. Quickshell itself is a
conditional **second** experiment as a layer-shell client, not a compositor or
an automatic implementation of the live-card shell. Keep the current normal
Sway service and card/gesture work as the baseline.

## Rendering boundary

| Question | Source-grounded answer | K230 consequence |
| --- | --- | --- |
| How is software selected? | [Qt scene-graph adaptations](https://doc.qt.io/qt-6/qtquick-visualcanvas-adaptations.html) specify `QT_QUICK_BACKEND=software`. `QSG_RHI_BACKEND` selects a **graphics API** such as OpenGL or Vulkan for the RHI; setting it is not a CPU fallback. `QSG_INFO=1` reports the actual scene graph. | Pin the environment on the test process and retain startup logs; do not infer a backend from a rendered screenshot alone. |
| What draws? | The [software adaptation](https://doc.qt.io/qt-6/qtquick-visualcanvas-adaptations-software.html) uses Qt's raster paint engine and partial updates. Most simple Qt Quick scenes can run, while unsupported operations may be silently ignored. | Rectangles, text, images, a `Flickable`, tap, and a property animation are reasonable *test content*, not yet proven board features. |
| What fails or degrades? | [ShaderEffect](https://doc.qt.io/qt-6/qml-qtquick-shadereffect.html) does not render under `software`; Qt also excludes particle effects. [MultiEffect](https://doc.qt.io/qt-6/qml-qtquick-effects-multieffect.html) is shader-based. Software text can lose quality when transformed. Fractional display scaling disables partial updates by default; force-enabling them can artifact. | Avoid shader blur/shadow and text scaling in the first app. Retain an integer scale and verify partial-damage behavior and visible pixels. Do not count an invisible effect as successful rendering. |
| Does VG-Lite help? | The [local accelerator audit](../evidence/vglite-compositor-audit.md) establishes a vendor 2.5D command API, not EGL/GL/Vulkan/GBM. | Neither Qt RHI nor Quickshell gains GPU acceleration from VG-Lite today. A future bridge would be separate driver/renderer work. |
| How reaches Sway? | [Qt Wayland Client](https://doc.qt.io/qt-6/qtwaylandclient-index.html) supplies the Wayland QPA plugin, and [Qt's Wayland overview](https://doc.qt.io/qt-6.8/wayland-and-qt.html) discusses copying content to shared CPU memory when an accelerated integration is unavailable. | A `wayland` QPA + software scene graph + `wl_shm` buffer is the intended path, but actual client buffer selection, format acceptance, and pixels must be observed on K230. Qt *Wayland Compositor* fallback documentation is not proof for this client path. |

Normal [`nix/shell.nix`](../../nix/shell.nix) uses `WLR_RENDERER=pixman`,
Xwayland disabled, and RGB565 scanout on the 568 × 1232 panel. The Qt client
will rasterize its own buffer, then Sway still composites it. One full
568 × 1232 × 4-byte client image is about 2.67 MiB before buffering, caches,
QML heap, fonts, or Sway copies; this is arithmetic, **not** an RSS estimate.
The existing [card cache board evidence](../evidence/card-shell/scaled-cache-board/README.md)
already exceeds its CPU/tracking targets, so compare *combined* client and
Sway CPU under the same visible workload. Recent RVV Pixman/system builds do
not establish Qt application performance or change the software-backend limit.

Qt Quick bindings, property animations, and `Flickable` are useful for app UI,
but CPU work and Wayland frame pacing must be measured on glass; there is no
source basis to promise 60 fps. Qt's [performance guide](https://doc.qt.io/qt-6/qtquick-performance.html)
also treats scene complexity and lifetime as costs. The pinned Qt/QML build's
RISC-V QV4 JIT/bytecode configuration was **not verified** here: [Qt's QML
engine configuration guide](https://doc.qt.io/qt-6/qtqml-javascript-finetuning.html)
distinguishes JIT and interpreter behavior, but neither a generic target
listing nor another project's JIT claim proves this Nix closure. Record the
actual Qt configure summary and `QV4_FORCE_INTERPRETER=1` comparison, if
available, in the preflight. Even a working interpreter would need measured
animation/binding cost; do not label it unsupported without that build check.

## Quickshell is an additional layer, not the renderer solution

[Quickshell's pinned 0.3.1 build instructions](https://github.com/quickshell-mirror/quickshell/blob/fae96f1a5b7f53de9b7e40e5b53c0b7a2e97b1d7/BUILD.md)
require Qt Base/Declarative, libdrm, Qt ShaderTools and private Qt APIs; its
binary must be rebuilt for each Qt release to avoid private-ABI crashes.
Wayland adds client libraries/protocol generation. SVG icons need Qt SVG.
Feature flags can omit X11, PipeWire, crash handler, screencopy, and unrelated
integrations, but the *actual* target closure must be inspected rather than
assuming small footprint. Quickshell's [PanelWindow](https://quickshell.org/docs/v0.2.1/types/Quickshell/PanelWindow/)
uses layer-shell for bars, overlays, and backgrounds; Sway's advertised
`zwlr_layer_shell_v1`, keyboard focus, and anchor/exclusive-zone behavior must
be checked in the actual session. It would still be a client of Sway. A
full-screen Quickshell view cannot own Sway's card transforms, input routing,
or compositor frame callbacks merely by drawing QML above applications.

The pinned Quickshell source search found no unconditional `setGraphicsApi`
or forced RHI choice in core paths. Its optional screencopy/dmabuf code
[`src/wayland/buffer/dmabuf.cpp`](https://github.com/quickshell-mirror/quickshell/blob/fae96f1a5b7f53de9b7e40e5b53c0b7a2e97b1d7/src/wayland/buffer/dmabuf.cpp)
does branch on Vulkan/OpenGL and uses graphics resources. Disable
`SCREENCOPY` for a software-only panel trial: the pinned
[`src/wayland/CMakeLists.txt`](https://github.com/quickshell-mirror/quickshell/blob/fae96f1a5b7f53de9b7e40e5b53c0b7a2e97b1d7/src/wayland/CMakeLists.txt)
places both buffer and screencopy subdirectories under that parent flag.
Check the generated CMake feature summary nevertheless; child flags alone
do not disable the parent. Do not claim that a rendered
plain panel proves screenshot/video or arbitrary Quickshell modules work.
The [upstream install guide](https://quickshell.org/docs/v0.2.1/guide/install-setup/)
is for release 0.2.1, not the pinned 0.3.1 source; it lists Nixpkgs packaging,
but does not prove this repository's riscv64 cross
build or installed size. [Quickshell desktop entries](https://quickshell.org/docs/v0.2.1/types/Quickshell/DesktopEntry/)
could inform a launcher; their API is not a reason to replace the already
scoped launcher without a measured benefit.

## Pinned Omarchy configuration: concrete incompatibilities

The 104 pinned shell QML files include useful primitive `Image`, `Text`,
`Flickable`, and animation patterns. They also include
[`background/Background.qml`](https://github.com/omacom/omarchy/blob/28ceaae70ebac3a0edcc21f2faa77a90dc6d404c/shell/plugins/background/Background.qml),
[`lock/LockView.qml`](https://github.com/omacom/omarchy/blob/28ceaae70ebac3a0edcc21f2faa77a90dc6d404c/shell/plugins/lock/LockView.qml),
and [`bar/widgets/Tray.qml`](https://github.com/omacom/omarchy/blob/28ceaae70ebac3a0edcc21f2faa77a90dc6d404c/shell/plugins/bar/widgets/Tray.qml)
using `MultiEffect`/`layer.effect`; these visuals cannot be accepted as-is
under Qt software rendering. [`PopupCard.qml`](https://github.com/omacom/omarchy/blob/28ceaae70ebac3a0edcc21f2faa77a90dc6d404c/shell/Ui/PopupCard.qml)
uses `HyprlandFocusGrab`; the bar, workspace, and keyboard widgets use
`Quickshell.Hyprland` monitor/workspace/keyboard state. Porting those behaviors
to Sway would change interaction and focus, not merely color tokens.

Omarchy's [`NotificationServer`](https://github.com/omacom/omarchy/blob/28ceaae70ebac3a0edcc21f2faa77a90dc6d404c/shell/plugins/notifications/Service.qml)
would also need one explicit owner for `org.freedesktop.Notifications`; two
servers cannot both own the same name. The pinned
[`video-background-test.sh`](https://github.com/omacom/omarchy/blob/28ceaae70ebac3a0edcc21f2faa77a90dc6d404c/test/shell.d/video-background-test.sh)
explicitly checks that selected background/lock QML do **not** import
`QtMultimedia`, so it would be wrong to treat that theme's video path as proof
that Qt Multimedia works here. A *new* Qt Quick media app needs its own
[Qt Multimedia](https://doc.qt.io/qt-6/videooverview.html) closure, decoder,
audio routing, Wayland pixels, and measurement.
[Qt Multimedia's backend notes](https://doc.qt.io/qt-6/qtmultimedia-index.html#target-platform-and-backend-notes)
name FFmpeg as the usual default and GStreamer as the embedded-Linux/Boot2Qt
alternative; the installed Nix backend and decoder closure are unverified and
must be inspected.
Touch handlers can draw and receive events in principle, but the shell's
edge-gesture arbitration and physical keyboard ownership remain compositor
responsibilities. [Qt Virtual Keyboard](https://doc.qt.io/qt-6/qtvirtualkeyboard-overview.html)
is a separate optional stack, not automatic support for the existing shell
keyboard/input-method route.

## Bounded preflight after the reserved build/board slot is free

1. Add an **opt-in**, pinned Qt 6 target derivation for a minimal C++
   `QQmlApplicationEngine` Wayland client using only Qt Base, Declarative and
   Wayland. QML shows colored rectangles, labeled image/text, a bounded
   `Flickable`, tap feedback, and one interruptible position/opacity animation;
   no Controls, effects, Multimedia, Quickshell, or required GPU rendering
   context. Inspect the actual Qt closure for incidental graphics libraries
   rather than promising none. Record Nix
   source revision, closure (`nix path-info -rsS <out>`), Qt configure summary,
   QML JIT mode, binary/library paths, and cross-build failures. Planned build
   command once an output is added: `nix build .#qtquick-software-probe --max-jobs 1 --cores 4 --no-link --print-out-paths`.
   **That output does not exist now; the command is a proposed gate.**
2. With the board operator's exclusive lock and a reversible normal-service
   trial, launch this client in the existing Sway session with
   `QT_QPA_PLATFORM=wayland QT_QUICK_BACKEND=software QSG_INFO=1` and the
   session's actual `XDG_RUNTIME_DIR`/`WAYLAND_DISPLAY`. Retain backend/QPA
   logs, `wayland-info` advertised protocols, buffer type/format where
   observable, a native capture *and* a panel photo, physical tap/flick and
   keyboard-focus result, service identity, exact store paths and restoration.
   Stop on missing pixels, wrong renderer, focus capture, or failed recovery.
   Do not run this during the current RVV build/board reservation.
3. Compare cold launch to first visible frame, steady and peak PSS/RSS from
   `/proc/<pid>/smaps_rollup`, client **and Sway** process CPU, p95 update/
   presentation/input timing, and loss of card-gesture responsiveness against
   an equivalent simple SHM client and the normal card workload. Capture
   measurement method and repeated runs; no performance threshold can be
   claimed from this note. Test software effects as an explicit negative
   control so omitted effects are visible in evidence.
4. Only if that passes, cross-build a **pinned minimal Quickshell** config with
   one plain layer-shell panel (`SCREENCOPY=OFF`, X11/Hyprland integration
   off), run it alongside Sway, and repeat protocol, pixels, focus, memory,
   launch and frame tests. An Omarchy-like theme is a later, separate port
   requiring software-safe effect substitutes, Sway-specific routing, and
   notification ownership. If either closure is too large, fails cross-build,
   misses touch/focus, or materially worsens combined frame CPU, stop there.

No experiment above was performed for this research note. It does not tick a
physical OpenSpec task or justify a new compositor, Qt shell dependency, or
claim about Quickshell performance on the K230.
