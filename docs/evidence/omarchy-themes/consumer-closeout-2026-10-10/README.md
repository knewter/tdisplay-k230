# Applicable theme consumers completed — 2026-10-10

The generated appearance now reaches actual mouse hover, existing focused text
fields, ordinary shell typography, bounded visual spacing, and overlay scrims.
The [102-field compatibility inventory](../token-adaptation-inventory.md) names
an actual consumer and reason for every field. This supersedes the implementation
gaps recorded in the October 2 partial font/spacing checkpoint.

The real Rust renderer and C appearance receiver passed 497 host test cases:
436 Rust library, 13 C receiver, 7 rendering/inventory, 14 activation and 27
transaction cases. One unrelated Rust diagnostic remains deliberately ignored.
All targets compile with `cargo check`. Commands, source hashes, UTC record time
and capture hashes are in [host-results.json](host-results.json); raw logs are
committed beside this record. The new tests verify actual painted pixels,
transformed pointer coordinates, cache invalidation without activation, focus
priority, gradient/alpha scrims, bounded metrics and C rollback/rejection.

## Reviewed production host captures

These six pairs use the pinned packaged Catppuccin report/appearance, the real
AppearanceReceiver and production RendererCache, Cairo and Pango. Service/app
fixtures are identical in each pair. The adapted fixture sets base-size 15,
caption-size 13 and spacing scale 1.25; it never edits upstream theme bytes.

| Existing surface/state | Baseline | Adapted |
| --- | --- | --- |
| Settings | [baseline](baseline.png) | [adapted](font-spacing-adapted.png) |
| Settings mouse hover | [baseline](settings-hover-baseline.png) | [adapted](settings-hover-adapted.png) |
| Drawer focused search | [baseline](drawer-focus-baseline.png) | [adapted](drawer-focus-adapted.png) |
| Home | [baseline](home-baseline.png) | [adapted](home-adapted.png) |
| Help | [baseline](help-baseline.png) | [adapted](help-adapted.png) |
| App actions | [baseline](app-menu-baseline.png) | [adapted](app-menu-adapted.png) |

Reviewed at native 568×1232: Settings rows, drawer search/labels, Home clock and
dock, Help actions and app menu remain within their existing bounds. Enlarged
long Help descriptions use the existing end ellipsis; this is a documented
fixed-layout adaptation. Captures with letter icons exercise recognizable
missing-asset fallback, not icon inheritance. Actual inherited icon evidence
remains [drawer/card generation](../drawer-card-generation/README.md).

## Adaptation and limits

Rust stores metrics on each render target, so a preview cannot alter another
renderer. Base font is expressed relative to the upstream 12 default and
bounded to 0.8–1.25; ordinary small labels retain an 11-pixel floor. Existing
Settings/caption role bounds remain. Spacing combines the explicit scale with
base font only when scale-with-font is enabled, also bounded to 0.8–1.25.
It affects visual text insets, Home/drawer label gaps, widget padding and card
header icon/text separation. Gesture zones, touch rectangles, panel dimensions
and fixed grid/row positions remain the handheld layout. C card labels use the
same bounded factor and are invalidated with the appearance generation.

Hover is driven by real Wayland pointer coordinates and never selects a tile or
activates a control. Focus belongs to existing drawer search, password and
folder-name editing states. Hover/focus retain full authored color brushes,
alpha and per-side outline widths. Ordinary idle outlines, persistent launcher
selection and shell text-range selection remain deliberately unavailable in
this accepted layout. The compatibility inventory explains each omission.
Launcher/menu scrims retain authored gradients and alpha; image-picker side
scrims multiply authored alpha by the existing carousel blend, with the centre
slice undimmed.

These are host captures, not new panel observations. The existing
[operator acceptance/waiver](../accepted-closeout-2026-10-10/README.md) applies;
additional real-finger recording and latency collection are not required.
Individual physical typography/spacing cases, static CPU/RSS/decode costs and
full fresh-HOME boot remain **UNVERIFIED**. Installation and published revision
are separate records; successful host tests do not imply deployment.

## Cross-build and publication

The source at `3a1a3e51d78f8a642677d28918fb018cad3de971` cross-built both
`handheld-shell-rust` and `card-shell` successfully under the exclusive build
lock: six changed derivations, no kernel or unchanged graphics rebuild. Exact
store outputs are in [build-result.json](build-result.json), with
[build.log](build.log) and [build-plan.log](build-plan.log). Both selected
outputs/derivation requisites and the prior verified input farm are retained
under a durable GC root; [retention.log](retention.log) records the new farm.
The build slot is released. No board or serial reservation was taken.

`python3 scripts/build_site.py` passed for committed compatibility revision
`ef55c4d7e1fd22e12890a744903c06b74ae45572`: 687 pages, 18,328,245 bytes,
58.66 seconds, inside unchanged 32 MiB/120-second budgets. The
[complete compatibility report](../compatibility-closeout-2026-10-10.md)
retains source/license attribution, captures, layout adaptations and limits.
[Publication receipt](publication.json) verifies HTTP 200 for the work board,
compatibility report and consumer evidence at landed revision
`923c6a9708a23ddbb8cff4b577cf0741c68580aa`.
[CI run 38104005765](https://github.com/knewter/tdisplay-k230/actions/runs/38104005765)
passed both build and Pages deployment.

These new packages are cross-built, not newly installed on the board. The
already installed accepted system is the separately recorded coherent-shell
candidate; no new physical consumer case is inferred. A later board deployment
must build the matching `nix build .#kernelMainlineDrmShellBootFiles` bundle,
then use the guarded stage/install workflow in
[combined-board-candidate](../../coherent-shell/combined-board-candidate-2026-10-10/README.md).
It must bind any install qualification honestly to that new candidate. This is
a separate deployment action, not a renewed request for waived recordings or a
gate on the accepted parent archive.
