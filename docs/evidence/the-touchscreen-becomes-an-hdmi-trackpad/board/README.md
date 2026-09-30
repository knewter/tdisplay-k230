# HDMI trackpad board checkpoint

The corrected relay's 20-second **startup-only dry run** succeeds on the real board: HDMI automatically selects Trackpad mode, the real GT9895 axis plan omits invalid pressure, and shutdown releases the grabbed touchscreen. Both shell services remain active. `startup-only.json` and the whitelisted `startup-only.log` preserve the command, installed profile and observation.

At that startup-only checkpoint no finger events occurred, so task 3.0 was still open. That run created no uinput device. It established none of pointer movement, tap/click, scrolling, pinch, shell gesture integration or panel-mode restoration. The subsequent trials below supersede this startup-only status. The persistent service was disabled at that checkpoint; its later installation is recorded below.

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

## Persistent HDMI service

`persistent-service.json` and its whitelisted log record the installed
service-enabled HDMI system. `k230-touch-trackpad`, `shell` and `shell-ui` are
active; the relay is enabled at boot, exactly one relay process and one
virtual touchpad are present, and Sway reports tapping enabled with two-finger
scrolling. The bounded transient trial was replaced by this persistent unit.
The filtered shell journal shows none of the original invalid-absinfo/libinput
errors during this observation. No reboot or panel-mode test was performed.
Physical click/scroll/pinch acceptance and pixel evidence remain open.
