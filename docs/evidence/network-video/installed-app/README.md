# Video launched from the integrated Apps entry

On 2026-09-23 UTC the operator injected two Next button taps and a tap on
Video in the installed launcher. The [native Apps frame](apps-entry.png)
shows the entry on page 3. The installed `k230-desktop-catalog list` reported
`k230-video.desktop`, label `Video`, terminal flag `1`. The app opened through
the Foot terminal bridge; controller PID 12619 owned mpv PID 12625, both UID
1000, with recorded `/proc` start times. This is injected board input, not a
real-finger video launch.

The installed system was
`/nix/store/568vf3220mpvdmgjgfnz5ln0qn09934r-nixos-system-nixos-26.11.20260919.20b1ddd`,
from source `03cbade`; see [flash/boot evidence](../integration-board-boot.md).
The player is the pinned mpv store path in [host evidence](../integration-host.md).

## Sustained playback observation

[The board-local observer](observe.py) sampled only allowlisted mpv IPC
properties and process identity/accounting every five seconds for 100 seconds.
[Its raw JSON](observation.json) retains all 21 samples, including initial
unavailable properties during startup. Every sample verified controller and
player UID/start times and excluded zombie states.

At elapsed 10 seconds, media time was 1.066667 seconds; at elapsed 100 seconds,
it was 91.033333 seconds. Every intermediate available media-time sample
advanced. The same player/controller remained alive. This proves healthy
playback beyond the former 90-second lifetime concern, not merely a surviving
process. No observer timeout or artificial EOF was sent to the player.

The selected source was public Big Buck Bunny DASH track 6, H.264 480×270,
30 fps, with software decoding, `wlshm` output and audio disabled. At the last
sample mpv reported zero decoder drops, one output drop, no cache pause, and
456.833333 seconds of cached media. Player CPU across the 90-second interval
was approximately 45.11% of one CPU, calculated from the raw utime/stime delta
with recorded `CLK_TCK=100`. It excludes compositor and other processes.

This observation does not measure presentation timestamps. The separate
[presentation instrumentation](../README.md) and final software/MVX comparison
remain distinct from these lifecycle samples.

## Native and physical images

[Native playback](playing-native.png) shows the decoded 480×270 movie in the
installed shell. [The eight-second physical camera clip](playing-camera.mp4)
and [camera frame](playing-camera.jpg) show the movie on the panel. The camera
is oblique and lower text is soft; these establish visible content, not perfect
cadence, exact colors, optical latency, or audio output. The clip is cropped
around the display and contains no legs. [Provenance and artifact hashes](provenance.json)
record source, capture and transformations; binary hashes are registered as DATA.

Big Buck Bunny © 2008 Blender Foundation, [CC BY 3.0](https://peach.blender.org/about/).

## Back recovery

The operator injected Windows on the persistent bar. The resulting
[controls frame](controls-native.png) shows Stop, Home and Back while video
continues. An injected Back tap then stopped playback. The
[sanitized console transcript](back-cleanup.txt) verifies controller/player PIDs
are gone, no mpv remains, the state file and IPC socket are absent, and `shell`,
`seatd` and `k230-wifi` remain active. The five-second observation after the tap
is not a measured shutdown-latency bound.

This run does not close independent Stop, Home, EOF, network-failure, MVX
fallback or final regression gates. It also does not claim the later launcher
cancellation fix was installed in this image.
