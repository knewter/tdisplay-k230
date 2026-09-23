# Installed video control checks

Observed 2026-09-23 by the coordinator on the physical board, with **injected touch**, not a physical finger.

The installed image was `/nix/store/d7r354bnsnffxnwnqblaf3raqvd15190-k230-sd-image.img`, built from source `03cbade`. The installed controller and mpv are the same production paths recorded in [installed-app evidence](../installed-app/README.md). Boot ID: `506e9b30-5617-4ecf-9c88-95e50dd5113e`.

`check.py` was transferred unchanged to `/run/video-controls-check.py` and executed using `/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3`. It launches `k230-video.desktop` through the installed catalog/Foot bridge, verifies advancing media time and PID/start-time/UID ownership, then exercises three independent sessions. The script requires the already running virtual touch device and `/run/inject-tap.sh`; it is a record of this exact board procedure, not a portable test runner.

| Case | Trigger | Observed result |
| --- | --- | --- |
| Stop | Injected Windows, then Stop button | Controller/player group absent; runtime state and IPC socket removed |
| Home | Injected Windows, then Home button | Same cleanup; existing `k230-terminal` focused |
| EOF | IPC seek to 632 seconds of the 634-second source, then natural end | Fresh `Exiting... (End of file)` marker; same cleanup |

All three cases passed. EOF was reached after seeking near the end; this is not a claim that the entire movie played uninterrupted. The script's final safety Stop runs after recording each case's cleanup assertions and therefore cannot turn a cleanup failure into a pass. `results.json` retains only allowlisted process/media/control data.

These checks add Stop/Home/EOF proof to the prior Back trial. Network errors, MVX fallback, and the final integrated-image regression remain separate gates. No physical audio or optical smoothness claim follows from this result.
