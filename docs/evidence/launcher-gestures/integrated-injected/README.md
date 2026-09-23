# Integrated-image injected gesture matrix

Captured 2026-09-23 at 04:27:26 UTC on the physical K230 board. These are
**injected touch and native compositor captures**, not real-finger evidence.

## Installed source and procedure

The flashed image was built from `03cbade`:
`/nix/store/d7r354bnsnffxnwnqblaf3raqvd15190-k230-sd-image.img`.
The running system was
`/nix/store/568vf3220mpvdmgjgfnz5ln0qn09934r-nixos-system-nixos-26.11.20260919.20b1ddd`,
boot ID `506e9b30-5617-4ecf-9c88-95e50dd5113e`.
The installed launcher binary was
`/nix/store/mmc9ag2dasrpp0ph3d890yq5mqcm0pcb-k230-touch-launcher-riscv64-unknown-linux-gnu-0.1/bin/k230-touch-launcher`.

The operator started that launcher as the shell user with
`K230_LAUNCHER_METRICS=/run/shell/launcher-metrics.txt`, PID 1099. Terminal and
Monitor were already open. `evemu-device` replicated the real touchscreen
controller descriptor as `/dev/input/event1`. The repository's unchanged
`tools/inject-tap.sh` and `tools/gesture-acceptance.py` ran from `/run` using
the installed Python closure. See [procedure](../procedure.md) and
[the executed action list and memory snapshots](acceptance.json).

The helper exited 0 after 20 left/right pairs, an explicit keyboard show/hide,
a two-window catalog query, overview entry, and its Back button. No input was
injected during the subsequent separately requested real-finger recording.

## Result

[The complete trace](launcher-metrics.txt) contains 197 render records and
41 settled transitions: 40 Apps transitions and one overview entry. Analysis:

```sh
python3 tools/analyze-launcher-transitions.py \
  docs/evidence/launcher-gestures/integrated-injected/launcher-metrics.txt \
  --expect-alternating 20
```

[Analysis output](analysis.txt) verifies exactly 20 left/page-1 then
right/page-0 pairs, with no missed or duplicate page changes. The catalog still
contained the two expected windows after those swipes. A classified swipe did
not launch another application.

| Measured quantity | Median | p95 | Maximum |
| --- | ---: | ---: | ---: |
| Release to final-frame submission, elapsed | 138 ms | 151 ms | 163 ms |
| Process CPU since release | 62.060 ms | 62.878 ms | 69.644 ms |

Every settled transition was below 200 ms. At most three live Wayland buffers
were recorded. The two transient animation snapshots occupied 5,343,744 bytes.
That snapshot counter excludes the saved last frame, live SHM buffers, font
caches, and other allocations; it is not total launcher memory.

The `/proc` snapshots record RSS 18,344 → 26,324 KiB and PSS
9,748 → 17,252 KiB, with the final status high-water mark 31,364 KiB.
The helper's `status` JSON key contains the selected `/proc/status` lines;
`smaps_rollup` contains separately sampled RSS/PSS. These are before/after
observations, not a continuous peak or a leak diagnosis.

## Native captures and limitations

- [Before paging](apps-before.png) and [after 20 pairs](after-20-each.png).
- [Keyboard explicitly shown](keyboard-visible.png).
- [Two-window overview](overview.png) and [Back to Apps](after-back.png).

These PNGs were produced by `grim` on this run and pulled over the serial
console. They contain the shell UI and generic test windows. Their hashes are
registered as DATA in `docs/blob-inventory.md`.

The transition timestamps measure CPU-side release-to-submit work, not panel
scanout or optical presentation. This run measures paging with the keyboard
hidden and one multi-card overview transition. The keyboard-visible screenshot
alone does not measure transitions under keyboard load. Focus selection,
stale/empty cases, downward exit, forced rollback and real-finger acceptance
remain separate gates. No archive follows from this matrix alone.

## Keyboard-visible follow-up

The same launcher PID then ran five left/right pairs with the keyboard explicitly
shown (`pkill -USR2 -x wvkbd-mobintl`). Each drag used the same coordinates and
250 ms settle interval. The keyboard was hidden with SIGUSR1 afterward.
[Trace](keyboard-gesture-metrics.txt), [analysis](keyboard-analysis.txt), and
[native frame](keyboard-gesture.png) preserve this separate run. All ten
transitions alternated correctly: elapsed median 132 ms, p95/max 139 ms;
process CPU median 47.214 ms, p95/max 52.573 ms. Maximum live buffers remained
three. The smaller surface's two snapshots occupied 3,526,144 bytes.
[Before](keyboard-gesture-memory-before.txt) and
[after](keyboard-gesture-memory-after.txt) RSS/PSS were unchanged at
24,548/15,929 KiB. This is a short bounded observation, not a long-term leak test.
