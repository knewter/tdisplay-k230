# Theme apply through the on-screen chooser: board timing

**Evidence class:** installed system on the reserved board, driven by
injected touch through a virtual touchscreen cloned from the GT9895
descriptor. It is not a real finger. Timings come from the Rust shell's
`theme-command … path=socket ms=` lines and the helper's `THEME_TIMING`
lines in the journal.

- **System:** `/nix/store/phj9y4fggpb177b0hgaawbh510chhwil-nixos-system-nixos-26.11.20260919.20b1ddd`
  (`master` `f4f75998`).
- **Steps:** Settings, then tap Themes (450,125), wait 5 s, tap the centred
  catppuccin (284,520), wait 12 s, tap Apply (330,1082).

| Step | Journal evidence | Time |
| --- | --- | ---: |
| Open Themes: catalog `list` | `theme-command list path=socket ms=166` | 166 ms |
| Carousel opens, prepare-ahead of the centred theme (cold) | `theme-command preview … ms=4071` | 4071 ms |
| Tap centre, preview of an already prepared theme | `theme-command preview … ms=206` | 206 ms |
| **Tap Apply → Rust `appearance-commit-accepted`** | touch-down 66983 ms → commit 67539 ms | **556 ms** |
| Apply round trip | `theme-command activate … path=socket ms=509` | 509 ms |

The helper's breakdown for that activate: `parse=65.0ms`, `discover=2.0ms`,
`prepare_entry=90.6ms`, `activate_generation=336.0ms` (the Rust shell
re-received `appearance-prepare` at 67409 ms before its commit at 67539 ms),
and keyboard deferred 9.9 ms. The handler total was 438.6 ms and the helper
total 504.1 ms.

Earlier on this board: activate took about 4.2 s through the Python client
(`board-diagnosis-2026-09-24.md`), and list about 0.9 s. This is roughly 8×
faster, but it still misses the ~100 ms target. The remaining cost is
`activate_generation` re-running the two-phase prepare exchange during Apply,
even though the chooser already prepared the same generation, plus 65 ms of
request parsing and 91 ms of `prepare_entry`. Real-finger timing and a camera
check of when the new theme becomes visible remain open.

## Re-check after skip-redundant-prepare (master `bc0cf82f`)

The installed system is `/nix/store/v84gna5s1qnabg5mqhwa55anml2q8amh-…`. The
flow is the same injected chooser run, except the carousel was swiped one slot
before tapping the centre, so the applied theme was one the chooser had only
warmed by prepare-ahead (id `b801d916…`), not the active theme.

| Step | Journal evidence | Time |
| --- | --- | ---: |
| Neighbour prepare-ahead after the swipe (cold) | `theme-command preview b801… ms=2417` | 2417 ms |
| Tap centre, preview of the warmed theme | `theme-command preview b801… ms=162` | 162 ms |
| **Tap Apply → Rust `appearance-commit-accepted`** | touch-down 77049 ms → commit 77446 ms | **397 ms** |
| Apply round trip | `theme-command activate … path=socket ms=313` | 313 ms |

This time no `appearance-prepare-accepted` appeared between the Apply tap and
the commit, so the redundant prepare is gone. The helper reported
`parse=2.2ms` (down from 65 ms), `prepare_entry=63.0ms`,
`activate_generation=226.2ms` and total 307 ms. Tap-to-commit went from
556 ms to 397 ms (about 4.2 s originally). The ~100 ms target is still not
met. The remaining cost is inside `activate_generation` and `prepare_entry`;
showing the theme optimistically at tap time was deliberately left out to keep
the post-frame ack and rollback guarantees. Cold prepare-ahead of an unvisited
theme still takes 2.4–6.8 s, spent while the user browses.
