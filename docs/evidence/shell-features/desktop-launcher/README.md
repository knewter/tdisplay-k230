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
but not reboot. That recording remains runtime-deployment evidence; the
subsequent image boot is recorded separately below.

Host verification: `python3 tests/test_touch_menu.py` (six tests),
`python3 tests/test_desktop_catalog.py` (three tests, including two launch
variants), and the narrow cross build passed. Catalogue fixtures exercise
precedence, hiding, visibility, addition/removal, encoded labels, quoted
arguments, `%c`, `%k`, `%%`, `%f`, `%i`, working directories, and the terminal
bridge using real GLib 2.88.3. A launch handoff is not application-health proof.

## User hands-on verification

After the desktop-aware launcher demo on 2026-09-22, the user reported:
“i used my finger to tst it it's fine”. This confirms user-observed finger
usability of the launcher. It is separate from the automated camera recording,
which remains labeled injected. The report does not claim the prescribed axis
string, a battery-only boot, or every parent-shell system-control test.


## Source-built image boot

The daily source image from `3f397a6`,
`/nix/store/x0qz7ibmyb1bbmx1cpwgryxapkzisb0m-k230-sd-image.img`, was written
successfully (2,308,689,920 bytes). The image SHA-256 is
`797d3fdf1e9901c6cf5d219a75c902e0cae12b951c9582514042535837d4b0a6`.
[Write transcript](image-flash.txt) retains a `READBACK FAILED` line because
the already-running comparison was deliberately terminated after the user
requested an end to routine full readbacks. It is neither evidence of a write
failure nor a successful full comparison. No full-image equality is claimed.

[Subsequent reset and Linux boot](image-boot.txt) succeeded.
[100-second physical boot video](20260922T193941Z-desktop-image-boot.mp4)
shows the shell terminal and persistent controls after startup. USB cables
were attached; serial initiated the reset. This is not a battery-only boot.
[Post-boot diagnostics](post-boot.txt) record the immutable system
`/nix/store/mp5llx58dcpnikfdwn455pyrygdvggbg-nixos-system-nixos-26.11.20260919.20b1ddd`,
active shell and seatd, empty systemd `DropInPaths`, and the expected
`mrs3y5x82skma9xkz6s035ily6fs308r-k230-sway.conf`. The Nix store database
contains the 576 requisite paths without a manual load, and Neofetch reports
T-Head C908 (RISC-V64) (1).

The no-logo daily display path is in use: no `/boot/logo.bmp`, no one-shot
splash flag, and `/dev/fb0` present. This does not prove logo-to-kernel handoff.
The same boot exposed `firewall.service` failing with
`iptables: Failed to initialize nft: Protocol not supported`; the launcher
boot claim does not imply a fully healthy network firewall.

[25-second launcher video after reboot](20260922T195137Z-desktop-image-launcher.mp4),
[action script](image-actions.sh), and [console](image-launcher-console.txt)
record Apps, page two, Htop launch and reopening Apps with the same immutable
configuration. Native images show [Apps](image-apps.png),
[desktop entries](image-entries.png) and [Htop](image-htop.png).
These are injected touches on the physical board. No home-directory backup was
restored: the fresh shell home had neither a `.config` directory nor user
application entries before the demonstration. The private backup transfer was
canceled and its partial board copy removed; it is not a shell dependency.

The newly flashed source U-Boot (including patch 0005) also passed the
[read-only UMS and USB host coexistence cycle](../../uboot-ums-host-coexist-daily.txt):
host RTL8152 before UMS, mass-storage enumeration, host RTL8152 after UMS,
and return to Linux in 100.2 seconds. This cycle performed no write or full
image readback. The separate BootROM recovery drills remain unverified.
