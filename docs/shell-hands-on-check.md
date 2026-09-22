# Handheld shell hands-on check

Use this only on the physical panel. Each line in **Glass action** is a finger
interaction, not an injected pointer or serial substitute. The coordinator
records camera and serial evidence; the operator does not need extra tools or
network access.

| Check | Glass action | Coordinator capture |
| --- | --- | --- |
| Keyboard and typing | Tap **Keyboard** to show it, tap **Keyboard** again to hide it, then show it and type `echo 1qaz0plm` followed by Enter in Terminal. The deliberately asymmetric string spans the left (`1qaz`) and right (`0plm`) sides of the mobile layout. | Camera must show the keyboard appearing, hiding, and the command plus its output. Serial is observation only. Save under `docs/evidence/shell-features/keyboard-show-hide/` and `terminal/`. |
| Apps | From the home bar tap **Apps**, then **Terminal**. Return home, tap **Apps**, then **Monitor**. | Camera shows each named menu item and the resulting full-screen tab. Save under `terminal/` and `monitor-portrait/`. |
| Windows | With Terminal and Monitor running, tap **Windows**. Tap the displayed window title to focus it. Open **Windows** again and tap **Next** to page, then tap the next displayed title. Use **Home** or **Back** to leave the page. | Camera records each focus change and page; serial may preserve the Sway tree only as supporting evidence. Save under `switch/`. |
| Terminal recovery | Focus Terminal, use the on-screen keyboard to type `exit`, and confirm that it closes. From the home bar tap **Apps** then **Terminal** to restore it. | Camera captures the closed state and restored terminal. Save under `terminal-recovery/`. |
| Safe system controls | Tap **System**, **Power off**, then **Cancel** and confirm the shell remains usable. Then tap **System**, **Reboot**, and **Reboot now**. | Camera captures both confirmation pages. Coordinator records serial boot progress for the confirmed reboot. Save under `system-controls/` and `reboot/`. |
| Battery-only boot | Only if a charged battery is available, have the coordinator arrange a fully powered-off, USB-disconnected start. Turn it on normally and wait for the shell without a tether. | Camera records the uninterrupted start; serial must not be treated as proof of this check. Save under `startup/`. |

The labels above are the current touch-menu labels in `nix/touch-menu.sh`:
**Apps**, **Windows**, **Keyboard**, **System**, **Terminal**, **Monitor**,
**Next**, **Home**, **Back**, **Power off**, **Cancel**, **Reboot**, and
**Reboot now**. Record whether each interaction was actual glass touch; camera
or serial evidence alone does not establish that.
