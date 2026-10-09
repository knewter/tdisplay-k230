## Why
The Apps catalog presents Foot Client, Foot Server, and Htop as equal generic “Installed application” cards. A person cannot tell which action is useful without launching it.
## What Changes
- Curate the portrait catalog into human-named actions while retaining desktop-entry discovery and safe GLib launch semantics.
- Demote implementation endpoints unless they have a useful named action; keep built-in Terminal, Monitor, New terminal, and Help.
- Add compact card metadata that preserves 56px-or-larger targets and page bounds.
## Capabilities
### New Capabilities
- `runtime/app-launcher`: a curated, refreshable action catalog above desktop-entry discovery.
### Modified Capabilities
None.
## Impact
Userspace launcher/catalog and its host fixtures; no compositor, cards, video lifecycle, or hardware change. Board review is needed for optical/readability and real-finger proof.
