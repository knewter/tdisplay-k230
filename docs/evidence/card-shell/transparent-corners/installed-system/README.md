# Rounded cards on the installed system

The physical board booted normally into the combined `11y992kp…` system.
The installed Sway is `7zvingic…`, containing the real rounded destination
clip. The selected live terminal and its partial left neighbor have rounded
corners exposing the selected wallpaper. The native capture was visually
reviewed; it contains no painted corner-cover patches.

![Installed rounded live cards over the selected wallpaper](rounded.png)

[Exact runtime identities and screenshot hash](result.json) ·
[Persistent installation and normal-boot proof](../../../backlight/combined-candidate/README.md)

The root coordinator held the board reservation and serial port. After
checking normal boot, active shell services and `/proc/<MainPID>/exe`, it
ran these commands as `shell` with `XDG_RUNTIME_DIR=/run/shell`,
`SWAYSOCK=/run/shell/sway-ipc.sock` and `WAYLAND_DISPLAY=wayland-1`:

```sh
swaymsg exec 'foot --app-id=k230-installed-card-proof --title=Terminal'
sleep 3
swaymsg card_shell enter
sleep 2
grim /run/shell/k230-installed-cards.png
```

The PNG was transferred to the host through the protected evidence endpoint.
This is a native screenshot on physical hardware. It is not camera evidence,
a frame-rate measurement, or real-finger motion acceptance. Task F.3 is
complete; task E.1 remains open for flicking, close/open gestures and the
radius transition's feel on the glass. No theme was applied during capture.
