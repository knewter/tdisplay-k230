# Shell feature media

These assets come from the physical K230. Native screenshots use Grim;
camera clips use host FFmpeg and `/dev/video0`. Each clip has an adjacent
JSON manifest with source settings and interaction provenance. A provenance
label records the method; it does not by itself prove a finger touched glass.

| Feature | Screenshot | Presentation video | Interaction |
| --- | --- | --- | --- |
| Nix / Neofetch | [Screen](neofetch/screen.png) | [MP4](neofetch/demo.mp4) | Launched by Sway IPC; camera records the physical panel |

The timestamped MP4 in the Neofetch directory is the original camera view.
`demo.mp4` rotates it 180 degrees for reading and converts full-range camera
pixels to limited-range H.264/yuv420p. Both copies retain real-time playback.
The clean screenshot is a separate compositor capture, not a video frame.

Terminal use, keyboard interaction, launching, switching, terminal recovery,
and system-control demonstrations are still being recorded; they are not
claimed complete by this index. Final evidence must also distinguish fresh
image behavior from the temporary service overrides used during first light.
