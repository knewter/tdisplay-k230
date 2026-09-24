# Launcher drawer and route source checkpoint

This checkpoint starts the final gesture session behind `k230-touch-launcher --serve`; the existing no-argument launcher remains the rollback menu. The persistent process leaves its layer surface unmapped while idle. `k230-touch-launcher --surface drawer|shade|settings` sends a bounded request through a mode-0600 socket in the session runtime directory. A successful helper exit means the persistent process accepted and submitted the mapping request, not that a frame reached the panel. The mapped surface uses the `k230-shell-drawer` namespace agreed with the card compositor owner. It draws no fake application cards: the live deck remains owned by Sway. The drawer itself lists installed desktop entries continuously with names and existing artwork, without Previous/Next pagination or a permanent footer. This route is not yet selected as the normal image session.

The drawer touch model tracks scroll displacement while a finger moves, bounds its offset and flick velocity, stops coasting on a new contact without launching, and cancels tap on a scroll, long press, second contact or Back. A long press opens a cancellable context sheet. This is host/source evidence only. The compositor's deck-to-drawer gesture command, Settings and notification data consumers, complete scene synchronization, actual Wayland mapping test, cross-build, installed image and real-finger proof remain open. No OpenSpec task is checked by this partial checkpoint.

Host checks from this source tree:

```text
python3 tests/test_shell_gestures.py
  PASS: drawer-drag, flick-stop, cancel-below-threshold, tap-launch,
        hold-cue, move-cancel, back-cancel, second-contact
python3 tests/test_shell_routes.py --case route-socket
  PASS: production launcher compiled; route client receives a positive
        local acknowledgement, rejects unknown routes, and fails closed
        when the private route socket is unavailable.
python3 tests/test_launcher_navigation.py
  PASS: 3 existing rollback navigation/client checks.
python3 tests/test_shell_icons.py --case theme --case missing --case cache-bound --case notification-icon --case private-no-identity
  PASS: 5 existing icon/privacy checks.
```

These tests do not run a compositor. They do not prove drawer movement on glass, layer z-order, scene presentation, keyboard ownership, or the user-visible final route.
