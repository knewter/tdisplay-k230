# Fresh image: offline Help, editor, files, and Wi-Fi

Host date: 2026-09-22 America/Chicago (2026-09-23 UTC). The board clock was
not synchronized; its timestamps are used only for elapsed intervals.

## Build and boot

[Build record](build.json), [image hash](image.sha256), and
[boot extract](boot-extract.txt) identify the image built from source commit
`eb3c4b849ff146a68f8ba5893f262e5c8650093c`:
`/nix/store/5qf3hhixs2z82phi405y60plqa8z0xij-k230-sd-image.img`.
The build took 185.425 seconds on the host. USB UMS wrote the image and
returned to Linux; no full-image readback was requested.
The running system was
`/nix/store/viq45iggfvfci11ggy6mj8x5ka0fdfzz-nixos-system-nixos-26.11.20260919.20b1ddd`,
boot `a45402f2-4c0c-44da-bfb1-8a7df1edd77e`.
Shell, seatd and firewall were active. No home-directory state was restored.
This is the normal panel-console configuration, not promotion of the separate
splash-preserving diagnostic image.

[Closure comparison](closure-comparison.json) uses the previous daily
panel-console system for like-for-like accounting: 1,280,517,168 NAR bytes.
Offline apps and Help total 1,280,960,640 bytes (+443,472); adding Wi-Fi gives
1,290,518,944 (+10,001,776 over daily baseline). The older running diagnostic
splash image is recorded separately because its different options make it an
unsuitable like-for-like baseline.

## Installed apps and Help

The first readiness command tried the catalog utility on the global PATH;
it is an internal executable in the launcher package, so that attempt failed.
The [explicit package-path query](catalog.txt) then discovered six entries,
including `k230-editor.desktop` and upstream `nnn.desktop`, both Terminal=true.
The installed launcher uses the same catalog implementation and configured
Foot terminal bridge.

[Injected actions](actions.sh) and [console results](apps-console.txt) show
Help, paging, Back, Editor and nnn after the image boot. The new apps were
launched from their actual catalog cards; no desktop fixture or alternate
launcher binary was installed. Screenshots: [Help](help.png),
[Help page 2](help-2.png), [Editor card](editor-card.png),
[nano](editor.png), [nnn card](nnn-card.png), [nnn](nnn.png).
The empty nnn list reflects a fresh home with no non-hidden files.

Nano RSS was 3,200 KiB. The nnn process listing contained two instances at
2,688 and 1,152 KiB, so it is not an isolated RSS measurement of the new
instance. The earlier isolated trial recorded 2,688 KiB.
The measured intervals around injected activation plus a deliberate 0.2s
wait were 0.612s (nano) and 0.609s (nnn). These are observation upper bounds,
not pure startup times or panel latency. Earlier baseline/injected measurements
and package outputs are in [the candidate trial](../offline-help-injected/README.md).
All three candidates cross-build; lf is rejected for its larger closure but
still lacks a board startup/RSS observation, leaving candidate task 1.2 open.

The harness mistakenly used SIGRTMIN+2 to hide wvkbd; that signal terminates it.
This did not affect the full-height app checks. The packaged keyboard was
explicitly restarted with its normal height/hidden arguments, and the subsequent
Wi-Fi regression captured it responding. The next full image boot restores
ordinary automatic keyboard startup without a runtime override.

These are injected touches on the physical board and native compositor
screenshots. They do not establish physical-finger accuracy or final-glass
readability for these new pages. Earlier accepted keyboard/Home finger tests
remain separate; no additional operator retake is required by this record.

## Wi-Fi connection

[Readiness](readiness.txt) shows SDIO vendor/device `024c:f179` bound to
`rtl8189fs`, module `8189fs`, and managed `wlan0`/`wlan1` interfaces.
No extra device-tree power GPIO was needed for this successful association.
The early kernel requested regulatory.db before the root filesystem was
available. It was present in the system firmware closure; runtime reload and
US regulatory selection worked ([record](regdb-runtime.txt)). A subsequent
initrd fix and boot are recorded separately below.

A root-only configuration was supplied privately through non-echoing serial
input into `/run`, never argv, shell history, Git, or the Nix store. The driver
log level was reduced before association and WPA output stayed in a root-only
runtime log. No raw status, scan, DHCP address, SSID, BSSID or key is published.
The pinned wpa_cli also required `/run/wpa_supplicant/client`; creating that
root-only directory resolved its initial control-socket error.

[Sanitized network results](wifi-network.txt) record association COMPLETED,
an IPv4 address supplied by the existing DHCP service, a default route on
wlan0, a resolver route using wlan0, a successful DNS lookup, and a successful
three-packet outbound ping test explicitly bound to wlan0. The DNS and ICMP tests
therefore establish Wi-Fi delivery, independently of USB Ethernet.

Shell, seatd and firewall remained active. Injected Apps/Back and keyboard
actions still worked ([native regression screenshot](wifi-regression.png)).
The temporary supplicant was stopped after checking its PID/config identity,
and both the operator source and copied runtime secret were removed
([cleanup result](wifi-cleanup.txt)). Serial console access continued.
This proves a one-off live connection, not persistent automatic reconnection.
