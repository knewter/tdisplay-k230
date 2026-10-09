# The flashable image ships mainline: host inspection and fresh-card boot

2026-10-08, America/Chicago. Evidence classes: host inspection
([host-inspection.json](host-inspection.json)), **reserved physical-board flash
and serial boot**, and native `grim` capture.

## Flash (task 2.1)

The image is `/nix/store/20mxf9lrzxp1zz1bk9siz0cffjvm6wli-k230-sd-image.img`
(`nix build .#sdImage` on this branch). It was written to the board's own TF
card over U-Boot `ums 0 mmc 1` on the J3 data USB-C. U-Boot presented the card as
`/dev/disk/by-id/usb-Linux_UMS_disk_0-0:0`, and `tools/flash.sh` (by-id target
and print-and-confirm, unchanged) reported:

```
done. 2026-10-08T20:07:19-05:00  wrote 5430300672 bytes in 644.239556982 s
```

The card held no data the operator needed ("i have no data on it"). Its
`/home/shell` and `/var/lib/k230/wifi` were archived to a protected host
directory before the flash. Neither is committed.

## First power-on of the fresh card

After the flash the board ran `reset` in U-Boot with no other input. The serial
console showed `Linux version 7.3.0-rc5`, `Welcome to NixOS 26.11 (Zokor)!`
and `nixos login: root (automatic login)`, with no `FAILED` unit lines. At
97 s uptime:

- current system and profile were both `kp6ldmdx33lgjl55hzv3xba5a55ils48-nixos-system-…`
  (the system the image's DTB `init=` selects);
- `shell`, `shell-ui` and `theme-helper` were `active`;
- `systemctl is-system-running` was `running` (it read `starting` once at about
  60 s), and there were no failed units;
- first-boot root growth had expanded `/dev/mmcblk1p2` to 59 G (4.3 G used);
  `/boot` was 58 M of 100 M.

After `swaymsg 'card_shell home'`, the fresh home's defaults (wallpaper, clock,
Video icon, dock) rendered:

![Native Home on the freshly flashed card](fresh-home.png)

After this record was taken, the Wi-Fi credential was restored over the serial
console to its protected path (`/var/lib/k230/wifi`, modes 700/600,
root-owned). `k230-wifi.service` then reported active and `wlan0` held an
address. Without it, a fresh card has no network, as designed. The
home folder was not restored, so the board now runs fresh repository defaults.
