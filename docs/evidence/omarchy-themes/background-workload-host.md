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

This checkpoint intentionally fails the video arm after resource sampling:
the installed Rust wallpaper client currently rejects video selections, and
no wallpaper decoder or frame status is wired to this trial yet. The isolated
video consumer work must provide a generation-matched decoder and frame
contract before this mode can claim an animated wallpaper. An mpv app window
is not a wallpaper substitute. The baseline/static resource numbers are
useful host-testable schema, not on-device measurements or card-budget proof.

Focused host commands:

```sh
python3 tests/test_handheld_theme_trial.py
python3 tests/test_theme_background_metrics.py
python3 -m py_compile tools/handheld-theme-trial.py tools/theme_background_metrics.py
```

The fixture exercises pinned choices, a static resource arm, strict video
failure, baseline restoration, bounded process counts and sampled cgroup
math. No board, video presentation, real touch or performance result is
claimed; theme tasks 4.3 and 5.4 remain open.
