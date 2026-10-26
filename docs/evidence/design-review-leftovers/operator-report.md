# Operator report: on-glass check of the installed build, 2026-10-26

**Evidence class: operator's on-glass observation, reported in chat.** The
operator used the board's touchscreen themselves. No camera recording was made.

- **Build:** `/nix/store/qh3i7b3f6isbmjphxw133nrw5901m474-nixos-system-nixos-26.11.20260919.20b1ddd`,
  test-activated. `master` at `8baf2c91` evaluates to the same system.
- **Requested check** (task 2.4):
  - the Battery – Details charger line on Home;
  - the framed slices at the right edge of the background chooser;
  - whether the frame looks wrong on a dark theme.
- **Report:** "looks good". It was received shortly before
  2026-10-26T22:28:24Z, which is the host clock's reading when the promotion
  checks began. The operator listed no exceptions.

## Limits

- The report is a single overall acceptance.
- It does not say whether the operator switched to a dark theme to check the
  frame.

## Promotion

`qh3i7b3f` replaced `1r8zfd5s` as the persistent system. The kernel and
initrd are identical between the two.

[`promote.py`](promotion/promote.py.txt) is the shell design-review
promotion script with these values changed:

- the system paths;
- the state directory;
- the source revision.

It ran as root under the board lock and set the profile to `system-93-link`.

An ordinary reboot then came up with these results:

- boot `a8be57ef…`;
- the booted, current and profile systems were all `qh3i7b3f`;
- `shell` was active;
- `systemctl is-system-running` reported `running`;
- the `/boot` hashes matched the receipt.

See the [receipt](promotion/receipt.json).

**Rollback.** Copy `/var/lib/k230/leftovers-promote-20261026/promotion/rollback/`
back to `/boot`, then run `nix-env --profile /nix/var/nix/profiles/system --set`
with `1r8zfd5s`.
