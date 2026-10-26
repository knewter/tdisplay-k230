# Design-review leftovers: board captures and measurements, 2026-10-26

Change: `openspec/changes/the-design-review-leftovers-are-closed`.

**Evidence class: native `grim` captures and sway IPC timings with injected
touch.** The operator did not touch the glass during these runs, so this is
not the operator's on-glass check (task 2.4).

- **Build:** `/nix/store/qh3i7b3f6isbmjphxw133nrw5901m474-nixos-system-nixos-26.11.20260919.20b1ddd`.
  It was test-activated with `switch-to-configuration test`, then
  `systemctl restart shell`. The boot default stayed `1r8zfd5s`.
- **Driver:** [`ui.py`](ui.py.txt) is the shell design-review driver, plus a
  `stamp` action that prints the wall-clock time. It ran over SSH under
  `/tmp/k230-board.lock`, like `docs/evidence/shell-design-review/run.sh.txt`.

## Results

| Item | Result | Capture |
| --- | --- | --- |
| Charger line | Full, on the charger: the line reads "USB power · limit 3.25 A", with no ellipsis. The charge target that did not fit is dropped. | `build-qh3i7b3f/home.png` |
| Chooser slices | Both carousels draw a thin frame along each item's outline. The pale background beside the centred one now shows its card edge, not loose glyphs. | `build-qh3i7b3f/themes.png` |
| Timer | Opened at 05:00 Ready. +1 min gave 06:00. −1 min twice gave 04:00. Start was running at 03:57 after 3.5 s, with Pause showing. Reset gave 04:00 Ready. | `build-qh3i7b3f/timer-*.png` |
| Weather | Refresh changed "Updated 15:49" to "Updated 16:14" (local time). Not committed: the screen shows a location. | — |
| Omawrite start-up | Tap to first new window: 6.89 s, 1.52 s, 1.50 s. | below |

## Omawrite start-up

[`time-launch.py`](time-launch.py.txt) ran as root on the board at
2026-10-26T21:15:24Z, with the tile at (717, 291) and three runs:

```
sudo flock -n /tmp/k230-board.lock python3 /var/tmp/time-launch.py /var/tmp/ui.py /var/tmp/verify 717 291 3
{"run": 1, "app_id": "omawrite", "tap_to_new_window_s": 6.892}
{"run": 2, "app_id": "omawrite", "tap_to_new_window_s": 1.516}
{"run": 3, "app_id": "omawrite", "tap_to_new_window_s": 1.5}
```

Each run did the following:

1. closed every app except the session's terminal;
2. opened the drawer;
3. printed a timestamp just before the injected tap;
4. took the first sway `window` event with change `new` after that timestamp.

The first run is the first launch since the shell restarted. The later two
find its files already in the page cache. This is a measurement only. The
change sets no threshold for it, and nothing about Omawrite was changed.

## Limits

- **What the timing measures.** A `new` window event is sent when the
  compositor creates the window, not when its first frame is shown. The
  time until the window has content was not measured.
- **The cold run.** It is a single sample, taken on a board that had been up
  for 2 h 47 min.
- **Weather.** Its tap was checked visually and the capture is not committed.

The operator's on-glass check and the promotion are in [operator-report.md](operator-report.md).
