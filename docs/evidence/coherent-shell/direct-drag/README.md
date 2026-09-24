# Direct manipulation correction

On 2026-09-24 the user reported that the installed preview moved faster than
their finger during an upward swipe, and clarified that momentum belongs
after release while a held touch must directly control movement.

Source inspection found the compositor normalized drawer travel over 60%
of output height while Rust rendered 81% travel, multiplying displacement
by 1.35. Shade used 55% against 65%, approximately 1.18 times displacement.
`c5cf6146` aligns those denominators with the rendered panel geometry while
leaving the separate 72-pixel release decision intact. The per-mille wire
representation rounds position; native pixel checks allow two pixels.

`python3 tests/test_card_shell_route.py` and
`python3 tests/test_card_shell_reveal.py` pass (one test each). These prove
existing route/cancel/protocol behavior, not the new geometric result.
Native pixel regression, exact target build, installation and physical
finger review remain open. The separate app-to-deck entry also used a
72-pixel visual travel and is being corrected independently. No physical
acceptance task is closed by this source checkpoint.
