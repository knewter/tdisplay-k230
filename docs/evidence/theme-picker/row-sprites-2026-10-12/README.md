# Theme-row repaint as cached card sprites, 2026-10-12

Task 14.4 follow-up in change `the-shell-swaps-themes-without-a-python-stall`.

The operator reported, on the panel, that "it's really janky moving between
theme cards and it shouldn't be". This directory records the board
measurements behind the fix, the install, and the operator's response.

The source is branch `perf/theme-row-paint`, in worktree
`/home/jadams/tmp/k230-row-paint`. The commits are:

- `f11c86fe`: spinner pulses and thumbnail arrivals repaint only the picker
  rows;
- `4d17b3c5`: carousel cards are drawn from cached sprites cut by an A8 mask.

Times are UTC.

Evidence classes:

- software-injected swipes over SSH, with counters-only runtime traces;
- one `perf record -e cpu-clock` profile on the board;
- one native `grim` capture;
- coherent-installer serial checks;
- one operator report after using the panel by finger.

No camera observation is claimed.

## Measurement

[swap-and-swipe-used.py](swap-and-swipe-used.py) ran as root over SSH. For
each run it does the following:

1. Points `shell-ui` at a given shell ELF through a non-persistent `/run`
   drop-in.
2. Sets `K230_TRACE_COUNTERS_ONLY=1` with a 55 s window.
3. Opens Settings → Themes.
4. Injects eight horizontal swipes on the theme row through a temporary
   `K230 injected touchscreen`.

Runs that left an empty trace are not counted. Those runs overlapped a restart
and were repeated.

| Label | Shell ELF | Trace files |
| --- | --- | --- |
| old | installed `k2z9z61k…` (master `24804e19`) | `old-3`, `old-4`, `old-5` |
| first fix | `ljrsf4…` (`f11c86fe`) | `new-2`, `new-3`, `new-4` |
| sprite | `b0yyyda8…` (`4d17b3c5`) | `sprite-1`, `sprite-2` |

The table shows `picker_row_repaint` in the `moving` phase, plus
`scene_rebuild` counts in the `held` and `moving` phases. All traces report
`dropped: 0`.

| Run | Repaints | CPU / repaint | Wall / repaint | Max wall | Full rebuilds |
| --- | --- | --- | --- | --- | --- |
| old-3 | 49 | 81.0 ms | 98.6 ms | 125.9 ms | 6 |
| old-4 | 51 | 79.4 ms | 101.0 ms | 124.7 ms | 6 |
| old-5 | 51 | 79.8 ms | 101.7 ms | 131.5 ms | 6 |
| new-2 | 46 | 75.1 ms | 120.2 ms | 246.4 ms | 0 |
| new-3 | 54 | 74.6 ms | 95.5 ms | 142.9 ms | 0 |
| new-4 | 44 | 77.1 ms | 122.3 ms | 225.6 ms | 0 |
| sprite-1 | 91 | 30.1 ms | 42.9 ms | 66.1 ms | 0 |
| sprite-2 | 92 | 30.4 ms | 43.5 ms | 87.4 ms | 0 |

The first fix removed the mid-swipe full rebuilds but barely changed the cost
of each row repaint.

A board profile of the first-fix build (1,736 `cpu-clock` samples) showed:

- `memset` at 24.6%, of which 13.4% was under `paint_carousel`'s path fill
  through `general_composite_rect`;
- pixman bilinear fetches at about 17%.

On this RISC-V pixman, a clipped or anti-aliased fill whose source is a scaled
surface takes the general per-span path. The sprite commit instead renders
each card once into a cached surface and blits it untransformed. The scaled
image, the scrim and the skewed rounded outline mask are all baked into that
surface.

The sprite build roughly halves the repaint wall time and draws about 1.8 times
as many frames during the same swipes. It is not 60 fps: the two cards that
change size during a swipe are re-rendered each frame.

[sprite-build-picker-native.png](sprite-build-picker-native.png) is a native
`grim -s 0.5` capture of the sprite build at rest. The theme cards, the
Backgrounds row and the labels draw correctly.

The `kanagawa` theme shown there was applied durably at 08:11:43 through the
theme socket, during one of the old-build runs. It was either an operator tap
or a stray injected tap. It was left in place and is the baseline appearance
of the install below.

## Install

| Identity | Value |
| --- | --- |
| Bundle | `/nix/store/60azv75vjpgcshjwh9kdhz12h4r9i8d0-k230-coherent-shell-boot-files` |
| System | `/nix/store/rav09qp6dwsnbjd2jrbcs595g9ayn3xf-nixos-system-nixos-26.11.20260919.20b1ddd` |
| Rust shell ELF | `/nix/store/b0yyyda8l7nqix1jb95kbmhh9s5mqnj0-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust` |
| Kernel, `Image`, `initrd.uimg` | unchanged from the baseline |
| Baseline | default-backgrounds install `cwfx0amr…` ([../default-backgrounds-2026-10-12/](../default-backgrounds-2026-10-12/README.md)) |

The build ran with
`flock /tmp/k230-nix-build.lock nix build .#kernelMainlineDrmShellBootFiles --out-link ~/.local/state/tdisplay-k230/retained-builds/row-paint-2026-10-12/candidate2 --print-out-paths --max-jobs 1 --cores 4`
at `4d17b3c5` and exited 0.

The `/run` drop-in was removed, and `shell-ui` was restarted on the installed
`k2z9z61k…` before the preflight.

The coherent installer then ran with the default-backgrounds recipes. Only the
paths, the baseline, and the saved `kanagawa` appearance in
[expected-runtime.json](expected-runtime.json) differ (see the `*-used.py`
files). Every step passed:

1. **Preflight:** boot `a563b9fb-…`, 14:37:47 ([preflight.json](preflight.json)).
2. **Stage:** ([stage.log](stage.log), [transfer.json](transfer.json),
   [staged-state.json](staged-state.json), [host-inspection.json](host-inspection.json)).
3. **Candidate boot:** ([candidate-boot.json](candidate-boot.json)). The
   runtime check ran on boot `777f5a20-…` at 14:42:40
   ([candidate-runtime.json](candidate-runtime.json)).
4. **Qualification:** ([deployment-authorization.json](deployment-authorization.json)).
5. **Install and ordinary autoboot:** ([ordinary-boot.json](ordinary-boot.json)).
   The runtime check ran on boot `49fb3850-…` at 14:45:55
   ([ordinary-runtime.json](ordinary-runtime.json)). The current system and
   profile are both `rav09qp6…`, the four shell services are active, and the
   saved appearance is unchanged.

The operator tried the build through the `/run` drop-in, before this install.
No finger observation was made on the installed boot.

## Operator report

After using the sprite build on the panel (temporarily swapped in through
the `/run` drop-in), the operator wrote: "it's good to go land it".

This is a real-finger acceptance of the theme-row feel for landing. It does
not separately state the four curve properties that task 18.4 names, and it
does not cover the matched comparison of tasks 11.3 and 13.
