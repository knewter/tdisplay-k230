# Shell feature media

This directory contains evidence captured from the physical K230. The gallery is available at [index.html](index.html).

Native clips are portrait 568×1232 H.264 videos assembled from Wayland screencopy PNG samples. They use the measured capture-start intervals, which are roughly 2 samples per second; they show state changes and readability, not smoothness, frame rate, compositor performance, or touch accuracy. The adjacent `native.json` records the sample timing and injected-input provenance. The original PNG samples are retained in [native-source.tar.xz](native-source.tar.xz).

Camera clips are 30-fps recordings of the physical panel. `demo.mp4` is the rotated, web-ready copy; the timestamped MP4 is retained as the camera source. Camera footage proves that pixels appeared on the panel, while the automated recordings use injected uinput or Sway IPC as identified below. It does not prove a finger touched the glass.

| Feature | Native sampled video | Screenshot | Camera video | Provenance and limits |
| --- | --- | --- | --- | --- |
| Installed application discovery | — | [Apps](desktop-launcher/apps.png), [entries](desktop-launcher/second-page.png), [keyboard](desktop-launcher/keyboard.png), [error](desktop-launcher/error.png) | [90-second video](desktop-launcher/20260922T192343Z-desktop-launcher.mp4) | Injected touches; discovery, Htop launch, add/remove refresh; [fresh-image reboot and evidence](desktop-launcher/README.md) |
| Portrait launcher (fixed baseline) | — | [menu.png](portrait-launcher/final-menu.png), [monitor.png](portrait-launcher/final-monitor.png), [keyboard.png](portrait-launcher/final-keyboard.png), [drag-cancelled.png](portrait-launcher/final-drag-cancelled.png) | [20260922T190646Z-portrait-launcher-final.mp4](portrait-launcher/20260922T190646Z-portrait-launcher-final.mp4) | Injected touchscreen events on the physical board; Terminal/Monitor/New Terminal/Back, keyboard path, repeated Apps, and cancelled drag are in [console.txt](portrait-launcher/final-console.txt); no finger-accuracy claim |
| Neofetch CPU identification | — | [native.png](neofetch-cpu/native.png) | [20260922T185501Z-neofetch-cpu.mp4](neofetch-cpu/20260922T185501Z-neofetch-cpu.mp4) | Serial-launched offline Nix shell; corrected T-Head C908/RISC-V parser; no finger interaction claim |
| U-Boot splash trial | — | [held splash](../splash-trial/uboot-held-25s.jpg), [native Linux](../splash-trial/linux-native.png), [post-splash defect](../splash-trial/20260922T183432Z-shell-after-splash.jpg) | [U-Boot](../splash-trial/uboot-splash-held-rotated.mp4), [transition](../splash-trial/splash-to-linux-rotated.mp4) | Serial-initiated warm reboot; U-Boot logo is proven before Linux, but the physical Linux handoff wraps/recolors the status row; see [boot-splash.md](../boot-splash.md); continuous handoff remains open |
| Terminal | [native.mp4](terminal/native.mp4) | [screen.png](terminal/screen.png) | [demo.mp4](terminal/demo.mp4) | Injected keyboard taps type `pwd`; sampled state changes plus physical-panel camera |
| Keyboard show/hide | [native.mp4](keyboard-show-hide/native.mp4) | [screen.png](keyboard-show-hide/screen.png), [hidden.png](keyboard-show-hide/hidden.png) | [demo.mp4](keyboard-show-hide/demo.mp4) | Injected taps show, dismiss, and reopen wvkbd |
| Launch Monitor | [native.mp4](launch/native.mp4) | [screen.png](launch/screen.png), [menu.png](launch/menu.png) | [demo.mp4](launch/demo.mp4) | Injected Apps launch; default htop clips columns, corrected by the portrait profile below |
| Window switching | [native.mp4](switch/native.mp4) | [screen.png](switch/screen.png), [next.png](switch/next.png) | [demo.mp4](switch/demo.mp4) | Injected Windows/Next navigation; older narrow Monitor layout remains visible in this capture |
| Terminal recovery | [native.mp4](terminal-recovery/native.mp4) | [screen.png](terminal-recovery/screen.png), [menu.png](terminal-recovery/menu.png) | [demo.mp4](terminal-recovery/demo.mp4) | Injected close then Windows/Home recovery |
| System controls | [native.mp4](system-controls/native.mp4) | [screen.png](system-controls/screen.png), [menu.png](system-controls/menu.png) | [demo.mp4](system-controls/demo.mp4) | Injected inspection and cancellation; Power off/Reboot were not executed |
| Neofetch | [native.mp4](neofetch-clean/native.mp4) | [screen.png](neofetch-clean/screen.png) | [demo.mp4](neofetch-clean/demo.mp4) | Clean image after automatic Nix registration; launched through Sway IPC/login shell |
| Monitor portrait | [native.mp4](monitor-integrated/native.mp4) | [screen.png](monitor-integrated/screen.png) | [demo.mp4](monitor-integrated/demo.mp4) | Injected Apps launch after verified image flash; uses the shipped Nix HTOPRC, without a local profile |
| Unattended startup | — | [screen.png](startup-portrait/screen.png) | [demo.mp4](startup-portrait/demo.mp4) | Verified portrait image, serial reset and automatic startup; USB cables attached |
| Reboot | — | [screen.png](reboot/screen.png) | [demo.mp4](reboot/demo.mp4) | Injected reboot confirmation and return; camera evidence, no native sample clip |

The diagnostic [neofetch-launch-failed](neofetch-launch-failed/) and earlier [neofetch](neofetch/) captures are retained for debugging but are excluded from the featured gallery.


The confirmed Reboot clip verifies return to an active shell with a new boot ID.
Power-off execution, battery-only boot, and a complete finger-touch workflow
remain unverified. These files are ready for site integration; this portable
gallery does not publish them into the existing Astro site.

The gallery now features the verified portrait image for Monitor and startup.
Earlier [live Monitor](monitor-portrait/) and [startup](startup/) recordings remain
for provenance. The newer Monitor sample originals are retained separately in
[its source archive](monitor-integrated/native-source.tar.gz). Its board clock
was unset (March 17); host camera timestamps are September 22.
