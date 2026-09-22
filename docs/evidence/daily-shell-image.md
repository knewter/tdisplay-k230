# Daily handheld image, 2026-09-22

The source-built image boots the physical board into Sway with the installed
application launcher. The boot log and feature checks are in
[shell-features/declarative-final](shell-features/declarative-final/).

## Reproduce

```
nix build .#sdImage --out-link result-daily --option max-jobs 1 --option cores 8 --option substituters https://cache.nixos.org
```

Image-producing source: `7a83afa`; subsequent evidence and read-only diagnostic
changes evaluate to the same image derivation.

- Image: `/nix/store/mc8di5pz0miia3fs27bqn1l9f7xx0a3w-k230-sd-image.img`
- Derivation: `/nix/store/d1gyh7vdpi591246f6nfb8s1mlaqzm4b-k230-sd-image.img.drv`
- Image file size: 2,308,689,920 bytes.
- SHA-256: `d6dacd7d4bfcc9233b78fd3fead6ca80e54dc679b9b4365fc9a1b915cbb585eb`.
- System: `/nix/store/n5lqa24jxmlw5sn1q89y58js3ag7p859-nixos-system-nixos-26.11.20260919.20b1ddd`
- System closure: 1,280,479,704 bytes (1221.2 MiB).
- Kernel: `/nix/store/b12sf247knyrfzidllghgnkysw8lhl8i-linux-riscv64-unknown-linux-gnu-6.6.36-xuantie`.
- Stage 1: `/nix/store/r7lvl2ddpm86p8cly5gcrnil58biyzsa-k230-stage1`.

The [write and boot transcript](shell-features/declarative-final/image-flash.txt)
records 181.7 seconds end to end at 12.7 MB/s, then U-Boot reset into the newly
written image and Linux return. No full readback was requested or performed.
No home-directory archive was restored.

## Defaults and boundaries

Foot, htop and Neofetch settings come from the repository and immutable NixOS
`/etc` links. The kernel includes the compatibility features needed by the
existing IPv4/IPv6 firewall policy. Desktop entries are discovered at launcher
open, with built-in Terminal/Monitor/recovery actions retained.

The daily image keeps `panelConsole=true` and omits `logo.xrgb`; the separate
splash-enabled system builds but its physical first-modeset handoff remains
incorrect. [Splash evidence](boot-splash-handoff.md) records the unresolved
geometry/color issue. BootROM recovery, a complete real-finger control run and
battery-only startup remain unverified. This checkpoint is not completion of
those hardware requirements.
