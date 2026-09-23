# Installed network-error and decoder-failure checks

Observed 2026-09-23 on the physical board with the production installed controller and player from image `/nix/store/d7r354bnsnffxnwnqblaf3raqvd15190-k230-sd-image.img` (source `03cbade`). These are root-controlled failure injections with the player running as shell UID 1000, not physical-finger trials.

`check.py` was copied unchanged to `/run/video-recovery-check.py` and run with `/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3`. The exact procedure and allowlisted observations are retained here.

- **Network startup failure passed.** A shell-owned mode-0600 runtime playlist named a deliberately unavailable local endpoint. The production controller exited spontaneously with status 2; its process group, state, IPC socket and playlist were gone before the safety Stop ran. This proves this startup failure, not recovery from every mid-stream network outage.
- **MVX initialization-failure fallback did not pass.** The fixture temporarily removed access to `/dev/video0`. It observed the production MVX child but no software child with advancing playback inside the 45-second bound. This does not establish the cause; a controller marker, socket existence or decoder argv alone cannot prove successful fallback. Task 4.2 remains open.

The fixture restored the decoder device permissions in `finally`, called the normal Stop path, and the subsequent console check reported mode `660`. Its failed result is retained rather than converted into an acceptance claim. Follow-up must establish why the player did not enter verified software playback, fix the production behavior if needed, and repeat the bounded test.
