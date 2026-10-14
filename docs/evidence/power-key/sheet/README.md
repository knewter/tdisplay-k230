# Power sheet on the board (tasks 3.3, 3.4), 2026-10-14

Landscape image, real power key and glass, operator at the board. Native
`grim` captures of the shell (camera waived by the operator).

## Hold, sheet, Cancel, named confirmation (3.3)

- `sheet-open-grim.png`, 16:38:22: holding the key opened the Power sheet
  (Restart…, Power off…, Cancel). Operator: "yes" (they held it), then
  Cancel closed it.
- `restart-confirmation-grim.png`, 16:38:48: Restart… opened the named
  confirmation "Restart device?" with Cancel and Confirm. Boot ID unchanged
  (`ccd3f704-…`): nothing ran before confirmation.
- `after-cancel-grim.png`: a later tap at x=52 on that bar cancelled it and the
  sheet showed "cancelled".

Problems the trial found, fixed in this branch (host tests; the revised sheet
still needs a look on the board):

- The confirmation was one bar split invisibly at its middle: the operator's
  tap on its left half cancelled when they meant to confirm, and the sheet
  looked frozen.
- Two real Confirm taps landed at y=505.4 and 507.5, just under the bar's
  432–500 band, and did nothing; the third, at 486.5, worked.
- "Restart device?" was painted twice (the question and the reply message).
- A swipe up the sheet (from 524,328 to 458,6) did not close it.

The confirmation is now two separate buttons, Cancel and the named action
(Restart or Power off), whose taps reach to the sheet's bottom edge; the
question is painted once; an upward swipe closes the sheet. Test:
`service_ui::tests::the_power_sheet_confirmation_is_two_buttons_with_room_below_and_swipes_away`,
replaying the board's own tap and swipe coordinates.

## Confirmed Restart and Power off (3.4)

Restart, from the shell's journal (boot `ccd3f704…`):

```
16:45:59.450939 kernel: k230-pmu-pwrkey 91000000.pmu-pwrkey: INT0 press
16:46:00.157049 k230-shell-rust: map-request
16:46:00.533893 kernel: k230-pmu-pwrkey 91000000.pmu-pwrkey: INT0 release
16:46:11.944438 sudo: shell : ... COMMAND=.../bin/systemctl reboot
16:46:11.995263 systemd-logind: reboot requested from client PID 4728 ('systemctl') (unit shell-ui.service)...
16:46:17.654292 systemd: Reached target System Reboot.
```

The next boot, `c988db76…`, started at 16:46:32 on its own and the shell came
up (`shell-ui` active). Operator: "i tapped confirm that time and it's
restarting now".

Power off (boot `c988db76…`):

```
16:52:19.509049 kernel: k230-pmu-pwrkey 91000000.pmu-pwrkey: INT0 press
16:52:20.214622 k230-shell-rust: map-request
16:52:21.088953 kernel: k230-pmu-pwrkey 91000000.pmu-pwrkey: INT0 release
16:52:26.364396 sudo: shell : ... COMMAND=.../bin/systemctl poweroff
16:52:26.412739 systemd-logind: poweroff requested from client PID 1213 ('systemctl') (unit shell-ui.service)...
16:52:32.029459 systemd: Reached target System Power Off.
```

Operator: the screen went dark and stayed off until they held the power key
for about 3 s ("it did"). The next boot, `dadc6e5c…`, started at 16:53:05.
The power-off handler is the one recorded in `../power-off/`.

Limits: no serial or camera capture. `/dev/ttyACM0` on this bench is another
device, not the K230, and the camera is waived. The power-off result (board
dark until the key hold) is the operator's observation; the journal shows the
request and shutdown, and the new boot ID shows the start again.
