## Context and resolved ownership

Read end to end on 2026-10-01:
`nix/handheld-settings.nix` exports helper executable paths and runs
`tools/device_settings.py`; `nix/handheld-notifications.nix` exports Sway IPC
and runs `tools/notification_center.py`. These are JSON/action helpers, not
rendered clients. The real Settings and Shade surfaces are `Route::Settings`
and `Route::Shade` in `nix/rust-shell-client/src/render.rs`, driven by
`main.rs`'s service snapshots and layer-shell overlay.

## Decisions

The Rust process owns both surfaces and already reads startup appearance and
handles prepare/commit/rollback through `appearance.rs` and `main.rs`. Shared
`RendererCache::set_appearance` invalidates their rendered caches; deferred ACK
waits for presentation readiness. Reuse this Rust/deck transaction rather than
adding independent Settings/notification endpoints for surfaces with the same
owner. The old assumed additional-endpoint task is superseded by proof of this
actual owner, preserving all-or-nothing semantics.

Settings panel/row backgrounds use `controls.background` if authored, otherwise
`menu.background`, otherwise `palette.background`. Normal text/tint consumes
`controls.normal-color`; selected tint consumes `selected-color` with a normal
fallback; normal/selected fills consume their alpha tokens. Selected outlines
consume the selected brush/width; ordinary row outlines remain omitted under
the accepted border-light design. Shared readable secondary text/accent/error
uses the palette. Notifications consumes its background and authored alpha,
text, countdown/accent and shared controls tints. Scalar text roles adapt the
first brush stop; full background/fill brushes retain gradients and alpha.
Every generated controls/notifications role must be reported, including absent
hover/focus, normal outlines, pressed/selection-specific states and notification
outlines as unavailable where no painted equivalent exists. Unknown custom
roles remain unknown. Report fallback role adaptation explicitly.

Rejected: pretending data helpers can repaint, creating extra acknowledgments
for one shared UI owner, calling every compiled token painted, restoring
unnecessary outlines to justify a coverage claim, or accepting a host screenshot
as physical proof.

## Verification and limits

The named system test runs generation/role-report regressions plus actual Rust
Cairo renderer pixel tests. It fails when Cargo/the native renderer test cannot
run. Normal startup/prepare/commit/rollback parser and rendering tests and the
existing two-receiver transaction suite establish host behavior only.
Task group 4 retains the full coherent closure build and physical dark/light
native captures with rollback. No fresh real-finger usability trial is needed
for this theme-only scope; injected commands and native screenshots are labeled.

## Open Questions

No surface-owner question remains. Task 4.2's six native physical-board captures
now establish dark/light presentation and same-surface rollback. See
`docs/evidence/omarchy-themes/settings-notifications-themed/board/README.md`.
This scoped change needs no additional boot or finger gate.

## Shared-layer invalidation found during the board trial

Settings and Shade rollback was visible at `eb38af2a`, but Home's independent
cached layer did not receive a repaint when the renderer changed appearance.
Mark that layer dirty on optimistic adoption, commit/rollback and failed-commit
restoration too. Repeat the native trial on the rebuilt source and compare the
dock as well as the scoped Settings/notification colors. Do not use the earlier
partially stale frames as proof of a coherent rollback.

The repeat at `288535289172c8465c4fa408eaa8ba2c7ab8a5ac` passed: Home dock
pixels as well as Settings and Shade returned to dark. The matching full
coherent system built successfully. Normal services and the original active
generation were restored; this was a recoverable component trial, not full
system activation. The larger theme/polish proposals retain their own gates.
