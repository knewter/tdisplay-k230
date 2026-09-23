# Work status and next steps

Reconciled 2026-09-22 (America/Chicago). `master` is the integration branch;
`origin/master` and its successful Spec site run establish publication. Source
landing, image installation, and physical acceptance are separate milestones.
Use `python3 tools/work-status.py` for the current local inventory; it reports
cached remote state and never fetches or changes Git. Fetch separately before
claiming a branch is current with the server.

## Done and landed

- Source-built boot chain and NixOS image, working display/touch, Sway shell,
  keyboard, desktop-entry app launcher, window/system controls, and offline
  apps/Help. Foot, htop and Neofetch defaults are repository/image settings.
- Wi-Fi connectivity and persistent reconnection across reboot, with private
  runtime credentials outside Git and the Nix store. See
  [Wi-Fi evidence](evidence/wifi-persistent/README.md).
- U-Boot USB mass-storage flashing: repeatedly used to write images without
  removing the card. The U-Boot host/gadget coexistence evidence is in
  [USB validation](evidence/usb-host-validation.md). The operator reconfirmed
  normal flashing works during this reconciliation. No new flash or routine
  readback was needed. Untested BootROM recovery is a separate proposal.
- Second-core readiness investigation, now archived. The live OpenSBI/DT/Linux
  handoff exposes one hart; Linux still has one CPU online. The
  [decision and prerequisites](evidence/second-core/README.md) explain why
  enabling another CPU is not a device-tree checkbox.
- Bounded software/MVX streaming experiments and
  [presentation measurements](evidence/network-video/README.md): about 29.96
  and 29.74 unique presentation events/second over more than 30 seconds,
  respectively. These are instrumented compositor feedback, not optical
  proof of perfect frame cadence or a completed player application.
- [GPU validation](evidence/gpu-validation/README.md), now complete and archived:
  RGB565 layout, a premultiplied-alpha sample, private DRM buffer export/import,
  and three-round timing passed. The full-panel probe used about 94% less process
  CPU but 11% more elapsed time than Pixman. This supports an opt-in renderer
  experiment; the current Sway renderer remains Pixman.
- [Cards and gestures planning](../openspec/changes/touch-launcher-gestures-overview/proposal.md),
  implementation now includes bounded transitions and window metadata, with physical acceptance still open.

## Almost done or actively underway

| Work | Already available | Remaining acceptance |
| --- | --- | --- |
| Network video | Pinned software player, Apps entry, reviewed lifecycle controller, measured probe paths and presentation tracing | Flash the integrated image; prove fallback, Stop/Home, EOF/error cleanup, final playback and cropped evidence |
| Cards and gestures | Host-tested swipe classification, animated paging, async metadata cards, stale focus handling and rollback | Integrated-image injected matrix, resource measurements and focused real-finger capture |
| Boot splash | Source-built U-Boot splash and opt-in kernel/compositor preservation, warm-boot and first-modeset evidence | Calibrated geometry, remaining power-on/second-card procedure, final default and specification acceptance |

The player and gesture implementations have passed host review and cross-builds.
The video controller owns player descendants through startup, Stop, EOF and
fallback; healthy playback has no arbitrary duration cutoff. Host tests cover
startup/fallback cancellation, private runtime input and process cleanup. Those
checks do not replace the final-image physical tests above.

A preliminary transferred launcher ran on the existing board image and visibly
paged Apps and opened a two-window overview. Its two transitions submitted final
frames after 137 and 152 ms. This small preflight is not the 20-swipe matrix,
resource comparison, final-image acceptance or real-finger proof.

The FFmpeg empty-capture candidate is committed as an **unapplied** patch for
review. [The timestamp investigation](research/mvx-timestamps.md) retains the
boundary trace and next experiment. No general timestamp fix is claimed until
timestamp association is correct. The patched FFmpeg completes repeated decode/EOF trials but still propagates duplicate MVX capture timestamps; it remains diagnostic-only.

## Planned, not implemented

