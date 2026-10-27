# Home notification count: board evidence

Evidence class: board, notifications injected with `busctl` on the shell
bus (see `docs/evidence/do-not-disturb/board/README.md`), native `grim`.
Build `/nix/store/f0zn5j8l5a7b7a2j26cwvpqkahg61rsv-nixos-system-nixos-26.11.20260919.20b1ddd` (commit `7a58eb53`),
2026-10-27.

- `home-count-1-with-banner.png` (15:43:16Z): one event, its private banner
  at the top and the count "1" at the top right of Home.
- With Quiet on, two more events at 15:43:36Z and 15:43:39Z showed no banner
  and the count read "3" (`home-count-3-quiet.png`) (task 2.3).

The count shows only the number. Dismiss, clear-all and paging with the
count showing (2.1, 2.2) were not run.
