# Background workload sampler: host checkpoint

The reserved-board theme trial now accepts `--workload backgrounds` with a
private, explicit still/video selection and bounded duration. It verifies the
same workload artifact used by the static theme trial, previews and activates
the exact opaque background choice, samples the Sway plus persistent Rust
shell cgroups, and uses the existing `finally` restoration path. The result
records CPU microseconds, mean CPU cores, sampled process RSS and cgroup memory
peaks, sample count and elapsed time. It records no process command lines or
theme source paths. Incomplete RSS, wrong media kind, changed background ID,
or failed activation is a failed trial, never a missing-value pass.

The video arm now requires a private 0600 wallpaper status record matching the
selected generation and source-relative asset fingerprint, an unchanged
decoder process, advancing decoded/submitted/callback counters and timestamps,
and two different native captures. Missing or stale status fails closed and
still invokes restoration. A host fake exercises the success schema; the
installed Rust wallpaper client at this checkpoint still rejects video, so
there is no board playback pass. An mpv app window is not a wallpaper
substitute. The baseline/static resource schema is not an on-device or
card-budget measurement. Changing native captures and Wayland callbacks do
not establish panel presentation; the operator must review the private raw
captures and retain the physical gate.

Focused host commands:

```sh
python3 tests/test_handheld_theme_trial.py
python3 tests/test_theme_background_metrics.py
python3 tests/test_theme_background_status.py
python3 -m py_compile tools/handheld-theme-trial.py tools/theme_background_metrics.py tools/theme_background_status.py
```

The fixture exercises pinned choices, a static resource arm, strict video
failure, baseline restoration, bounded process counts and sampled cgroup
math. Status fixtures exercise privacy, source identity, restart, stalled
frames, and a simulated advancing video arm. No board, video presentation,
real touch or performance result is
claimed; theme tasks 4.3 and 5.4 remain open.
