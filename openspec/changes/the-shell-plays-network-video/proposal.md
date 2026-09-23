## Why

The handheld can now prove a bounded remote Big Buck Bunny stream through a temporary mpv probe, but video playback is not part of the Nix image or Apps surface. The current evidence shows software H.264 with `wlshm` is usable as a baseline at 480x270, while 640x360 incurs substantial video-output drops; the project needs a reproducible player configuration and honest hardware acceptance before presenting network video as a shell capability.

## What Changes

- Add a reproducible Nix video-player configuration built into the selected image, with mpv/FFmpeg software playback and an explicit hardware-decoder experiment path for the K230 MVX V4L2 device.
- Add a visible terminal video entry to Apps and define touch-safe launch, Back/Home recovery, stop, and failed-network behavior.
- Preserve runtime-only network credentials and URLs; do not add a network manager, stored Wi-Fi secret, or media installer.
- Record a software baseline and a separate MVX hardware baseline, including source stream, selected representation, audio setting, decoder path, frame counters, cache, CPU samples, and physical presentation evidence.
- Keep audio acceptance separate from video acceptance when audio is not measured or is disabled.

## Capabilities

### New Capabilities

- `runtime/video`: reproducible network video playback, decoder selection, controls, and evidence requirements for software and MVX paths.

### Modified Capabilities

- `runtime/shell`: Apps exposes the video player and the user can launch, stop, return Home/Back, and recover from a failed playback or network attempt without an external keyboard.

## Impact

The change affects the Nix shell image, mpv/FFmpeg package configuration, the native launcher catalog or terminal bridge, and touch/menu controls. It adds no kernel or device-tree requirement for the software baseline; the optional MVX path depends on the existing V4L2 device and requires physical-board evidence. The existing Wi-Fi runtime-only secret procedure remains the network boundary. The current Big Buck Bunny and `docs/evidence/mvx-v4l2-audit.md` records provide initial grounding; new-player and successful hardware-presentation requirements begin unverified.
