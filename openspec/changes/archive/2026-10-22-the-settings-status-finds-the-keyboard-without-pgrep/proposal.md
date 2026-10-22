## Why

Every time the notification shade, Settings or Power opens, the shell reads
the settings status. On the board that read cost about 103 ms. Most of it was
a `pgrep` child that only checks whether the on-screen keyboard is running:
procps reads every process in full and loads glibc's gconv tables for its
regular expression. That is about 79 ms of CPU per open on the one online
core, competing with the shade's animation. While it ran, the shell took
21 ms to answer a frame callback.

## What Changes

- `nix/settings-status.c` finds `wvkbd-mobintl` by reading `/proc` directly:
  - `comm` first;
  - then the effective UID from `status`, only for a name match.

  This has the same match rule as `pgrep -u UID -x`.
- Tests replace the fake-`pgrep` cases with fake-`/proc` cases. A further test
  checks that the production status read starts no child process.
- Non-goals:
  - caching status;
  - changing the JSON, the Python actions or `K230_PGREP` for actions;
  - changing what the shade looks like;
  - opaque regions on sliding surfaces, excluded by the operator on
    2026-10-22.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. This is a performance refactor that keeps the `runtime/device-settings`
contract. It continues
`2026-10-20-the-notification-shade-reads-settings-without-cold-starts`, which
also used `skip_specs: true`.

## Impact

Userspace only: `nix/settings-status.c` and `tests/test_settings_status.py`.
Evidence is in `docs/evidence/interaction-jank/shade-pull/`. Proof needs the
physical board, for helper timing and injected shade pulls. Host tests cover
the matching rules.
