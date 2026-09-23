# Handheld UX evidence review

Reviewed 2026-09-23 on host against committed reports and captures. This is an
inventory, not a new board trial. A native compositor PNG proves the composed
pixels; injected input proves routing on the board; camera and real-finger
records provide the narrower physical observations named below.

| ID | Surface | Evidence class | Citation | What it proves | Open gate |
| --- | --- | --- | --- | --- | --- |
| E-BOOT | Boot handoff | camera, native | `docs/evidence/splash-initial-scene-ready/video-audit.md` | A visible first Sway scene follows the preserved splash in the recorded trial. | Cold USB-powered timing and optical continuity remain `UNVERIFIED`. |
| E-BAR | Persistent controls | native, injected | `docs/evidence/launcher-gestures/integrated-injected/README.md` | Apps, Windows, Keyboard, and System remain visible while the launcher is open. | Full real-finger reachability for every bar action is `UNVERIFIED`. |
| E-APPS | Catalog and Help | native, injected | `docs/evidence/offline-wifi-image/README.md` | Fresh-image desktop catalog, Help pagination, nano, and nnn were reached through production launcher cards. | These new cards lack focused real-finger/readability evidence. |
| E-KEY | Keyboard | camera, real-finger, native | `docs/evidence/shell-real-touch-keyboard/README.md` | A user showed the keyboard and entered the asymmetric `1qazoplm` sequence; native states corroborate shown/hidden composition. | A deliberate full-panel drag and uniform optical sharpness remain `UNVERIFIED`. |
| E-WINDOWS | Overview and selection | injected, native, real-finger | `docs/evidence/launcher-gestures/real-finger/README.md` | A user paged, opened window cards, selected Monitor, reopened Apps, and returned from overview. | Exact motion coordinates and full-screen sharpness remain `UNVERIFIED`. |
| E-HOME | Application recovery | real-finger operator report | `docs/evidence/shell-real-touch-apps/README.md` | The user explicitly confirmed Home recovery after the Apps/Windows/exit sequence. | The camera does not make every menu label legible. |
| E-SYSTEM | System confirmation and recovery | camera, real-finger, serial, native | `docs/evidence/shell-real-touch-system/README.md` | A touch-triggered reboot returned to shell with host cables attached. | Standalone power-on remains outside this evidence. |
| E-MOTION | Launcher paging budget | injected, native | `docs/evidence/launcher-gestures/integrated-injected/README.md` | The named injected matrix recorded 41 settled transitions under 200 ms release-to-submit. | It is not panel scanout, touch latency, or a real-finger latency claim. |
| E-VIDEO | Stop, Home, EOF recovery | injected | `docs/evidence/network-video/installed-controls/README.md` | Production video control sessions cleaned their processes/state for Stop, Home, and EOF. | Network failure and optical playback experience remain separate. |

## Review notes

The captured native Apps frame shows a 568×1232 portrait composition with a
56px control bar, a title and page state, three large cards, and three footer
actions. The keyboard-visible native frame preserves the control bar and
narrows the launcher viewport above the keyboard. The physical Apps still
shows the same hierarchy, but glare, an oblique camera angle, and finger
occlusion make it unsuitable as proof of uniform small-label readability.
These observations are reflected in the contract rather than treated as a
visual defect proved on all of the glass.

The comparison lens is deliberately narrow. Palm webOS guidance emphasizes
fast, direct interaction, visible common commands, and avoiding needless modal
blocks; it is a design reference, not a compatibility target. See
[references](references.md).
