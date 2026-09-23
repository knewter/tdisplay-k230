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
  ready for implementation with existing controls preserved.

## Almost done or actively underway

| Work | Already available | Remaining acceptance |
| --- | --- | --- |
| Network video | Pinned probe, measured software and MVX paths, presentation tracing, empty-capture diagnosis | Repair/review lifecycle implementation; integrate Apps and image; prove fallback, Stop/Home, EOF/error cleanup, final image and cropped evidence |
| Boot splash | Source-built U-Boot splash and opt-in kernel/compositor preservation, warm-boot and first-modeset evidence | Calibrated geometry, remaining power-on/second-card procedure, final default and specification acceptance |

The player implementation is preserved on remote branch
[`impl/video-lifecycle`](https://github.com/knewter/tdisplay-k230/tree/impl/video-lifecycle)
and in `/tmp/k230-video-lifecycle`. It is **not on master** at this checkpoint.
Review found an arbitrary 90-second healthy-playback cutoff and a controller
signal path that can leave its watchdog alive. Host fake-player tests do not
settle those issues or establish physical image acceptance.

The FFmpeg empty-capture candidate is committed as an **unapplied** patch for
review. [The timestamp investigation](research/mvx-timestamps.md) retains the
boundary trace and next experiment. No general timestamp fix is claimed until
patched decoding, timestamps and EOF are physically verified.

## Planned, not implemented

- `touch-launcher-gestures-overview`: client-side swipe paging and window cards;
  metadata-only overview first, preserving the current keyboard and buttons.
- `characterise-bootrom-usb-recovery`: no-card/SW3 entry and conditional vendor
  recovery-tool proof. This is independent of working U-Boot USB flashing.
- `the-boot-shows-a-computational-game-of-life`: computational animation and
  handoff, after the static splash boundary is accepted.
- [Latest U-Boot](research/latest-uboot-feasibility.md) is landed feasibility
  research, not a completed upgrade or an implementation proposal.

## Next execution order

1. Finish usable network video. Decoder work and host lifecycle fixes can run
   in parallel; one coordinator owns final board tests and image integration.
2. Use the completed GPU validation to plan a bounded compositor experiment;
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
| Video lifecycle `d955a7d` | Unfinished remote branch with explicit review issues above |

Old worktrees are retained during reconciliation; none were reset, swept into
commits, or deleted merely because a patch looked similar. Clean integrated
worktrees can be removed after confirming they contain no unique evidence or
running build. The workflow in [AGENTS.md](../AGENTS.md) requires early proposal
publication, concrete handoffs, prompt integration, and verification of the
pushed revision's CI/deployment. No archive may turn an unperformed test into a
completed task.
