> **Superseded 2026-10-11.** This change targeted the Python/C touch-launcher, which the Rust coherent shell no longer launches. Unmet requirements move to `the-rust-shell-explains-stale-denied-and-ended-states`. Tasks below were not performed and are deliberately left unticked; specs are not synced.

## Why
Home recovery is explained only inside Help while the first persistent control says Windows. Error states also expose raw helper/GLib text inconsistently, making recovery less clear.
## What Changes
- Make Home and Back recovery visible at the first decision point without removing Apps, Windows, Keyboard, or System.
- Normalize short status copy and visible recovery actions for catalog/window/system/video states.
## Capabilities
### New Capabilities
- `runtime/recovery-navigation`: shared visible recovery routes and status-copy contract.
### Modified Capabilities
None.
## Impact
Touch bar, launcher, and video/system state copy/fixtures. It does not replace card composition, catalog discovery, or video lifecycle ownership. Board readability testing remains required.
