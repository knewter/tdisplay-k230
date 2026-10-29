## Context

The layers are Nix (the system configuration) and userspace (the shell and a
privileged helper). `nix/k230.nix` sets `time.timeZone`, so NixOS makes
`/etc/localtime` a managed link and `timedatectl set-timezone` cannot change
it. `systemd-timesyncd` runs and has synchronized on the board
(`/run/systemd/timesync/synchronized` exists, per
`docs/evidence/settings-about/README.md`). The shell runs as the `shell` user
with no general root access. Its existing privileged actions (power, Wi-Fi)
each go through a narrow, named path. There is no login manager, and the
`shell` user has no `systemd --user` instance.

## Goals / Non-Goals

**Goals:** change the zone and turn network time on or off from Settings,
with the narrowest privilege that works, persisting across a reboot and a
build switch.

**Non-Goals:** setting the time by hand, automatic zone detection.

## Decisions

These are left open for task 1.1 to settle with a board check. The current
leaning:

- **Persistence:** set `time.timeZone = null` so that `/etc/localtime` is
  writable state, keeping America/Chicago as the first-boot default through
  an activation step that writes it only when it is missing.
- **Privilege:** `systemd-timedated` (`timedatectl`) with a polkit rule that
  lets only the `shell` user run `set-timezone` and `set-ntp`. This uses
  systemd's own checked interface rather than a new setuid or sudo rule.

Rejected so far:

- **A sudo rule for `timedatectl`.** Broader than needed, and it would be a
  second privilege mechanism to audit.
- **Rebuilding the image with a new `time.timeZone`.** That is the current
  state, and it is what this change removes.

## Risks / Trade-offs

- [polkit is not on the image, or adds too much to the closure] → task 1.1
  checks this on the board first. If so, the fallback is a small root
  service that accepts only a zone name from a fixed list over a socket that
  only the `shell` user can reach.
- [A switch to a new build resets a writable `/etc/localtime`] → the board
  check in task 3 includes a `switch-to-configuration test` and a reboot.

## Migration Plan

The first boot of the new build keeps America/Chicago until the person
changes it.
