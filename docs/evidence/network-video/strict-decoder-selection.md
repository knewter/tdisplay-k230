# Strict MVX selection before controller fallback

The installed-image [failure trial](recovery-check/README.md) exposed a distinction between player-internal decoder fallback and the controller's software profile. The public runtime log [excerpt](strict-decoder-before.txt) records MVX initialization failure followed by 640x360 wlshm output in the same player. The controller did not select its 480x270 software profile. The unavailable decoder's timing/track options therefore survived the internal fallback; this is not accepted recovery behavior.

Pinned mpv 0.41.0 [`mp_select_decoders`](https://github.com/mpv-player/mpv/blob/v0.41.0/common/codecs.c#L56) splits the selection on commas and stops appending unlisted decoders only for a standalone `-` entry. The [`--vd`/`--ad` manual](https://github.com/mpv-player/mpv/blob/v0.41.0/DOCS/man/options.rst) documents this shared selection behavior. The controller now requests `--vd=h264_v4l2m2m,-`. An MVX initialization failure can then exit that child and invoke the existing explicit software profile. Merely appending a hyphen to the decoder name would be an unknown decoder and would not disable fallback.

Source revision: `7984a58`. `K230_VIDEO_MPV_DECODER_PROBE=/tmp/k230-bbb-270p/camera.mp4 python3 -m unittest tests.test_video_session` passed all 19 tests on the host. The optional real-mpv test obtains the decoder selection from the production controller, feeds a local H.264 sample to host mpv with null output, and checks a nonzero decoder-init failure with no selected streams. It assumes a host without a working MVX device; it is not board decoder proof. Other lifecycle tests cover controller fallback and Stop behavior with controlled child processes.

`nix build --no-link --print-out-paths .#toplevel .#sdImage --option max-jobs 1 --option cores 8` completed successfully. The new image and source-built controller still require board recovery and healthy-MVX playback checks before the recovery gate can close.

Built output: `/nix/store/gch5zzxlffr2ma2y6ynra2l89a9f8ikl-nixos-system-nixos-26.11.20260919.20b1ddd`.

Built output: `/nix/store/kd4hk8g7v635xr8jf1y7k7ms0jyzpx56-k230-sd-image.img`.
