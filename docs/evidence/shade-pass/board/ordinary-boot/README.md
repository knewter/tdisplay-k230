# Shade after an ordinary boot, build 2867v7pm

Evidence class: an ordinary boot on the board, with native grim captures and
injected touch. Nobody touched the glass for this check.

- 2026-10-29: the build
  `/nix/store/2867v7pmxsw8gk4w5b07zbhz2v0vrlfd-nixos-system-nixos-26.11.20260919.20b1ddd`
  was made the boot default. The charger was online, and the kernel, initrd
  and dtbs were the same as the previous default, `37g1magg…`. The `init=` in
  `/boot/bootargs.txt` was changed, and the system profile was set with
  `nix-env -p /nix/var/nix/profiles/system --set`.
- 10:10:59 CDT: `sudo systemctl reboot`.
- 10:12:42 CDT: the board was back. `/run/booted-system`, `/run/current-system`
  and the `init=` in `/proc/cmdline` all named `2867v7pm…`.
  `systemctl is-system-running` printed `running`, and
  `systemctl --failed` listed no units.
- `boot-2867.png`: a grim capture after boot. The shell is up, with the
  Terminal card in front.
- `boot-2867-shade.png`: a grim capture after an injected swipe down from the
  top edge (`swipe 616 2 616 400 400`). It shows the wide shade: the time and
  date lead, then the battery status line, the six tiles, the brightness and
  volume sliders, and "Notifications" heading the list. Quiet still reads
  "On" after the reboot. An injected swipe up closed the shade again.
