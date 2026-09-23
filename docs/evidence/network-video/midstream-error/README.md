# Midstream HTTP truncation is a recoverable error

On 2026-09-23 the board played a generated 480x270/30 fps H.264 fixture from a
loopback HTTP server. After IPC media time passed two seconds, the server closed
at 1,343,488 bytes while advertising 5,089,683. The production controller removed
its state, socket, player group and runtime playlist, but returned success because
mpv classified the truncated body as ordinary EOF (`before-board.json`).

The controller now drains player output with bounded nonblocking work, recognizes
pinned FFmpeg's explicit HTTP premature-body diagnostic, and reports a generic
interruption with exit 2. Runtime-source diagnostics remain memory-only and are
not copied to the public playback log. Normal EOF and unrelated decode warnings
retain their prior behavior. A transport failure does not trigger the MVX decoder
fallback. User cancellation still follows the normal cleanup path.

Host verification: 22 lifecycle tests passed, including the optional real-mpv
strict-decoder selector check. A real host mpv with null output and 20x speed
returned 2 for the truncated fixture and 0 for the complete fixture, with all
runtime files removed and private-source log empty (`host-results.json`). This
is a transport/lifecycle test, not board rendering evidence. The existing healthy
startup test now permits 500 ms interpreter startup while keeping its fake player
alive for one second; the old 100 ms allowance failed under concurrent host load.

Reproduce the synthetic fixture (FFmpeg-generated test pattern, no third-party
media or private URL):

```sh
ffmpeg -f lavfi -i testsrc2=size=480x270:rate=30 -t 30 -an \
  -c:v libx264 -preset ultrafast -g 30 -pix_fmt yuv420p \
  -movflags +empty_moov+default_base_moof+frag_keyframe /tmp/network-fixture.mp4
python3 docs/evidence/network-video/midstream-error/check-host.py /tmp/network-fixture.mp4
python3 -m unittest tests.test_video_session
```

The classifier is deliberately limited to the verified pinned HTTP diagnostic.
It does not claim to detect all malformed media or unknown-length live-stream
interruptions. Board validation of the corrected controller and final-image
regression remain open.
