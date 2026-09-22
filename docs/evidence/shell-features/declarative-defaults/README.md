# Initial fresh-image defaults check

Image source `6b59f33`, system
`/nix/store/whskfvcll29493mgj4lz51mqn23328fa-nixos-system-nixos-26.11.20260919.20b1ddd`.
The UMS write and normal boot passed without full readback or a home restore.
The shell home was empty, all three defaults resolved into the Nix store,
and automatic store registration reported 577 closure paths.

[Fresh state](fresh-image.txt) and [firewall rules](firewall.txt) prove these
claims. The board clock is unset; capture filenames use the host UTC clock.

Plain `foot -e htop` loads the narrow system profile, as shown by
[the screenshot](plain-htop.png) and the camera recording alongside it.
Plain Neofetch reads the packaged system config without creating a user config,
but [its initial screenshot](plain-neofetch.png) exposes clipped OS/CPU lines.
The [layout trial](neofetch-layout-trial.png) uses explicit `--gap 1
--distro_shorthand on` flags; those settings were then committed in
`nix/neofetch.conf` for the final image. The trial is not fresh-image proof of
the revised defaults.

All launches here use serial/Sway IPC. The camera captures the physical panel;
native PNGs use Wayland screencopy. These are not real-finger interaction tests.
