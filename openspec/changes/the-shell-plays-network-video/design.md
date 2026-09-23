## Context

The existing shell is Sway/Pixman at 568x1232 with Foot, a native Apps launcher,
an on-screen keyboard, and runtime-only Wi-Fi credentials. The committed BBB trial
shows that the target can decode H.264 in software through `wlshm`, but 480x270
recorded 106 video-output drops and 640x360 recorded 509; these are useful baselines,
not smooth-playback claims. `docs/evidence/mvx-v4l2-audit.md` identifies the MVX V4L2
boundary, while no complete MVX-to-panel playback is yet grounded.

## Goals / Non-Goals

**Goals:**

- Make the software player and its FFmpeg behavior reproducible in the Nix image.
- Reuse the existing terminal bridge and Apps catalog so video has no second session model.
- Provide safe touch recovery and an explicit software-versus-MVX test switch.
- Make every playback claim traceable to source representation, decoder counters,
presentation timing, and physical/native evidence.

**Non-Goals:**

- Persistent Wi-Fi credentials, network-manager UI, offline media download, or a
media library.
- Audio acceptance bundled into video acceptance.
- A compositor replacement, GPU renderer, or a claim that CPU decode is smooth at
30 fps before timing evidence exists.
- Treating the KPU as a video decoder or claiming MVX success from device-node
presence alone.

## Decisions

1. **Use the existing terminal/launcher path.** Add one controlled desktop entry
through the current catalog and Foot bridge. This keeps input, Back/Home, process
lifecycle, and error recovery in already-tested shell paths. A separate full-screen
Wayland player would duplicate focus and return behavior.

2. **Ship a software baseline first.** Pin the mpv/FFmpeg derivations and explicit
`wlshm`, software-H.264, and audio settings. The 480x270 BBB representation is the
initial reproducible baseline because the supplied trial measured it; 640x360 remains
a comparison profile with its observed drops.

3. **Keep MVX opt-in and evidence-gated.** Add a separate command/profile that
selects the audited V4L2 decoder only after device discovery, format negotiation, and
frame delivery are observable. On failure, return to software playback and label the
result as fallback. Do not make the default image depend on a successful MVX path.

4. **Use runtime-only source configuration.** A public URL may be supplied by the
operator or a documented test wrapper. Private network material stays in the existing
root-owned `/run` procedure and never enters desktop files, Nix expressions, argv,
or the store. The player entry must not become a general network installer.

5. **Separate three evidence layers.** Host/Nix evidence proves derivations and
closure. Console evidence proves decoder/output counters and CPU/cache behavior.
Native screenshots and camera frames prove visible content, but only synchronized
presentation timing over at least 30 seconds can support a sustained-presentation
claim. Audio gets its own measured result or remains explicitly unverified.

6. **Prefer bounded controls over playback sophistication.** The first controls are
launch, stop/quit, Back/Home return, and recovery after EOF/network/decoder failure.
Do not add seek UI, thumbnails, playlist state, or background playback until the
basic lifecycle is stable on the narrow portrait panel.

## Risks / Trade-offs

- [Software decode cannot meet the source cadence] -> keep 480x270 as the baseline,
record drop counters honestly, and do not advertise 30 fps without presentation proof.
- [MVX negotiation or output conversion fails] -> keep the path opt-in and retain the
known-good software fallback.
- [A terminal process survives navigation] -> track the launched PID/session and
verify Back/Home, EOF, and failed-network cleanup on the board.
- [Audio adds an unmeasured failure surface] -> disable it for video acceptance until
separate decode, output, and physical-audio evidence exists.
- [Remote DASH changes or becomes unavailable] -> preserve the exact manifest,
representation, date, and cache/provenance in every trial, and use a local test
fixture only as a separate deterministic test.
- [Presentation timing is confused with mpv counters] -> require a synchronized
frame/presentation method and label native screenshots as visual samples only.

## Migration Plan

Build the player and launcher entry behind the existing shell image option. Validate
host closure and desktop discovery before flashing. On the board, run the software
baseline first, then the optional MVX profile, leaving the ordinary shell configuration
unchanged on failure. Roll back by removing the video package and entry; existing Apps,
Help, Terminal, Monitor, keyboard, and Home behavior remain the recovery path.

## Open Questions

None that change the bounded first implementation. The exact MVX format/output
negotiation and audio method can be selected during the evidence task after the
software baseline is reproducible.
