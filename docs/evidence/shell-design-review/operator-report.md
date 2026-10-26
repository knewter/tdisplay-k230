# Operator report: on-glass check of the installed build, 2026-10-26

**Evidence class: operator's on-glass observation, reported in chat.** The
operator used the board's touchscreen themselves. No camera recording was made.

- **Build:** `/nix/store/1r8zfd5s7jy0wqkvinpxch908nl3w6sz-nixos-system-nixos-26.11.20260919.20b1ddd`,
  from source `3ec31882`. It was test-activated with `switch-to-configuration test`, and
  `master` at `1723fd09` evaluates to the same system.
- **Requested check:** one pass that covers two changes:
  - `the-shell-and-its-apps-look-finished` (task 9.2): the drawer, Shade,
    Settings, Home, the overview, Clock, Timer and Weather, the GTK games and
    Galculator, and Nautilus. The request named the limits in
    [README.md](README.md#limits), including the background chooser's
    neighbour slice and the truncated input line in Battery – Details.
  - `the-hiding-keyboard-uncovers-the-app` (task 2.2): sliding the keyboard
    down uncovers the app, with no opaque strip.
- **Report:** "looks good". It was received shortly before
  2026-10-26T18:25:27Z, which is the board clock's reading when the promotion
  started. The operator listed no exceptions.

## Limits

- The report is a single overall acceptance. It does not itemise surfaces.
- The operator accepted the limits named in the request as they stand. They
  are not resolved:
  - The background chooser's neighbour slice still shows.
  - The input line in Battery – Details is still truncated.
  - Timer and Weather touch input was exercised on the host only.
  - The exact number of btop rows was not measured.

## Promotion

After the report, `1r8zfd5s` replaced `h4rqzlgr` as the persistent system.
The kernel and initrd are identical between the two.

[`promote.py`](promotion/promote.py.txt) is the keyboard-blend promotion
script with these values changed:

- the system paths;
- the state directory;
- the source revision.

It ran as root under the board lock and set the profile to `system-92-link`.

An earlier attempt is worth noting. `nix-env --set` followed by
`switch-to-configuration boot`, then a reboot, still booted `h4rqzlgr`. That
pair does not rewrite `/boot/bootargs.txt` or the DTB, which pin `init=`. The
profile was reset before the script ran.

An ordinary reboot then came up with these results:

- boot `887f0c98…`;
- the booted, current and profile systems were all `1r8zfd5s`;
- `shell` was active;
- `systemctl is-system-running` reported `running`;
- the `/boot` hashes matched the receipt.

See the [receipt](promotion/receipt.json).

**Rollback.** Copy `/var/lib/k230/shell-design-promote-20261026/promotion/rollback/`
back to `/boot`, then run `nix-env --profile /nix/var/nix/profiles/system --set`
with `h4rqzlgr`.
