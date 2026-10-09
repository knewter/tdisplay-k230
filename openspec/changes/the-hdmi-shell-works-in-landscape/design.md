## Context

Original HDMI group 5 remains unfinished. The accepted monitor uses 1280×800
with transform 90 and a touchscreen trackpad. That proves portrait HDMI,
not normal-transform landscape. Shared whole-output configure, Home/Drawer
reflow, Settings transforms and hit-testing already belong to
`the-shell-adapts-to-output-resolution`; its tasks retain density, Wi-Fi/theme
geometry, dock and physical follow-ups. This proposal does not complete them.

## Goals / Non-Goals

Qualify minimum usable Home/navigation/Settings in landscape and preserve every
original task 5.1–5.4. No full redesign, default portrait change, new hotplug driver
or replacement responsive implementation is implied by this proposal.

## Decisions

Layers: Nix/Sway output configuration and Rust/card-shell userspace geometry.
The combined runtime uses exclusive outputs on one CRTC; keep that constraint.
Use a separately selected landscape qualification profile, preserving accepted
portrait defaults until an explicit instruction changes them. Choose an actual
supported EDID mode rather than assuming the historical 720p example is selected.
Reuse responsive production paint and hit-test paths and fixtures. The original
literal/scaling audit includes Wi-Fi and must not be silently dropped merely
because a shared proposal deferred it.

## Risks / Trade-offs

Host renders establish fixture behavior only. A real monitor can expose density,
focus, input mapping and output configure differences. Preserve native captures
and operator observations as separate evidence classes. No monitor photograph
is required. Do not infer landscape interaction from accepted portrait use.

## Validation and ownership

Original commands and separate board gate are retained in tasks. Branch
`proposal/hdmi-landscape-successor-2026-10-09`, original base `ba5217ca`.
Owned paths: only this proposal directory. Worktree ownership is recorded in
the integration evidence; no build slot or board reservation is involved.

## Accepted proposal and scope decision — 2026-10-09

The operator directed: "we dont need a settings button to reboot into hdmi
now that hot swap works and yeah we want landscape layout support as a new
proposal and land hdmi". This proposal is authorized for landing as a plan.
Original HDMI tasks 5.1–5.4 transfer here; task 5.1 explicitly uses the working
automatic exclusive-output arrangement and retains its original rollback
build command, adding the shipping mainline bundle proof. All original
landscape layout and physical requirements remain open. No landscape source
implementation, new board trial or installed profile is claimed.

Proposal integration base is `a55e5a55838b150479bf97c43b7406eda7e04a05`; the
original draft base was `ba5217ca`. Only this proposal directory is owned.

## Responsive follow-up transfer — 2026-10-09

The operator authorized moving icon/text sizing, Wi-Fi/theme layout and dock
layout into this proposal: "you can move those into the landscape proposal".
Original responsive tasks 6.3–6.5 are preserved as 7.1–7.3, all unchecked.
Home/Drawer column reflow alone is not a density scale; keep the existing
portrait geometry intact while adding a deliberate actual-output sizing
policy. Wi-Fi and the theme chooser need a real reflow or uniform centered
scale, replacing their independent non-uniform scaling. Decide dock slot
reflow from actual layout/hit-target evidence rather than merely stretching
four slots. Reuse the shared responsive owner’s existing geometry paths.
No implementation, new installed profile or physical qualification is claimed.
