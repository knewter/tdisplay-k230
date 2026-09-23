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
interruptions. The corrected controller was then built and imported as
`/nix/store/izf7j0kyv5sqjjv0698v2vm8rglnd6dp-k230-video-session` (source `972a397`).
The same board trial passed: after IPC media time exceeded two seconds, HTTP
closed at 1,310,720 of 5,089,683 advertised bytes; the controller returned 2 and
removed the player group, state, socket and runtime playlist before safety Stop
(`after-board.json`). `check-board.py` is the executed procedure. Its no-EOF-log
field is not independent proof for private inputs, whose diagnostics are not
persisted; the deliberately incomplete response, observed progress, exit 2 and
cleanup establish this case. The pre-existing image stayed installed. Final-image
regression remains open.
