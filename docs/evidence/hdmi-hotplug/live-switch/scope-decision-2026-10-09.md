# HDMI final scope decision — 2026-10-09

Evidence class: explicit operator scope decision, linked to existing physical
acceptance and installed-artifact proof. No new board action or test is implied.

The operator directed:

> we dont need a settings button to reboot into hdmi now that hot swap works and yeah we want landscape layout support as a new proposal and land hdmi

## Canceled scope

Original tasks 3.1 (selector/controller and restore), 3.2 (confirmed Settings
row/status) and 3.3 (separate forward/restore physical trial), plus the entire
manual reboot/self-revert requirement, are dropped. None is marked passed.
The historical prototype `58498320` is parked and removed from active source;
the successor draft `6b0ad37555381bc97e78c904fb90f5726d67c6dd` is rejected and
never merged to master. Automatic switching supersedes that proposed UI.
No guarantee of recovery from a failure before Linux restoration is published.

## Preserved landscape scope

Original tasks 5.1–5.4 transfer to `the-hdmi-shell-works-in-landscape`, landed
before this archive (proposal integration `a9d355ad`). All four implementation
and physical gates remain unchecked:

| Original task | Successor task and remaining requirement |
| --- | --- |
| 5.1 | 5.1: supported landscape HDMI mode/normal transform and exclusive outputs; automatic switching replaces the canceled reboot premise. Original vendor toplevel command remains, with the shipping mainline bundle check added. |
| 5.2 | 5.2: actual-geometry scaling audit including Wi-Fi, preserving portrait behavior; original Cargo test/Clippy proof. |
| 5.3 | 5.3: usable Home/navigation without overlaps or unreachable controls, landscape and portrait fixtures; original Cargo proof. |
| 5.4 | 5.4: separate physical landscape Home/Settings observations and matching native captures. Operator waived a monitor photograph; portrait acceptance does not prove landscape. |

Shared configure/reflow/hit-test implementation remains owned by
`the-shell-adapts-to-output-resolution`; these HDMI integration gates do not
silently complete its density, Wi-Fi/theme, dock or physical follow-ups.

## Completed scope and limits

All 17 retained HDMI tasks are complete with their existing committed evidence
or explicit operator timing deferral. `closeout-2026-10-09.md` records acceptance,
precise timing limits and the exact normal installed tuple. Historical
probe-touch and vendor-only qualification UNVERIFIED markers remain, without
claiming those omitted sequences occurred. Host builds, volatile physical
trial, normal installation/autoboot and built image remain distinct proof.
No additional deployment or physical verification is required for automatic
switching; landscape implementation and board qualification remain open in
its successor. Precise timing is deferred, not an archive gate.

## Integration

Worktree `/home/jadams/tmp/k230-hdmi-close-final`, branch
`closeout/hdmi-accepted-2026-10-09`, original base `ba5217ca`, archive integration
base `a9d355ad`. Owned paths: HDMI planning/archive and evidence, its work-board
entry and necessary dependency references, responsive proposal references to
its moved scope, and CLI-generated `display/hdmi` / `display/touch` specs.
No source changes, build slot or board/serial reservation.

Validation and sync proof will be recorded in `archive-check-2026-10-09.json`.
The CLI, rather than manual main-spec edits, merges four HDMI requirements,
adds the shared-pin touch requirement and updates the existing trackpad
requirement while preserving the other touch requirements.

Landscape proposal ownership: worktree
`/home/jadams/tmp/k230-hdmi-landscape-successor`, branch
`proposal/hdmi-landscape-successor-2026-10-09`, original base `ba5217ca`,
integration base `a55e5a55`. Owned paths are only that proposal directory;
no build or board reservation. Local worktree paths are kept in this evidence
rather than the public planning document, satisfying site validation.
