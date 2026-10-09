# Responsive follow-up scope decision — 2026-10-09

Operator instruction: "you can move those into the landscape proposal".
This follows the closeout audit identifying three unimplemented follow-ups.
It authorizes their scope transfer, not physical acceptance or an archive.

| Original responsive task | Landscape successor task | Preserved requirement |
| --- | --- | --- |
| 6.3 | 7.1 | Implement actual Home/Drawer icon and text density scaling beyond column-count reflow. |
| 6.4 | 7.2 | Implement Wi-Fi/theme reflow or uniform centered scaling instead of independent non-uniform scaling. |
| 6.5 | 7.3 | Decide whether/how the four-slot Home dock should reflow from actual layout and hit-target evidence. |

The successor's preservation is committed at `67b6c55a` on
`proposal/hdmi-landscape-successor-2026-10-09` and landed on master before
removing these duplicate open tasks from the responsive proposal. All three
remain unchecked in the successor. The dock's current four-slot implementation
is explicit in `nix/rust-shell-client/src/home_grid.rs:19`; the responsive delta
no longer claims the dock column count already reflows.

Responsive tasks 6.1/6.2 remain unchecked: matching whole-output configure and
native capture plus the operator's filled-Home observation, followed by actual
Home, Drawer and Settings target activation. The earlier photo waiver remains
in force. This planning change obtains no new board, camera, injected-event,
QEMU or host-render evidence and does not alter the installed runtime.

Ownership: worktree `/home/jadams/tmp/k230-responsive-close-final`, branch
`closeout/responsive-output-2026-10-09`, initial base
`88655ee0da98cd53988142af2106d721cef7b5f7`, reconciled after landscape preservation
`67b6c55a`. Owned paths are this proposal directory, this evidence file and the
two related entries in `docs/work-board-status.json`. No build slot or board
reservation is taken.

Validation on 2026-10-09 at source revision
`b7e6eee69b1e6a5e04d7efcc76e25d0fb1546621`:

- `openspec validate the-shell-adapts-to-output-resolution --strict`: passed.
- `openspec validate the-hdmi-shell-works-in-landscape --strict`: passed.
- `openspec validate --all --strict`: 55 passed, zero failed.
- `git diff --check`: passed.
- `python3 scripts/build_site.py`: passed, 669 pages, 17,800,997 bytes,
  82.45 seconds against 32 MiB / 120 second limits; included Markdown links,
  committed work-board rendering, blob accounting and output assertions.
- Task reconciliation: responsive has 17 completed tasks and only 6.1/6.2
  unchecked; landscape has one planning task completed and seven unchecked,
  including transferred 7.1–7.3. No unperformed task was marked complete.

Review and local validation are complete. Merge/push and exact-revision Pages
publication are checked at handoff. No image deployment is needed for this
planning change. The proposals stay open until their required implementation
and physical proof are committed. Operator check for responsive 6.1/6.2: on
HDMI, open Home and confirm it fills the display; activate a Home app icon,
an All Apps icon and a Settings row, each selecting the intended target.
Matching native capture/configure evidence must accompany those observations.
