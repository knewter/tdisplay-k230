## Context

The shared base currently leaves the timezone at the NixOS default. The shell clock already uses libc `localtime_r` and `/etc/localtime`.

## Goals / Non-Goals

Use the requested timezone for the running board and every board profile. RTC persistence and a timezone picker are outside this change.

## Decisions

Set `time.timeZone` in `nix/k230.nix`, the Nix layer shared by the hardware profiles. A runtime-only `timedatectl` setting cannot define a fresh image default, so it is only the immediate activation step. Retain the existing UTC/NTP/RTC policies.

## Risks / Trade-offs

A running client may retain its libc timezone state. Refresh only the shell UI if necessary; preserve the compositor and apps. Deploy the coherent HDMI trial profile so the proven renderer and touch routing remain selected.
