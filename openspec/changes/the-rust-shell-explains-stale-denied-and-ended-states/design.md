## Context
Layer: userspace (Rust shell client, built as `.#handheld-shell-rust`). Existing Rust modules such as `video_status.rs`, `catalog.rs`, `sway_ipc.rs`, `service_ui.rs` are candidate homes. <!-- UNVERIFIED: which modules render each state today has not been audited. -->

## Decisions
- Define state IDs and short copy keys for loading, empty, stale, denied action, Stop, EOF, cancelled; each names one available Back, Apps, Home, Retry, Cancel, or Stop action.
- Raw paths, helper diagnostics, and secrets reach logs only.
- Stale means the focused target vanished; the shell must not focus a different window silently.

## Rejected
- Modal error stack or global notification system: outside scope.
- Porting changes to touch-launcher: it is unreachable under the coherent shell.
- Home disclosure: see proposal.
