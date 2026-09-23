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
All three candidates cross-build; lf is rejected for its larger closure ; its later board observation below completes candidate task 1.2.

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

## Final initrd fix and fresh boot

[Final build](final-build.json) and [image hash](final-image.sha256) identify
`/nix/store/b384ag314xp1gprqy3i5h7sbsci3fmm0-k230-sd-image.img`, built from
`9b59fc005b331578c2cae32d743be45010dd051c` in 71.901 seconds. Signed regulatory
data is included in the initrd as well as the root firmware closure.
The image was written through UMS and booted successfully without a full
readback. The [fresh readiness record](final-readiness.txt) shows system
`/nix/store/x03zsq959aa1fifsibvchz8jqr7wzsxr-nixos-system-nixos-26.11.20260919.20b1ddd`,
boot `23619819-9cc7-44a7-8674-dc193fd39857`, shell/seatd/firewall active,
automatically started keyboard, bound radio, managed interfaces, and **zero**
early regulatory.db load failures. Global country 00 and driver-local 99 are
reported as observed; no runtime country override was needed for this trial.

The corrected documented runtime procedure was then exercised with a newly
supplied private configuration. Its client control directory and private log
worked without the earlier setup error. [Sanitized final connection results](final-wifi-network.txt)
again pass association, DHCP, Wi-Fi default/resolver routes, DNS and bound
outbound ping. This connection is left running for the operator. The source
copy was removed; the daemon's only protected configuration is root-owned
mode 0600 under `/run`, cleared on reboot. This is a **manual fresh-boot
reconnection**, not the unimplemented automatic reconnect/persistence tasks.

## Completing candidate comparison on the final image

The rejected lf candidate's exact built closure was transferred over Wi-Fi from
an ephemeral host HTTP server, SHA-256 checked, and imported with nix-store.
The server then stopped. lf was a temporary evaluation package; it was never
added to the system profile or Apps catalog. This tested the pinned package,
not an alternate implementation.

[Final candidate console](final-candidates-console.txt) records both selected
desktop IDs launched explicitly through `k230-desktop-catalog launch`, with
exit status 0. Nano RSS was 3,840 KiB and nnn RSS 2,688 KiB in this trial.
The [full Foot process arguments](final-app-environment.txt) show the shared
`k230-terminal-foot.ini` configuration retained for both entries.

lf started and rendered in Foot ([native screenshot](lf-trial.png)), with
8,576 KiB observed RSS. The interval from before compositor exec through a
0.2s wait was 0.297 seconds; the following process query confirmed it running.
As with the other samples, this includes harness overhead and is not isolated
startup or physical presentation latency. The lf process was then stopped and its imported package output deleted.
All three candidates now have build, closure, startup and memory observations.
Nano + nnn remains the selected set: lf adds 5,788,696 NAR bytes versus nnn's
441,408 and had higher RSS in these individual samples. These are single
observations, not a statistical performance benchmark.
