## Context
Current native evidence shows generic page-two cards for Foot Client, Foot Server, and Htop. GLib remains the sole desktop-entry parser/launcher.
## Decisions
- Maintain a small allowlist/denylist of internal endpoint IDs with explicit user-facing action names and descriptions.
- Refresh discovery on Apps open, then filter/demote before pagination; no Exec parsing or shell evaluation.
- Keep Back, Apps, and launch-error recovery in place.
## Rejected
- Hiding every discovered application: removes useful installed tools.
- Importing a heavyweight launcher: exceeds the focused portrait scope.
## Risks
A curated entry can become stale; fixture coverage must test refresh, unknown entries, and a failed launch retaining controls.
