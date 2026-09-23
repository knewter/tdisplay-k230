# Handheld shell hands-on check

Use this only on the physical panel. Each line in **Glass action** is a finger
interaction, not an injected pointer or serial substitute. The coordinator
records camera and serial evidence; the operator does not need extra tools or
network access.

| Check | Glass action | Coordinator capture |
| --- | --- | --- |
| Keyboard and typing | Tap **Keyboard** to show it, tap **Keyboard** again to hide it, then show it and type `echo 1qaz0plm` followed by Enter in Terminal. The diagonal/asymmetric sequence spans the left (`1qaz`) and right (`0plm`) sides, catching both swapped and mirrored key mappings. | Camera must show the keyboard appearing, hiding, and the command plus its output. Serial is observation only. Save under `docs/evidence/shell-features/keyboard-show-hide/` and `terminal/`. |
| Directional drag | With the keyboard shown, touch and hold a letter-row key, then slowly drag horizontally in one direction across its neighbours. Before the command test, use Backspace to clear any character the touch sent. | Film the finger and pressed-key feedback together. Count it only if the visible feedback follows the left-to-right drag; record absent or incorrect feedback as a failed drag check. Save beside `keyboard-show-hide/`. |
| Apps | From the home bar tap **Apps**, then **Terminal**. Return home, tap **Apps**, then **Monitor**. | Camera shows each named menu item and the resulting full-screen tab. Save under `terminal/` and `monitor-portrait/`. |
| Windows | With Terminal and Monitor running, tap **Windows**. Tap the displayed window title to focus it. Open **Windows** again and tap **Next** to page, then tap the next displayed title. Use **Home** or **Back** to leave the page. | Camera records each focus change and page; serial may preserve the Sway tree only as supporting evidence. Save under `switch/`. |
| Terminal recovery | Focus Terminal, use the on-screen keyboard to type `exit`, and confirm that it closes. Tap **Windows**, then **Home** to exercise recovery; Home must start Terminal again when it was closed. | Camera captures the closed state, **Windows** page, **Home**, and restored terminal. Save under `terminal-recovery/`. |
| Safe system controls | Tap **System**, **Power off**, then **Cancel** and confirm the shell remains usable. Then tap **System**, **Reboot**, and **Reboot now**. | Camera captures both confirmation pages. Coordinator records serial boot progress for the confirmed reboot. Save under `system-controls/` and `reboot/`. |

The labels above are the current touch-menu labels in `nix/touch-menu.sh`:
**Apps**, **Windows**, **Keyboard**, **System**, **Terminal**, **Monitor**,
**Next**, **Home**, **Back**, **Power off**, **Cancel**, **Reboot**, and
**Reboot now**. Record whether each interaction was actual glass touch; camera
or serial evidence alone does not establish that.

The user explicitly declined a separate wall-supply power-on trial. It is not
a shell acceptance gate. Use the recorded touch-triggered reboot for automatic
startup, and label its USB-connected provenance; do not describe it as a
disconnected power-on test. No battery is required.