- `the-shell-trials-vglite-composition`: opt-in actual Sway/wlroots renderer trial, with whole-pass Pixman fallback and explicit board acceptance gates; proposal only.
- `characterise-bootrom-usb-recovery`: no-card/SW3 entry and conditional vendor
  recovery-tool proof. This is independent of working U-Boot USB flashing.
- `the-boot-shows-a-computational-game-of-life`: computational animation and
  handoff, after the static splash boundary is accepted.
- [Latest U-Boot](research/latest-uboot-feasibility.md) is landed feasibility
  research, not a completed upgrade or an implementation proposal.

## Proposal coverage and parallel work

The active proposals cover network video, touch gestures/window overview, the
VG-Lite compositor trial, remaining static splash acceptance, computational boot
Game of Life, and BootROM USB recovery. The GPU validation is already archived.
Latest U-Boot and further second-core enablement have research records but no
active implementation proposals; their next bounded implementation scope still
needs a proposal before execution.

Network video and touch gestures are the current independent implementation
tracks. The compositor trial is a third possible track, initially restricted to
host work in its own worktree. The coordinator owns shared shell/Nix integration
and serializes all board sessions. Static splash work can proceed separately at
the source level but its physical tests share the same board. Game of Life
acceptance depends on static splash acceptance. BootROM recovery is lower
priority and is unrelated to already-working U-Boot USB flashing.

## Next execution order

1. Finish usable network video. Decoder work and host lifecycle fixes can run
   in parallel; one coordinator owns final board tests and image integration.
2. Implement the proposed `the-shell-trials-vglite-composition` as a separate opt-in compositor experiment when scheduled;
   process-CPU offload is promising, but elapsed time did not improve and
   complete buffer/synchronization/color/scanout gates remain.
3. Start cards/gestures implementation independently of decoder work if desired.
   It does not require a GPU renderer or a second Linux CPU.
4. Return to static splash acceptance before the boot animation. Investigate
   second-core firmware/coherency prerequisites in parallel as source research;
   do not release/reset a core on assumptions.

## Reconciliation record

The first reconciliation batch was pushed as `2bb0ca9`. Its
[Spec site run](https://github.com/knewter/tdisplay-k230/actions/runs/35813460508)
passed. Follow-up commits carry the USB archive/successor, this status report,
and the read-only worktree report. Their deployment must be checked separately.

Historical branch comparison uses `git log --cherry-pick --right-only` plus
current file/evidence review; a non-ancestor commit is not necessarily missing.
The old Wi-Fi, offline apps, launcher, Neofetch, U-Boot research, GPU and
second-core work is represented by merged/cherry-picked successors. Notable
nonidentical historical patches were reconciled as follows:

| Historical work | Current disposition |
| --- | --- |
| U-Boot logo port `64a0c3e` | Revised port on master at `a4ce291`, with subsequent bounded-load fixes |
| Firewall experiment chain | Repository-managed kernel fragment and evidence landed at `3797e1a` |
| `e0aeb27` splash task update | Task 4.2 is already complete in the current splash proposal |
| Diagnostic preserve/initial-Sway splash branches | Opt-in integrated implementation and evidence at `61dcc90`; old diagnostic image settings are not daily defaults |
| Initial handheld site `020dad7` | Replaced by current page and cropped media; the old draft contains a placeholder media revision |
| MVX audit on `shell-usability` | Current firmware inventory and V4L2 audit supersede the earlier draft |
| Original video proposal `613f4ab` | Same scope now maintained with measured progress on master; do not overwrite it with the stale all-unchecked copy |
| Video lifecycle `d955a7d` | Superseded by the reviewed Python controller with startup/fallback cancellation and descendant cleanup; final-image physical acceptance remains open |

Old worktrees are retained during reconciliation; none were reset, swept into
commits, or deleted merely because a patch looked similar. Clean integrated
worktrees can be removed after confirming they contain no unique evidence or
running build. The workflow in [AGENTS.md](../AGENTS.md) requires early proposal
publication, concrete handoffs, prompt integration, and verification of the
pushed revision's CI/deployment. No archive may turn an unperformed test into a
completed task.
