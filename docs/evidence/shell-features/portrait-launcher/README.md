# Fixed launcher baseline, 2026-09-22

Source: `fb85a3d`. This is the first, fixed-action launcher. It does not
scan `.desktop` entries. The user requested installed-app discovery after
this recording; that extension remains in flight and this change is not archived.

The final 60-second camera recording is
[portrait-launcher-final.mp4](20260922T190646Z-portrait-launcher-final.mp4),
with its adjacent JSON manifest. [final-actions.sh](final-actions.sh) injects
uinput touches on the physical board. [final-console.txt](final-console.txt)
records actual Sway window IDs and launcher PIDs. No real finger accuracy is
claimed. The board clock was unset; camera filenames use the host clock.

Verified: Apps opens, repeated Apps keeps PID 2080; Terminal focuses the
existing terminal (window 5); Monitor starts window 7; New terminal creates
window 8; Back dismisses; the keyboard leaves all cards and Back reachable;
dragging off a card cancels activation; Windows dismisses the overlay.
The final native screenshots show each layout. Launcher memory at the first
open was RSS 4,128 KiB and PSS 1,558 KiB, one observation rather than a peak.
The scripted delays and camera recording are not latency measurements.

The final package was cross-built and imported into the existing image.
[install-session-verified.txt](install-session-verified.txt) confirms shell
restart with `/nix/store/83q3pzk9jyrwxckn05ybj7qn1k7fkqsr-k230-sway.conf`.
The override lives under `/run/systemd/system/shell.service.d/` and therefore
survives service restart but not board reboot. This is not a new full-image
boot test. [install-session.sh](install-session.sh) documents deployment and
rollback. The original `/etc` attempt failed because NixOS owns that immutable
directory; its transcript is retained.

Earlier screenshots and the 18:56 recording retain the prior layout for
comparison. Its `console.txt` used unavailable bare `jq`; use `final-console.txt`
for window-tree assertions. The final run uses the installed absolute jq path.

[desktop-inventory.txt](desktop-inventory.txt) inventories Foot, Htop, Foot
Server, and Foot Client desktop entries. The fixed launcher does not discover
them; this inventory is input to the requested discovery extension.
