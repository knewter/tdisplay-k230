# Home notification count: board evidence

Evidence class: board, notifications injected with `busctl` on the shell
bus (see `docs/evidence/do-not-disturb/board/README.md`), native `grim`.
Build `/nix/store/f0zn5j8l5a7b7a2j26cwvpqkahg61rsv-nixos-system-nixos-26.11.20260919.20b1ddd` (commit `7a58eb53`),
2026-10-27.

- `home-count-1-with-banner.png` (15:43:16Z): one event, its private banner
  at the top and the count "1" at the top right of Home.
- With Quiet on, two more events at 15:43:36Z and 15:43:39Z showed no banner
  and the count read "3" (`home-count-3-quiet.png`) (task 2.3).

The count shows only the number.

## Dismiss and clear (task 2.1), build `zs05li2k…` (commit `be58ff02`)

`home-count-3-2-cleared.png` is a sheet of three native captures of Home:
16:48:20Z with three waiting events the count reads "3"; 16:48:29Z after one
was dismissed in the shade it reads "2"; 16:48:38Z after Clear all it is gone.
All three events were sent over D-Bus `Notify` with the app name "Probe",
which matches no installed app, so every one came from an unknown sender
rather than one of three. `k230-notifications emit` was not used; the D-Bus
path is the one real apps take.

Paging and the pull-down shade with the count showing (2.2) were not run.
