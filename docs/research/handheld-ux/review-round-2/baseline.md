# UX review baseline — 2026-10-01

This is a host-side evidence inventory for the second handheld UX review. It
separates observations from proposals and physical acceptance. The baseline is
the persistent coherent system and Rust shell identified in
[`coherent-ordinary-boot`](../../../evidence/boot-verification/coherent-ordinary-boot/README.md):
system `/nix/store/p1a1hz9n8s4g8qyr55ffl3dzbnjgqwr8-nixos-system-nixos-26.11.20260919.20b1ddd`,
Rust client `/nix/store/3hy6h165ii649z6vjzjd36jwg16d37rc-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust`,
and source `5bb67db128210f830dab4de0d20a4b0eca13c578`. The ordinary reboot,
active appearance restoration, and saved native Home capture are documented
there. The camera frame is partial; `real_finger_verified` is false.

| Journey/surface | Baseline artifact and what it establishes | Still unknown / evidence class |
| --- | --- | --- |
| First usable Home | [ordinary-boot Home](../../../evidence/boot-verification/coherent-ordinary-boot/home.png), native capture after ordinary reboot of the pinned candidate; current Home hierarchy, actual desktop icons, wallpaper and dock. | Full-panel optical legibility is limited by the partial/out-of-frame camera photo. This does not re-run first-use boot timing or finger reach. |
| Apps discovery | [authored dark drawer](../../../evidence/shell-polish/after/dark-drawer.png) and [light drawer](../../../evidence/shell-polish/after/light-drawer.png), host Cairo/Pango production-path renders. Current icon-led 4-column catalog has search and two rows. | Host fixtures are not board state; overflow, scrolling, search filtering and real-finger label readability are not established by these images. |
| Open/repeat app | [Exact-candidate operator report](../../../evidence/boot-verification/coherent-manual-candidate/operator-navigation.json) accepts Home→All apps, bottom handle→Overview, and Terminal open/return by real finger on the exact `p1a1hz` system + `3hy6` Rust source. The report is tied to a temporary matching-kernel boot. A later [ordinary reboot](../../../evidence/boot-verification/coherent-ordinary-boot/README.md) returned to the same source/system and captured Home. | These three accepted interactions are reusable because source and interaction contract are unchanged; ordinary reboot did not repeat their gestures. Other Home edits, full journeys, and all other finger/optical claims remain open. |
| Settings and appearance | [Settings volume layout board evidence](../../../evidence/shell-polish/settings-volume-layout/board/README.md) records dark/light native captures and injected control of the actual slider/picker on source `5bb67db128210f830dab4de0d20a4b0eca13c578`. | Injected input is not finger acceptance; no headphone/acoustic output review. Picker placement overlaps adjacent rows in the captured state. |
| Cards/window switching | [Home navigation overview](../../../evidence/home-screen/navigation/overview.png) is prior board evidence on source `f39cb7eb`. | Current-source deck screenshot/optical comparison is absent. Current visual treatment and gesture quality remain `UNVERIFIED`; do not treat prior card screenshots as this baseline. |
| Keyboard visible | [installed keyboard capture](../../../evidence/keyboard-gestures/supervised-installed/keyboard-shown.png) is a native capture on source `dcfbdb0b`, shown by command. The 400px keyboard and handle are visible. | Not the baseline source; no injected or real-finger gesture in that trial, no disconnection/reconnection test, and Home/Back reachability while typing is not demonstrated by that frame. |
| Notifications/shade | [dark shade](../../../evidence/shell-polish/after/dark-shade.png) and light counterpart are host production-path renders with synthetic notices. | No latest-source settled board shade capture or privacy/real-notification review in this evidence set. |
| Theme picker | [theme host render](../../../evidence/shell-polish/after/dark-themes.png), plus the theme-picker evidence referenced by its change. | These host frames do not establish latest integrated board load/latency, physical selection, or optical readability. |
| Media, Help, System and recovery states | Existing journeys and evidence are indexed in the [flow matrix](../flow-matrix.md) and [evidence review](../evidence-review.md). | The baseline review did not repeat these interactions. Their cited evidence has its own source, date and gate; empty/loading/stale/error/denied states are not all visible in the current captures. |

The review concerns design and evidence quality. It does not change the
Omarchy theme, wallpaper, or icon inventory. Production renders, board-native
captures, camera images, injected input, and finger input remain distinct
evidence classes. See [`rubric.md`](rubric.md) before treating a gap as a
product defect.

## Journey inventory cross-check

The archived [flow matrix](../flow-matrix.md) was checked row by row against
the change design’s required coverage. It supplies each journey’s starting
state, action, expected result, escape route, owner, evidence class and existing
gate. This review adds the reviewed artifact/source and current unknowns above
and below; it does not claim to execute the matrix again.

| Required journey | Matrix row and current review record | Current-source status |
| --- | --- | --- |
| First usable USB-powered boot | `First use`; ordinary reboot Home evidence in this baseline. | The Home state is current-source; cold first-use/USB timing is not observed in this review. |
| Discover and launch an app | `Discovery` / `Repeat use`; current Home + host drawer; prior navigation report. | Drawer search/launch not freshly executed on current source. |
| Type with keyboard | `Keyboard-visible`; prior native shown frame and service recovery report. | Display is older-source, command-revealed; typing/tracking/reach remains `UNVERIFIED`. |
| Enter, switch and return from cards | `Window overview` / `Card shell`; older injected board report and current-source capture gap. | Latest current-source card path `UNVERIFIED`. |
| Close/refusal | `Card shell` recovery contract and card owner’s refusal evidence. | Current integrated refusal/close journey not rechecked; see [journey review](journey-review.md). |
| Use/stop media | `Video`; existing injected Stop/Home/EOF report. | Reused as a prior evidence pointer only; no new media interaction here. |
| Reach Home, Help and System | `First use`, `Discovery`, `System`; existing Home, catalog and System reports. | Latest Home capture exists; Help/System current-source walkthrough not performed here. |
| Empty/loading/stale/error/denied | State inventory in flow matrix and linked edge-state evidence. | No new full state matrix run; preserve each named state’s own source/gate. Keyboard-visible variants remain unknown unless specifically captured. |

This makes the absent states reviewable instead of replacing them with
illustrative screens. For source-specific actions and expected results, follow
the linked row in the matrix; for what this review did and did not observe,
see [`journey-review.md`](journey-review.md).
