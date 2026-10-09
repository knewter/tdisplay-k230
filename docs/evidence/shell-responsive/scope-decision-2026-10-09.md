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

Planning validation: `openspec validate the-shell-adapts-to-output-resolution
--strict`, `openspec validate the-hdmi-shell-works-in-landscape --strict`,
`openspec validate --all --strict`, and `git diff --check` must pass before
handoff. The published work board is built with `python3 scripts/build_site.py`;
CI and Pages publication are checked against the landed revision. The change
stays open until its required physical proof is committed.
