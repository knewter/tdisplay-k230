## ADDED Requirements
### Requirement: A person can open an app's window list by touch
*Grounding: `docs/evidence/recovery-routes/touch-capture-2026-10-11/README.md` (2026-10-11): on the installed build, holding a drawer tile still opened its menu (shell log `app-menu-hold` then `app-menu-ready`, no `home-drag-begin`) under a real finger, and the menu stayed open after lift. The touch route is the drawer hold; Home's long press still enters rearrange mode.*
The shell SHALL offer a touch route to an app's window list that does not start the drawer's drag to Home. The list's loading, empty and stale states SHALL then be reachable with a finger.

#### Scenario: A person opens the window list with a finger
- **WHEN** a person uses the documented touch route on an app in the drawer or on Home
- **THEN** that app's menu opens with its window list, and no drag to Home starts
