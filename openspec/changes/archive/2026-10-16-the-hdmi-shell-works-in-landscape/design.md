## Context

Original HDMI group 5 remains unfinished. The accepted monitor uses 1280×800
with transform 90 and a touchscreen trackpad. That proves portrait HDMI,
not normal-transform landscape. Shared whole-output configure, Home/Drawer
reflow, Settings transforms and hit-testing already belong to
the archived `the-shell-adapts-to-output-resolution`; its accepted portrait
fill and target evidence is available for reuse. This proposal owns the transferred density, Wi-Fi/theme geometry
and dock follow-ups in tasks 7.1–7.3. None is completed by this transfer.

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


## Responsive archive reference — 2026-10-09

Responsive physical fill and Home/All Apps/Settings target checks are accepted
for the normal 800×1280 portrait-HDMI arrangement and committed in
`docs/evidence/shell-responsive/board/acceptance-2026-10-09/`. The archived
responsive change supplies the shared implementation and this bounded proof;
all seven implementation/physical tasks here remain open. No portrait
observation closes this proposal’s separate normal-transform landscape gate.

## Panel landscape decision — 2026-10-13

Operator: "in this configuration the board should really be rotated 90 degrees
counterclockwise ... we should do it here (you can ignore hdmi ... we can test
it at the end tho)". Camera frames from the bench (the camera sits at the
device's top edge, opposite the person at the keyboard) fixed the direction:
a runtime `transform 90` put the terminal upright for the camera and upside
down for the typist; `transform 270` is upright from the keyboard side.

The orientation is a build-time option, as `hdmiTransform` already is, with
portrait kept as the default because accepted portrait defaults change only
on explicit instruction. A board in the keyboard case runs the landscape
profile. A runtime toggle in Settings is not part of this change.

Landscape HDMI (task 5.1, 2026-10-14) is the flake output
`k230-mainline-drm-shell-landscape-hdmi` (boot files
`kernelMainlineDrmShellLandscapeHdmiBootFiles`): the landscape panel profile
with `k230.shell.hdmiTransform = "normal"`. Sway takes the monitor's
EDID-preferred mode, so no mode is assumed (the operator's monitor offers
1280×800). The display controller has one CRTC, so the panel and HDMI are
mutually exclusive outputs: plugging the cable moves the session to HDMI-A-1
and unplugging returns it to DSI-1, with no reboot and no Settings button.
While HDMI is active the glass is a trackpad, so the touch calibration matrix
for `normal` is the identity.

The shell's landscape layout (`help::wide`) applies to every output at least
1.6 times as wide as it is tall. Before 5.2/5.3 it also required a short
output, so a 1920×1080 monitor fell back to the portrait pages, stretched
non-uniformly, with Settings running off the bottom.

The shared layout work (5.2, 5.3, 7.1–7.3) is done once, against actual output
geometry, so it serves both 1232×568 on the panel and HDMI landscape. The
panel's 568×1232 portrait renders stay byte-identical, guarded by the existing
pixel-identity test.
