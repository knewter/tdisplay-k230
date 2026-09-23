## Purpose
Keep a person oriented and able to recover from shell navigation and transient failures.
## ADDED Requirements
### Requirement: The shell SHALL make Home recovery discoverable
<!-- UNVERIFIED: current help documents Home, but first-level discoverability is proposed. -->
The shell SHALL expose a visible Home recovery route at the same decision level as window switching or clearly disclose it before entering a subpage, while retaining Apps, Windows, Keyboard, System, and Back behavior.
#### Scenario: A person needs a terminal after closing one
- **WHEN** no terminal is available from the current task
- **THEN** a visible Home route explains that it focuses or opens Terminal
### Requirement: Transient shell states SHALL name recovery
<!-- UNVERIFIED: implementation and integration evidence are pending. -->
Catalog, window overview, system action, and video surfaces SHALL use short person-facing status copy and an available visible recovery action. Raw paths, helper diagnostics, and secrets SHALL not be displayed in the person-facing status.
#### Scenario: A launch fails
- **WHEN** a desktop application cannot launch
- **THEN** the surface explains that it could not open and shows Back or Apps
#### Scenario: A window list is empty or stale
- **WHEN** no current selectable window remains
- **THEN** the surface says so and preserves Apps, Back, or Home without focusing a different window
