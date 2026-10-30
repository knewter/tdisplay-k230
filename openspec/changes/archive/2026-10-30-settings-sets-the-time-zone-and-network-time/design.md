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

Settled by task 1.1 (`docs/evidence/time-zone/board/design-check.md`). The
board has no polkit. With the zone fixed, `timedatectl set-timezone` run as
`shell` is refused ("Access denied"), and the pinned nixpkgs does not disable
timedated's `SetTimezone`.

- **Persistence:** set `time.timeZone = null`, so that `/etc/localtime` is
  writable state on the root filesystem. An activation step after `etc`
  writes the America/Chicago link only when `/etc/localtime` is missing,
  which keeps the first-boot default.
- **Privilege: a socket-activated root helper, not polkit.** `k230-time.socket`
  (`/run/k230-time.sock`, owner root, group `shell`, mode 0660,
  `Accept=yes`) starts a short-lived `k230-time@.service` per request. The
  helper reads one line, answers `ok` or `error <reason>`, and exits. It
  accepts only:
  - `zone <name>`, where the name is listed in `/etc/zoneinfo/zone1970.tab`
    or is `UTC`. It then runs `timedatectl set-timezone <name>` as root, so
    timedated still writes the link.
  - `network-time on|off`. This creates or removes
    `/var/lib/k230-time/network-time-off` and starts or stops
    `systemd-timesyncd`. The timesyncd unit gains
    `ConditionPathExists=!/var/lib/k230-time/network-time-off`, so the
    choice survives a reboot. timedated's own `SetNTP` would try to enable
    and disable unit files, which NixOS keeps read-only.

  It also checks the peer's credentials (`SO_PEERCRED`): only the `shell`
  user is answered. Nothing is resident between requests.
- **The chooser:** Date & time's "Time zone" row opens a region page
  (Africa, America, …, UTC). A region opens its zones, paged with Previous
  and Next so that no new scrolling is needed, at the 99 px floor. Tapping a
  zone applies it and returns to Date & time.

Rejected:

- **polkit with timedated.** polkit is not on the image, and it would add a
  resident daemon and a JavaScript engine for two settings.
- **A sudo rule for `timedatectl`.** The zone argument would need a
  wildcard, and it would be a second privilege mechanism to audit.
- **Rebuilding the image with a new `time.timeZone`.** That is the current
  state, and it is what this change removes.

## Risks / Trade-offs

- [A root helper is new attack surface] → it accepts two fixed commands,
  validates the zone against the tzdata table, answers only the `shell`
  user, and runs hardened (`NoNewPrivileges`, `ProtectHome`, a narrow
  `ReadWritePaths`).
- [A switch to a new build resets a writable `/etc/localtime`] → the board
  check in task 3 includes a `switch-to-configuration test` and a reboot.

## Migration Plan

The first boot of the new build keeps America/Chicago until the person
changes it.
