# Strict MVX failure returns to the software profile

Observed 2026-09-23 on the physical board. The unchanged installed mpv ran through source-built controller `/nix/store/krqszp7x14mi9xyyz0k6bp2p3ywvhkyn-k230-video-session/bin/k230-video-session`, transferred/imported with matching SHA256. Controller source is `7984a58`; the board still used the earlier image. These are controlled failure injections, not real-finger or final-image acceptance.

`check.py` was transferred to `/run/video-recovery-check-v2.py` and executed with the installed Python 3.14.7. The [earlier trial](../recovery-check/README.md) did not reach the explicit software profile because mpv silently selected a different decoder inside the MVX process. The [strict selector correction](../strict-decoder-selection.md) prevents that internal fallback.

Both cases now pass:

- A shell-owned mode-0600 runtime playlist pointing to an unavailable local endpoint produced spontaneous exit 2 and removed the player group, state, IPC socket and playlist before safety Stop.
- Removing access to `/dev/video0` caused the strict MVX child to fail. The same controller started a different software child, emitted its fallback marker, selected public BBB track 6 at 480x270, and advanced media time from 0 to 2.133333 seconds. Device permissions were restored as soon as the software child appeared. Normal Stop then removed both tracked child groups, the controller, state, and socket.

`results.json` retains PID/start-time/UID ownership, selected representation, decoded dimensions, advancement, and cleanup assertions. No process argv or private URL is retained. This proves recovery from the tested device-open/initialization failure. Healthy strict-MVX playback, longer comparison, final-image controls, and a post-start network failure remain separate gates.
