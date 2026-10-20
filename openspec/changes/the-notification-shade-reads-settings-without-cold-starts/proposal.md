## Why

The operator reports stutter while pulling the notification shade. The installed-board comparison identifies repeated Python Settings startup as a major CPU competitor: roughly 821 ms CPU per status call on the only online core. The existing async UI worker avoids blocking the UI thread but still starts that competing process during reveal.

## What Changes

- Preserve the existing Settings status JSON, fresh reads on every request, async queue/coalescing/deadline, unavailable states and all action behavior.
- Route the installed wrapper's ordinary read-only `status` call to a small native helper; retain the Python action implementation and CLI compatibility.
- Compare native status against the existing Python implementation on capability fixtures before building and deploying a matching userspace candidate.
- Retain installed kernel/compositor/Rust client identities and landscape. Record bounded before/after shade pulls and actual normal installation separately from host/build results.
- Inspect storage before deployment; remove only identified, owned, safely copied disposable files. Preserve current/booted/persistent systems, boot backups and rollback roots. Stop deployment if no safe adequate space can be obtained.
- Non-goals: cache stale state, defer freshness, weaken unavailable/error reporting, change actions/confirmations, change process priorities, kernel/display work, add a resident daemon, promise 60 fps or complete other deferred measurements.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. This is an implementation/performance refactor preserving the existing `runtime/device-settings` and `runtime/shell` contracts. `skip_specs: true` prevents inventing a capability requirement for an implementation choice.

## Impact

Userspace only: `nix/settings-status.c`, its Nix derivation, `nix/handheld-settings.nix`, native/Python conformance tests and `docs/evidence/shade-status/`. Existing Settings actions remain in `tools/device_settings.py`. Host tests/builds do not establish installed behavior. Physical qualification needs the reserved board over protected SSH, following the operator's preference; subjective smoothness needs an operator report. Other jank/portrait proposals stay open.
