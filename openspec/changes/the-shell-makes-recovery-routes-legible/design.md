## Context
Current Help says “Windows / Home,” while the persistent bar says only Windows and Home appears after entering that page. Native launcher error evidence shows a truncated filesystem path in a raw GLib error.
## Decisions
- Preserve the four persistent controls, but disclose Home recovery adjacent to Windows or provide an equally visible Home route.
- Define state IDs and short copy keys for loading, empty, stale, failed launch, denied system action, Stop, EOF, and cancelled.
- Each state names an available Back, Apps, Home, Retry, Cancel, or Stop action; raw helper paths stay in logs only.
## Rejected
- A modal error stack or a global notification system: outside the recovery scope.
- Moving lifecycle ownership from video/card changes: duplicates active work.
