# Operator touch report after the GPU device-tree install

Relayed by the coordinator, 2026-10-30, after the DTB install at 14:38:24Z and
the warm reboot. Booted DTB `/boot/k230-tdisplay.dtb` sha256
`f3fe41f75a0de41895e5d9cfe0bdd28e0c1df1307abfe254058d7a2c3e0b2558`; boot default
(`/run/booted-system`) `/nix/store/49mnsl2si30m1l4fxdx2h114myv3anjf-nixos-system-nixos-26.11.20260919.20b1ddd`.
No GPU module was loaded at boot.

Evidence class: **operator observation on the glass** (verbatim, one sentence).
No capture, timing or list of gestures accompanies it.

> "yeah touch is fine carry on"

What it supports: the operator found touch working on the booted system with the
GPU node in the device tree. What it does not say: which gestures, which apps,
how long, or anything about Wi-Fi, audio or the GPU driver being loaded during
the touch.
