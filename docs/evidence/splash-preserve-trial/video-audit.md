# Camera timing audit: preserve-image automatic boot

Source video: [20260922T214204Z-preserve-image-automatic-boot.mp4](20260922T214204Z-preserve-image-automatic-boot.mp4)

SHA-256: `c9ef74213899144262cb22b4575ca988456d216460d051b6bc1897e0cf9e22b8`

The source is H.264, 1920x1080, 30/1 fps, and 120.000 s. These properties were
checked with:

```sh
ffprobe -v error \
  -show_entries format=duration:stream=index,codec_name,width,height,r_frame_rate,avg_frame_rate \
  -of default=noprint_wrappers=1 \
  docs/evidence/splash-preserve-trial/20260922T214204Z-preserve-image-automatic-boot.mp4
```

## Method

I used timestamped FFmpeg extraction and numeric timestamp order. The broad
review used 5-second samples:

```sh
ffmpeg -y -hide_banner -loglevel error \
  -i docs/evidence/splash-preserve-trial/20260922T214204Z-preserve-image-automatic-boot.mp4 \
  -vf 'fps=1/5,scale=480:-1,tile=5x5' -frames:v 1 \
  /tmp/splash-audit-frames-214204/contact-0-120.jpg
```

The onset review used 2 fps from 0 through 15.5 s, then 10 fps from 10.0
through 12.4 s. The handoff review used 1 fps from 60 through 95 s, then 5
fps from 69.0 through 73.8 s. Individual frames were also extracted at
11.2, 11.3, 11.4, 11.5, and 11.6 s, and at 71.0 through 72.6 s in 0.1 s
steps, using this timestamped extraction form:

```sh
ffmpeg -y -hide_banner -loglevel error -ss <timestamp> \
  -i docs/evidence/splash-preserve-trial/20260922T214204Z-preserve-image-automatic-boot.mp4 \
  -frames:v 1 -vf scale=640:-1 /tmp/splash-audit-frames-214204/t-<timestamp>.jpg
```

At 30 fps, the nominal source frame index is timestamp multiplied by 30;
the indexes below are therefore approximate labels for the requested camera
timestamps, not a claim about FFmpeg seek rounding.

## Observations

| Requested time | Nominal frame | Camera-visible result |
|---:|---:|---|
| 11.3 s | ~339 | dark |
| 11.4 s | ~342 | first faint logo |
| 11.5 s | ~345 | clear logo |
| 11.6 s | ~348 | clear logo |
| 71.0 s | ~2130 | logo visible |
| 71.1 s | ~2133 | logo visible |
| 71.2–72.3 s | ~2136–2169 | sampled frames dark |
| 72.4 s | ~2172 | shell bar first visible |
| 72.5–72.6 s | ~2175–2178 | shell visible |

The first visible logo is bracketed by the 11.3 s dark sample and the 11.4 s
faint sample, with a clear logo by 11.5 s. The camera-visible dark handoff
interval is approximately 1.1–1.2 s, from the last sampled logo at 71.1 s to
the first sampled shell at 72.4 s. This is camera timing only: it is not an
electrical timing measurement, and sparse samples do not establish what
happened between samples or exclude a shorter sub-frame blackout.

The sampled frames between the onset and handoff retain the logo, but this
does not prove uninterrupted rendering throughout that interval. After the
handoff, the oblique recording shows the portrait shell bar and terminal
without an obvious recurrence of the earlier wrap/recolor defect. Glare,
reflections, and perspective prevent calibrated geometry or color claims;
the native comparison image is [shell-native.png](shell-native.png).

## No-logo fallback

The no-logo fallback video is
[20260922T215021Z-preserve-kernel-no-logo-fallback.mp4](20260922T215021Z-preserve-kernel-no-logo-fallback.mp4).
Its SHA-256 is
`3c396c1d8dc1a0201cc5565d5cc669f1df472ca1112620c52a7d006533b739bb`.
`ffprobe` reports H.264, 1920x1080, 30/1 fps, and 100.000 s. I reviewed a
5-second cadence contact sheet and a late frame extracted with:

```sh
ffmpeg -y -hide_banner -loglevel error \
  -i docs/evidence/splash-preserve-trial/20260922T215021Z-preserve-kernel-no-logo-fallback.mp4 \
  -vf 'fps=1/5,scale=480:-1,tile=5x5' -frames:v 1 /tmp/splash-audit-2156/no-logo.jpg
ffmpeg -y -hide_banner -loglevel error -sseof -2 \
  -i docs/evidence/splash-preserve-trial/20260922T215021Z-preserve-kernel-no-logo-fallback.mp4 \
  -frames:v 1 -vf scale=960:-1 /tmp/splash-audit-2156/no-logo-late.jpg
```

The late camera frame shows a readable Linux console on a dark background in
the portrait panel. The text rows and panel geometry appear normally oriented;
there is no obvious horizontal wrap or magenta/color-swap defect in this
oblique, glare-affected frame. This is a visual observation, not calibrated
scanout or color evidence.

## Color page-flip capture

The finalized page-flip video is
[20260922T215603Z-preserve-colors-pageflips.mp4](20260922T215603Z-preserve-colors-pageflips.mp4).
Its final SHA-256 is
`60862df429822d6913fa6e7534fe98a2ce0a2dcd631db2479371cfecf8b4a025`.
`ffprobe` reports H.264, 1920x1080, 30/1 fps, and 42.000 s. The recorded
camera command is preserved in the capture manifest; the review contact sheet
was generated with:

```sh
ffmpeg -y -hide_banner -loglevel error \
  -i docs/evidence/splash-preserve-trial/20260922T215603Z-preserve-colors-pageflips.mp4 \
  -vf 'fps=1/3,scale=480:-1,tile=5x3' -frames:v 1 \
  /tmp/splash-audit-2156/colors-0-42.jpg
```

This samples nominal camera times 0, 3, 6, ..., 42 s. The physical panel
shows the temporary Foot page changing from RED at approximately 6–12 s, to
GREEN at approximately 15–21 s, to BLUE at approximately 24–30 s, then back
to the terminal by approximately 33–39 s. The color transitions are visible
in the camera contact sheet, so this capture demonstrates that the physical
scanout can change through multiple page flips after handoff. It does not
measure page-flip latency, vblank timing, or uninterrupted behavior between
the sparse samples; glare and the oblique camera angle also limit color
interpretation.

## Keyboard contrast and row geometry checks

I compared [keyboard-contrast-physical.jpg](keyboard-contrast-physical.jpg)
(`d65287480b85f3ab3130d6796587fb5b4cc7fdbfe4beb27278441af8cbc254a1`) with
[keyboard-contrast-native.png](keyboard-contrast-native.png)
(`fc9e766b661bff2840f225dc401526c1edf0c4436d83b3bd4ef40b3266ad6816`), and
also compared [rows-physical.jpg](rows-physical.jpg)
(`356f7a499f10fcd9b7a488bcac72e27e1136e5cf57c783306c1e73c1df2df5`) with
[rows-native.png](rows-native.png)
(`1a888057276d30433c81d4a7866ddf19e2c2640737ff4a46c11f9f114603fabd`).

The physical keyboard frame contains a bright cyan/white region along the
lower part of the panel, in the expected location for the native keyboard.
The camera does not resolve the key grid or labels, so this supports only
that a bright lower keyboard-like region is visible. Its apparent height
cannot distinguish perspective compression from partial camera framing or
cropping. The rows comparison shows the red, green, and blue test bands in
the expected top-to-bottom order, but it is not a keyboard geometry proof.
Neither pair establishes touch accuracy, full-panel coordinate mapping, or
that every native key is physically visible.
