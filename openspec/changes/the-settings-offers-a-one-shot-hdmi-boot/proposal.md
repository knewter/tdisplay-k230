## Why

Automatic HDMI plug/unplug now works, but the parked Settings prototype has no
proved one-shot reboot/restore sequence. Preserve that unfinished optional scope
from `plugging-in-hdmi-moves-the-display` tasks 3.1–3.3 so the accepted automatic
path can close separately if the operator approves the split. The operator does
not need this optional path for current use; proposing it does not authorize
implementation or installation.

## What Changes

- Preserve the Settings confirmation, next-boot status, alternate mainline DTB
  selector and one-shot panel restoration requirements and original proof commands.
- Retain the original next-boot guarantee as UNVERIFIED. An early Linux restore
  alone cannot guarantee recovery when Linux fails before restoration; resolve
  that gap explicitly before claiming the guarantee or operating the prototype.
- Reuse shipping HDMI-only and panel-only qualification bundles. Keep automatic
  switching the normal default and preserve protected serial recovery.

**Non-goals:** changing automatic hotplug, HDMI orientation or trackpad defaults;
landscape layouts; reviving the historical prototype without a new implementation
instruction; claiming a power cycle recovers a selector left before Linux restore.
Physical board/serial reservation is required for the named forward/back sequence.
No monitor photograph is required by the operator; observations and console proof
remain required.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `display/hdmi`: preserve the unfinished manual reboot/self-revert requirement
  as an ADDED follow-up to the accepted automatic capability. It must not be
  published as shipped until the successor's own tasks and physical proof pass.

## Impact

Future implementation owns a narrow boot selector/controller and restore unit,
Nix image wiring, Settings UI and focused tests. The prototype at `58498320` is
historical host evidence, absent from the current source and never installed.
This proposal changes planning files only. Its dependency is the accepted mainline
HDMI implementation at `6b4fe555`; grouping it separately does not make it complete.
