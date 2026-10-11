## ADDED Requirements
### Requirement: A person can open an app's window list by touch
<!-- UNVERIFIED: today the menu opens only on a mouse right-click (source reading, 2026-10-11); no touch route exists or has been observed. -->
The shell SHALL offer a touch route to an app's window list that does not start the drawer's drag to Home. The list's loading, empty and stale states SHALL then be reachable with a finger.

#### Scenario: A person opens the window list with a finger
- **WHEN** a person uses the documented touch route on an app in the drawer or on Home
- **THEN** that app's menu opens with its window list, and no drag to Home starts
