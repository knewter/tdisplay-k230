# Fresh-image declarative defaults

The final image was built from `7a83afa`, written over UMS, and reset into
`/nix/store/n5lqa24jxmlw5sn1q89y58js3ag7p859-nixos-system-nixos-26.11.20260919.20b1ddd`.
[Image identity and build](../../daily-shell-image.md),
[write and boot](image-flash.txt), [fresh state](fresh-image.txt), and
[installed firewall rules](firewall.txt) record the checks.

The shell home was empty before launching either application. Foot, htop and
Neofetch use `/etc` links into the Nix store. No home backup, local config,
service override, or manual Nix database load was used. Automatic registration
reports 577 closure paths. The board clock is unset; camera timestamps use host
UTC.

| Feature | Screenshot | Camera video | Launch |
| --- | --- | --- | --- |
| Neofetch | [native](plain-neofetch.png), [physical](plain-neofetch-physical.jpg) | [20260922T204419Z-plain-neofetch.mp4](20260922T204419Z-plain-neofetch.mp4) | `foot -e bash -lc 'neofetch; exec bash'` |
| Htop | [native](plain-htop.png), [physical](plain-htop-physical.jpg) | [20260922T204441Z-plain-htop.mp4](20260922T204441Z-plain-htop.mp4) | `foot -e htop` |
| Startup | [physical](startup-physical.jpg) | [20260922T204210Z-declarative-final-startup.mp4](20260922T204210Z-declarative-final-startup.mp4) | Automatic shell after serial-initiated reboot; camera starts during boot |

Plain Neofetch now fits its OS and CPU/core-count lines without clipping.
[After-launch inspection](after-launch.txt) confirms that it did not generate
a user config. Plain htop loads the portrait CPU/memory/process profile.

The firewall starts successfully and installs IPv4/IPv6 filter and mangle
chains, including conntrack acceptance, DROP refusal and reverse-path checks.
This proves installed rules, not network packet delivery.

Applications were launched through serial/Sway IPC; no real finger input or
battery-only boot is claimed. Camera clips prove physical display output but
the angled view and glare limit small-text legibility; native PNGs provide
exact readable pixels. Recordings and hashes are included in the adjacent
[media validation index](../media-validation.json).
