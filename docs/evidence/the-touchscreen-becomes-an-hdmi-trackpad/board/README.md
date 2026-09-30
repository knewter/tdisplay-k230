# HDMI trackpad board checkpoint

The corrected relay's 20-second **startup-only dry run** succeeds on the real board: HDMI automatically selects Trackpad mode, the real GT9895 axis plan omits invalid pressure, and shutdown releases the grabbed touchscreen. Both shell services remain active. `startup-only.json` and the whitelisted `startup-only.log` preserve the command, installed profile and observation.

No finger events occurred, so the full task 3.0 contact test is **still open**. No uinput device was created and the persistent service remains disabled. Pointer movement, tap/click, scrolling, pinch, shell gesture integration and panel-mode restoration have not been established by this run. Root is coordinating an operator-contact trial; later gates may only advance after its required proof.

The prototype and proposal were already merged on master through `6534585eb00a` (verified as an ancestor of the shared master), completing the earlier task 4.2 handoff. This checkpoint changes evidence/task reconciliation only.
