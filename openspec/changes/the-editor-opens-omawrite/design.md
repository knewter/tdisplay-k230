## Context

Editor is `k230-editor.desktop`, currently a Nano launcher in `nix/shell.nix`.
Home pins store desktop-entry IDs. Upstream Omawrite is a Qt Quick/C++ app
with its own Open/Save buttons, Qt file dialogs and Omarchy palette reader.
The board currently uses a software Wayland compositor at 568x1232.

## Goals / Non-Goals

Make Omawrite a usable ordinary app in the existing shell and default graphical
text/Markdown handler. Keep the CLI recovery editor available. This is not
approval of Qt as the shell toolkit or completion of the general Qt proposal.

## Decisions

- Nix/userspace only: pin upstream `omacom/omawrite` revision and source hash;
  compile for RISC-V and retain MIT/OFL notices. No prebuilt x86 package.
- Preserve `k230-editor.desktop` for existing pins, label it Omawrite and use
  the upstream icon. Set StartupWMClass to the app's Wayland ID so Home can
  focus it. Avoid a duplicate visible editor entry.
- Select Wayland and Qt Quick software rendering in the app wrapper, not
  globally. Do not assume a working GPU or install a replacement shell.
- Carry a narrow portrait adaptation: allow a 568px window, constrain dialogs
  to the available view and use Qt's in-process Open/Save dialog rather than
  introduce an unqualified portal service. Keep touch targets reachable above
  the bottom system gesture band and while the keyboard reserves space.
- Read the existing active Omarchy palette through the app's existing theme
  reader with a path adaptation if required; preserve live palette reload.
- Set image-level graphical MIME defaults for plain text/Markdown. A Home
  directory edit or an ad-hoc installed binary is not the deliverable.

## Risks / Trade-offs

- Qt increases the closure and may cross-build slowly → build the package
  first and record its closure cost before a coherent-system build.
- Desktop QML can clip on a phone → exercise the exact portrait size, software
  backend, file dialogs and keyboard interaction before persistent install.
- Software text rendering may be slow → record observed startup/edit behavior;
  do not claim general Qt performance or a framerate from a launch screenshot.

## Migration Plan

Land the plan promptly, build/test the package, wire image defaults, then
use the reserved board for a bounded application trial. Preserve user files;
use a dedicated scratch document for edit/save/reopen proof. Select the new
system persistently only after that proof, retaining the prior image for rollback.
