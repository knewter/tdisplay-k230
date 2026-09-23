# Big Buck Bunny software streaming trial

This is a bounded playback baseline for the K230 shell. It does not claim a
production video player, sustained 30 fps, audio support, or hardware decode.
The board was operated by the primary agent; this evidence audit used only the
provided transcripts and media.

## Source and attribution

The stream was the public Akamai DASH manifest
`https://dash.akamaized.net/akamai/bbb_30fps/bbb_30fps.mpd`, using Big Buck
Bunny. The film is the Peach open movie by the Blender Foundation and is
licensed under Creative Commons Attribution 3.0; attribution is retained here:
(c) 2008 Blender Foundation / www.bigbuckbunny.org,
[official project attribution](https://peach.blender.org/about/).

The trial worktree was at source commit `45e5e1a` (`Add a bounded software video
probe and quiet radio logging`). Playback used the target's RISC-V `mpv`
derivation with `--vo=wlshm --hwdec=no --audio=no`; the 270p launch also used
`--profile=sw-fast`, `--vid=6`, `--start=45`, `--length=30`, and a 568x320
window. Audio was intentionally disabled. The source was remote DASH, so these
results include network/cache behavior.

## Results

The 640x360 trial selected H.264 video stream 7 (30 fps, 1255 kbps) and used
`wlshm` software output. It recorded zero decoder drops and 509 video-output
drops by the end of the bounded roughly 40-second observation, when playback
was at about 1:09. The bounded run ended with `Exiting... (End of file)` after the requested
40 seconds; a concurrent DASH read reported `Immediate exit requested` during
shutdown. This is a
software-rendering stress result, not a claim that 360p is smooth.

The final 480x270 trial selected H.264 stream 6 (30 fps, 760 kbps), again with
software H.264 and `wlshm`. It reached about 1:14 with **0 decoder drops and
106 video-output drops**, and a final demuxer cache of about 96.97 seconds. The
native screenshot [270p-native.png](270p-native.png) shows the decoded frame,
launcher bar, terminal title, and keyboard.

The tested boot had only CPU 0 online and present. The CPU probe captured four
complete process snapshots. `CLK_TCK=100` and `PAGESIZE=4096` were verified through
the board console. Raw `/proc` samples are preserved in
[270p-cpu-console.txt](270p-cpu-console.txt). Across the recorded interval,
mpv advanced from 851 to 1,134 user ticks and 99 to 111 system ticks; Sway
advanced from 650 to 740 user ticks and 86 to 93 system ticks. Using the
recorded timestamps and `CLK_TCK=100` gives a rough sampled average of 57% mpv,
19% Sway, and 76% combined CPU occupancy; this is an interval estimate, not a
scheduler or whole-system benchmark.

The 270p status and the 360p status are preserved with terminal control sequences removed in
[270p-final-status.txt](270p-final-status.txt) and
[360p-status.txt](360p-status.txt). The automated 270p physical camera trial
was inspected before selection. The four-second cropped clip and still contain
only the device display and no legs or other private scene content:
[270p-physical-clip.mp4](270p-physical-clip.mp4) and
[270p-physical-frame.jpg](270p-physical-frame.jpg). The crop was made from
`camera.mp4` with ffmpeg:

```text
ffmpeg -ss 4 -t 4 -i camera.mp4 -vf crop=900:600:250:130 -c:v libx264 -pix_fmt yuv420p -an
ffmpeg -ss 5 -i camera.mp4 -frames:v 1 -vf crop=900:600:250:130
```

The camera media is not copied into the repository; the selected derivatives
are the privacy-bounded evidence assets.

## Limits

The status counters measure mpv's decoder and video-output counters, not
panel scanout or human-perceived smoothness. The native screenshot is a
compositor capture, while the camera crop establishes physical display output
but is oblique and not a readability calibration. The trial leaves network
availability, DASH behavior, and the software-only decode path in the result.
