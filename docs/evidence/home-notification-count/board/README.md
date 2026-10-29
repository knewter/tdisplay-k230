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

## Privacy, paging and the shade (task 2.2), build `gpgh1vx6…` (commit `e8056ece`)

One event with the summary "Private summary" and body "private body" was
sent over D-Bus `Notify` (app name "Probe"). `home-count-paging-and-shade.png`,
five native captures 17:08:21Z–17:08:32Z, injected touch: Home shows only "1" at the
top right, no source or text; a left drag moved to page 2 with the count
still there; a right drag returned to page 1; a pull from the top edge opened
the shade, which lists the event (the shade is where content belongs);
closing it returned to Home with "1". Page 2's Weather widget is covered in
the capture because it shows a location. Dismiss all in the shade then
removed the count (checked with a crop of the corner, not committed).

## Corner padding (task 2.5), 2026-10-29

On the glass the operator reported that the count "kinda runs into the
rounded corner of the screen" and asked for more top-right padding.
`count-8px-before.png` (build `vf91pbq6…`, native `grim`) shows the pill 8 px
from the top and right edges. `COUNT_MARGIN` is now 24 px.
`count-24px-after.png` (build `37g1magg…`, test-activated, native `grim`,
count 1) shows the pill further inside the corner. A `grim` capture does not
show the panel's physical corner mask, so whether it now clears the corner is
for the operator to judge on the glass.
