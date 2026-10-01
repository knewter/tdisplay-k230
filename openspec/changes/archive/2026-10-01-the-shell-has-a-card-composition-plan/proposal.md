## Why

The existing launcher can page text metadata after release, but it cannot show a running application's pixels, track a finger globally, shrink an app into a card, or close a thrown card. A real card deck needs a source-grounded route to application surfaces and input while preserving Sway as the single DRM owner.

## What Changes

- Compare existing client/protocol and narrow Sway/wlroots routes, then record the selected card-composition architecture and its surface, input, focus, close, buffer-lifetime, format, and presentation contracts.
- Require small source-audited capability probes before product integration: a two-app visual scene, continuous drag, expand, dismissal/refusal, and measurements on the live Pixman/RGB565 system.
- Preserve Sway as sole DRM owner and the current Pixman session as the default fallback. No GPU renderer or second compositor is selected by this plan.

## Capabilities

### New Capabilities

- `runtime/card-composition-plan`: specifies the evidence and interface gates for the selected visual application-card architecture.

### Modified Capabilities

None.

## Impact

Planning only. Host source audit and fixture work can proceed without the board; the two-app visual proof needs the board coordinator. A later implementation may add a pinned Sway patch only if the comparison selects it, and must not alter the default shell until the specified capability evidence exists. The sibling `the-shell-manages-apps-as-cards` change consumes this architecture boundary for product behavior.
