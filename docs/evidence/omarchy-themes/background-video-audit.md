# Video background audit: tasks 2.2 and 2.3

Base `33cd23aa`, branch `bg-video`, 2026-10-17. Host evidence only. Nothing
here was run on the board; task 3.3 is untouched and stays open.

Task 2.2 and 2.3 were written as if `background_decode.rs` had no video path.
That is stale: commit `68badde1` shipped a decoder child process, a
visibility signal, status telemetry and transaction-aware slot retention.
`background_decode.rs` is still still-only and is still the right place for
nothing in this task. Line numbers below are for this branch after the change.

## Already existed (before this branch)

| Requirement | Where |
| --- | --- |
| Bounded decode: local regular files only, `mp4`/`m4v`/`mov`, at most 128 MiB, no symlink or non-canonical path | `nix/rust-shell-client/src/video_wallpaper.rs:21-72` (`local_video`) |
| Bounded decode: ffprobe must say h264 and at most 1920x1080, 800 ms probe timeout, 4 KiB output | `video_wallpaper.rs:74-134` (`probe`) |
| Bounded decode: output frame bound, one decoder thread, 8 fps, scaled and cropped to the surface, first-frame timeout 1.3 s | `video_wallpaper.rs:21-24,141-246` |
| Muted | ffmpeg run with `-an -sn -dn` and a single `-map 0:v:0`, `video_wallpaper.rs:164-180`; no audio path exists |
| Named failure categories instead of a crash (`unsupported-format`, `source-unavailable`, `source-bound`, `source-path`, `unsupported-codec`, `probe-*`, `output-bound`, `decoder-*`, `first-frame-timeout`) | `video_wallpaper.rs:50-246`, delivered as `VideoEvent::Error` and `failure()` |
| Pause = stop decoder child, keep last frame; resume = new child | `main.rs` `VideoPlayback::pause/resume` (`main.rs:454-490`) |
| Visibility pause on a certified, fresh, correctly sized, opaque-coverage signal; missing or stale means visible | `video_visibility.rs:20-51`; polled every 500 ms at `main.rs:7050`; compositor producer `nix/card-shell/adapter.c` |
| Reduced motion: no decoder is started and a running one is paused | startup flag `main.rs:6814` via `reduced_motion_enabled` (`main.rs:659`); start/pause/resume gates at `main.rs:2332,7070,7082,7098,7140` |
| Still fallback on decode failure: the failing decoder is dropped, `video_display = None`, the wallpaper draws the paired still | `main.rs:7110-7125`, `wallpaper_path = fallback_still(..)` at `main.rs:2171,6674,7265,7627`; the still is drawn with the generation's fit mode (default `crop`) |
| Status record reports `error` + category, `paused-covered`, `paused-reduced-motion`, `still`, `unsupported`, `playing` | `main.rs:7660-7685`, `video_status.rs` |
| Rollback retention and slot selection | `main.rs:283` (`resolve_video_slot`), `main.rs:2301`, unit-tested |

## Missing (found) and what this branch did

| Gap | Resolution |
| --- | --- |
| No `handheld-wallpaper` flake output | Added `nix/handheld-wallpaper.nix` and `packages.<system>.handheld-wallpaper`. See "Why not a separate decode crate" below. |
| No compatibility-report entry for a recognised-suffix-but-undecodable video. `tools/theme_activate.py` accepted `.webm/.mkv/.avi/garbage.mp4` silently as a background, and the user only found out at play time | `theme_activate.py` `video_diagnostic()` / `video_report_line()`: a line in the report's `unavailable` list, named with the decoder's own category, for theme assets and user overlays. Never fatal. |
| Pause and reduced-motion decisions were five hand-copied boolean expressions in the binary, untestable | One predicate, `video_visibility::should_decode(reduced_motion, covered)`, used at all five sites; unit-tested. |
| `fallback_still` lived in the binary, untested | Moved to `appearance::fallback_still`; test `video_selection_falls_back_to_the_first_still_and_never_to_a_video`. |
| Decoder failure categories and the stop/restart lifecycle had no test (only a fixture-gated happy path that silently returns when its env is unset) | `nix/rust-shell-client/tests/video_wallpaper_module.rs`: five tests against stand-in ffmpeg/ffprobe scripts driving the real `decode_loop`. |
| `tests/test_handheld_theme_backgrounds.py` named by the parent task but never created | Created, with `--video`. |

## Not closed, by design

- The live reduced-motion setting. `K230_SETTINGS_REDUCED_MOTION` is read once
  at shell start (`main.rs:6814`), so toggling reduced motion while a video
  plays takes effect when the shell restarts. Whether the Settings control
  restarts the shell, and so whether the spec's "reduced motion is enabled"
  scenario holds live, is <!-- UNVERIFIED --> and board-only (3.3).
- The compositor's real cover signal and the resulting pause/restore on glass.
  `certified()` is host-tested; the producer in `adapter.c` and the end-to-end
  pause are not (3.3).
- The codec check at report time is best effort. `theme_activate.py` runs ffprobe
  only when `K230_WALLPAPER_FFPROBE` is an absolute path in the helper's own
  environment. `nix/shell.nix:727-728` exports it for the shell wrapper only,
  so whether the board's theme helper sees it is <!-- UNVERIFIED -->; without
  it the report catches suffix and container problems, and the codec/size case
  is still caught at play time (named `unsupported-codec`, still shown).
- CPU, RSS, frame budgets and what the panel shows: 3.3. Video stays off by
  default.
- The real-decoder test uses the host ffmpeg (with libx264), not the board's
  minimal cross build, so it proves the invocation and framing, not the shipped
  binary.

## Why not a separate decode crate

The task asked for "its own isolated flake output" for decode in
`background_decode.rs`. The decode logic is `video_wallpaper.rs`, a module of
the shell client crate that shares `frame_bytes` and the appearance types, and
the only costly dependency is the minimal ffmpeg (`nix/video-probe.nix`). A
second Rust crate would copy code, not isolate it. The closest honest
equivalent is `handheld-wallpaper`: the ffmpeg/ffprobe pair the decoder child
runs, plus an `environment` file naming `K230_WALLPAPER_FFMPEG/FFPROBE`. It is
the same store path `nix/shell.nix` already uses, so its closure can be built
and sized on its own. Building it shows the decoder closure cross-builds; it
runs no decode.

## Commands run

See the task notes in
`openspec/changes/the-background-chooser-supports-fill-solid-and-video/tasks.md`.
