## Why

The accepted HDMI shell uses portrait rotation. Its success does not establish
usable Home, navigation and Settings in landscape. Preserve original HDMI
tasks 5.1–5.4 explicitly so the automatic-switching proposal can close separately
if the operator approves the split. Geometry work already belongs to
`the-shell-adapts-to-output-resolution`; reuse it rather than create a competing
implementation owner.

## What Changes

- Qualify a landscape HDMI output and document mutually exclusive display use.
- Finish the actual-geometry scaling audit and usable Home/navigation layouts
  using the responsive-shell implementation and its existing host fixtures.
- Obtain separate physical Home/Settings landscape observations, native captures
  and correct interaction proof; portrait acceptance cannot complete this gate.

**Non-goals:** changing accepted portrait defaults without instruction, redesigning
every shell screen, adding new hotplug or input drivers, HDMI audio/CEC, or claiming
host renders prove real monitor interaction. Host geometry work needs no board;
landscape qualification requires the single board/serial reservation. The
operator waived a monitor photograph, while observations and native captures
remain required.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `runtime/shell`: add the explicit minimum usable HDMI landscape requirement.

## Impact

Future work owns the landscape Sway qualification profile, the remaining geometry
and layout integration, and physical evidence. Shared responsive code/tasks
remain owned by `the-shell-adapts-to-output-resolution`; this proposal owns their
HDMI landscape integration gate. Automatic HDMI implementation at `6b4fe555`
is a prerequisite, not landscape evidence. This proposal changes planning only.
