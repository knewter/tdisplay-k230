# Omarchy theme compatibility — completed parent scope

This report describes the accepted static-theme parent, including the consumer
implementation at `3a1a3e51`. It combines existing host, QEMU and board evidence
with the operator's explicit acceptance and waiver. Those evidence classes remain
distinct. It does not claim every arbitrary community theme or desktop feature
works, or that an unperformed camera/benchmark trial passed.

## Complete compatibility matrix

The generated [102-field inventory](token-adaptation-inventory.md) is the
field-by-field authority for all 13 active sections in the pinned shell
 template. `tools/theme_field_inventory.py` regenerates it and
`python3 tests/test_handheld_theme_rendering.py` rejects unclassified fields.
Unknown extensions are preserved and identified by the generation report;
they are not silently promoted to supported controls.

| Input or behavior | Disposition and evidence |
| --- | --- |
| Unchanged repository/collection sources | Applied: direct roots, built-in collections, `.git` directories/files and no-Git sources; generated output stays outside the source. [Source fixtures](source-fixtures.md), [activation tests](consumer-closeout-2026-10-10/host-results.json). |
| Palette aliases, explicit semantic/ANSI/selection/custom values, mode precedence, derived mixes/gradients | Applied: pinned upstream helper behavior, including full-file then section replacement and last machine overrides. [Helper parity](helper-package.md), [native token checkpoint](native-token-checkpoint.md). Labels use a brush's first stop; applicable painted fills/borders preserve full stops and authored alpha. |
| Shell colors and corresponding surface overrides | Applied or explicitly adapted/unavailable in the [field inventory](token-adaptation-inventory.md). Hover/focus have real pointer/editing state owners; idle outlines and persistent launcher selection remain deliberately omitted. [Completed consumer proof](consumer-closeout-2026-10-10/README.md). |
| Typography and spacing | Adapted: bounded 0.8–1.25 visual factors in Rust and C; spacing optionally follows base font. Settings/caption role limits and small-label floors remain. Text insets, label/icon gaps and widget padding change; fixed touch/grid/panel/gesture geometry does not. Long labels retain end ellipsis. [Six reviewed host capture pairs](consumer-closeout-2026-10-10/README.md). |
| Launcher/menu/image-picker scrims | Applied: full authored brush stops/alpha. Adapted carousel side-slice dimming multiplies the brush alpha by its blend; centred imagery remains undimmed. [Pixel tests](consumer-closeout-2026-10-10/rust-lib.log). |
| Icons | Applied: installed freedesktop inheritance and generation invalidation; adapted fallback to recognizable icon/text when dependencies are missing. [Bundled icons](bundled-icons.md), [real drawer/card tests and captures](drawer-card-generation/README.md). |
| Built-in collection | Applied: all 22 pinned palettes resolve. Catppuccin and Catppuccin Latte assets remain byte-identical. Other 20 built-ins use bounded build-time background derivatives, with source palettes/selectors/preview bytes preserved. [Bundle provenance](../../../nix/handheld-theme-default/SOURCE.md), [background/default proof](bundled-backgrounds-host.md). |
| Static background/preview/carousel selection | Applied: source imagery, preview/first-background fallback, bounded lazy decode, touch carousel, crop-only static rendering and per-theme wallpaper memory. [Preview source tests](theme-preview-host/README.md), [background selection](../theme-picker/background-selection/README.md), [wallpaper memory](wallpaper-memory-host.md). Empty/removed assets retain recovery/fallback. |
| Coordinated activation and failure recovery | Applied: validated two-receiver prepare/commit, generation ordering, rollback and cache invalidation. [27 current transaction cases](consumer-closeout-2026-10-10/transaction.log), [native dark/light activation](board-switching/README.md), [unchanged community activation](community-board-fixed/README.md). |
| Preview/cancel/apply and chooser behavior | Applied in the existing chooser/runtime; exact operator acceptance and superseded additional recording requests are preserved in [accepted closeout](accepted-closeout-2026-10-10/README.md). No new per-class finger video is claimed. |
| Startup/reboot | Applied policy: valid selected cached generation/wallpaper survives a removed source; no saved valid state uses the pinned default. [Corrected reboot-v2 protocol and host checks](accepted-closeout-2026-10-10/README.md). Individual removed-source/fresh-HOME physical boot cases remain UNVERIFIED. |
| Keyboard and installed app adapters | Applied or limited by each app: keyboard seven color flags with supervised visibility-preserving restart; Foot/app session reload reports limitations independently. [Keyboard](keyboard-appearance-host.md), [app adapters](app-appearance-host.md). No automatic termination of running work is promised. |
| Bar, tooltip, lock, polkit, desktop Hyprland, RGB keyboard, absent desktop apps/hooks | Unavailable with a named absent surface/hardware/app reason. Source is preserved; theme code is not executed. [Research/asset inventory](../../research/omarchy-quattro-theme-compatibility.md), [field inventory](token-adaptation-inventory.md). |
| Settings/notifications full adapters | Moved by the authorized September 28 split into `the-settings-and-notifications-surfaces-are-themed`; its own accepted capability/evidence remains independent. Parent Rust Settings control painting is covered here. |
| Non-crop fit modes, user overlays and video | Moved by that same authorized split into `the-background-chooser-supports-fill-solid-and-video`; its outstanding tasks remain independent. Closing this static parent does not close video work. |

## Attribution and source identities

The implementation reuses `omacom/omarchy` at
`28ceaae70ebac3a0edcc21f2faa77a90dc6d404c` (inspected Quattro snapshot).
Four helpers and 19 templates are retained with repository MIT license and
original file hashes in [helper SOURCE.md](../../../nix/omarchy-theme-tools/SOURCE.md)
and [SHA256SUMS.upstream](../../../nix/omarchy-theme-tools/SHA256SUMS.upstream).
The only helper path patch permits isolated staging; parity tests retain the
original behavior. The [built-in SOURCE.md](../../../nix/handheld-theme-default/SOURCE.md)
names all 22 themes, exact fetched-source hash, byte-identical dark/light tree
digests, background derivative operation and packaged repository LICENSE.

The unchanged community fixture is Fuchsblau at
`aa7fde043ae60603c3ecc6fd6ac3b6674cacab04`, tree SHA-256
`f72ece7c9eead4fb049ebead18d918b4b11be6f35dcc861b8862e5c8f0693e75`.
[Fixture provenance](source-fixtures.md) records its repository MIT license hash
and built-in source/license hashes. Community fixture checkouts are not included
in the normal image. Repository licenses are identified; individual third-party
wallpaper/art rights are **UNVERIFIED**, as retained in the original provenance.
This is attribution and an explicit license boundary, not a blanket asset-level
license assurance. No new upstream art or community repository is redistributed
by this closeout. Newly committed captures are production host renders of the
already packaged default, with source/capture hashes recorded.

## Completion and limits

Actual board evidence already shows built-in dark/light and unchanged community
activation and native images. Existing QEMU drawer/card captures and host pairs
prove their named rendering classes only. The operator accepted implemented
behavior and waived additional physical recording, static workload/latency
collection and individual reboot/full-fresh-HOME collection. Original requests
and acceptance statements remain committed in
[accepted-closeout-2026-10-10](accepted-closeout-2026-10-10/README.md).

Static CPU/RSS/decode/card-budget measurements, individual per-class finger
recordings, new physical typography/spacing cases, and full fresh-HOME boot
remain **UNVERIFIED**. These are waived collection, not unimplemented consumers.
The source consumer work, cross-build and published revision are reported
separately; a successful build alone is not board installation proof.
