# Desktop-entry launcher, 2026-09-22

Source `d53d863` (also in daily image source `3f397a6`). The launcher now
uses GLib desktop-entry discovery and launch semantics, with Pango/Cairo text
and touch pages. It refreshes on every open; there is no background catalogue
daemon or separate cache to rebuild. Omarchy's discovery-based application
library informed the design; no Omarchy code or desktop stack was imported.

[90-second camera video](20260922T192343Z-desktop-launcher.mp4),
[manifest](20260922T192343Z-desktop-launcher.json),
[action script](actions.sh), [console transcript](console.txt).
The physical panel was recorded with FFmpeg at 1920×1080, 30 fps, rotated
180 degrees for presentation. The actions were injected uinput touches;
this does not prove finger accuracy. Native PNGs preserve readable layouts.

Observed on the physical board:

- Four desktop entries discovered: Foot, Foot Client, Foot Server, Htop.
  These represent two installed programs with three Foot launch modes,
  not four unrelated GUI applications. See [page two](second-page.png).
- Htop launches from its `Terminal=true` desktop entry using the readable
  Foot/htop configuration: [Htop](htop.png), window 7 in the transcript.
- Adding a temporary user desktop entry changes the count from four to five
  on reopen: [added](added.png). Selecting it creates the distinct
  `k230-discovery-proof` window 8: [launched](launched.png).
- Removing that entry restores four on reopen: [removed](removed.png).
- Keyboard-open pagination leaves all controls accessible:
  [first page](keyboard.png), [second page](keyboard-page-two.png).
- An entry with an unavailable working directory produces a visible GLib
  error and retains the overlay/Back: [error](error.png). Back then dismisses
  it, and reopening yields the ordinary four entries. Temporary entries and
  the injected device were removed; see [cleanup](cleanup.txt).

At first open, RSS was 15,748 KiB and proportional memory was 7,289 KiB
(about 7.1 MiB). This is a single observation, not peak or latency evidence.
The 327.1 MiB Sway-config dependency closure includes the already-installed
compositor and libraries. The final transfer from the preceding trial was
55,720 bytes across five new store paths; it is not total image size.

[Final deployment](install-final.txt) imported source-built store paths and
restarted the shell with `/nix/store/mrs3y5x82skma9xkz6s035ily6fs308r-k230-sway.conf`.
This capture uses a runtime systemd override, which survives service restart
but not reboot. Full-image/reboot acceptance remains a separate task.

Host verification: `python3 tests/test_touch_menu.py` (six tests),
`python3 tests/test_desktop_catalog.py` (three tests, including two launch
variants), and the narrow cross build passed. Catalogue fixtures exercise
precedence, hiding, visibility, addition/removal, encoded labels, quoted
arguments, `%c`, `%k`, `%%`, `%f`, `%i`, working directories, and the terminal
bridge using real GLib 2.88.3. A launch handoff is not application-health proof.
