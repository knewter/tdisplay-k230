## Why

Overview offers no obvious route to Home while keeping apps open. Standard mouse input reaches the Rust launcher but the compositor's overview owns only touch events, and Rust overlay wheel events are ignored. The user reports these navigation gaps on the physical board.

## What Changes

- Make overview cards, the Home footer, and edge drags navigable with a normal mouse or the board's built-in glass acting as an HDMI trackpad.
- Make the overview Home target tappable as well as swipeable, without closing any app.
- Bind four-finger spread to smoothly expand the centered card; keep inward pinch for overview.
- Support wheel/two-finger scrolling in scrollable shell surfaces and audit Home, drawer, overview, shade, Settings, themes and Wi-Fi routes by actual pointer interaction.

- Complete Home → overview with a visible bottom gesture handle: tap/click for open windows; swipe up for the app drawer.
- Distinguish an edge tap from a drag before taking client input or hiding a mapped overlay. App header controls and drawer-search Backspace must remain tappable. Ordinary app-launch behavior is unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `runtime/shell`: pointer navigation, overview-to-Home, centered-window spread, and shell scrolling.

## Impact

Userspace Sway adapter, Rust Wayland client, and Nix session configuration. Host/headless tests can establish event dispatch and scene outcomes. The physical board is needed for deployment, captures and real-glass acceptance. No kernel, touch calibration, display rotation, theme redesign, or hardware haptics changes.

## Accepted closeout, 2026-10-01

The operator accepts this delivered functional scope and waives additional
capture-only acceptance gates. `docs/evidence/proposal-closeout/2026-10-01/mouse.md` records the exact report,
prior evidence and limits. Its task dispositions supersede older statements
that these acceptance gates remain open; they do not claim new test runs.
