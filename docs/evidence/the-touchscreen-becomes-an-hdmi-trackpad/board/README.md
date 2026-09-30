# HDMI trackpad board checkpoint

The corrected relay's 20-second **startup-only dry run** succeeds on the real board: HDMI automatically selects Trackpad mode, the real GT9895 axis plan omits invalid pressure, and shutdown releases the grabbed touchscreen. Both shell services remain active. `startup-only.json` and the whitelisted `startup-only.log` preserve the command, installed profile and observation.

At that startup-only checkpoint no finger events occurred, so task 3.0 was still open. That run created no uinput device. It established none of pointer movement, tap/click, scrolling, pinch, shell gesture integration or panel-mode restoration. The subsequent trials below supersede its contact status; the persistent service remains disabled. Root is coordinating an operator-contact trial; later gates may only advance after its required proof.

The prototype and proposal were already merged on master through `6534585eb00a` (verified as an ancestor of the shared master), completing the earlier task 4.2 handoff. This checkpoint changes evidence/task reconciliation only.

## Real-contact trial

`contact-checkpoint.json` summarizes the next 20-second dry run: 8,515 raw
events, one-contact and two-contact frames, followed by clean release and
active shell services. The protected source capture is identified by SHA-256
and timestamp; its raw contents are not published. This completes the bounded
grab/read/translate/release safety gate, while recording the tool-code defect
it uncovered. In a subsequent bounded virtual-device trial the operator
reported cursor movement and no tap click. Neither this report nor the serial
capture proves scrolling, pinch, panel restoration, or pixel acceptance.

The follow-up source fixes the multi-finger UAPI codes and enables Sway's
normal tap-to-click configuration for the named virtual touchpad. Host tests,
including an independently compiled Linux-header comparison, and both RISC-V
relay and coherent-HDMI configuration builds passed. The full hardware gates
remain open until their corresponding physical observations are recorded.

`tap-configuration.json` records the installed corrected system/relay and
Sway's live classification: `tap: enabled`, `scroll_method: two_finger`.
The five-minute transient trial is independently bounded and does not enable
the permanent service. Physical click and scroll acceptance remain pending.
