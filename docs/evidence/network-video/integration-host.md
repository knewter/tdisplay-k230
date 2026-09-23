# Integrated player: host proof

The source at `03cbade` builds the shell image, launcher, mpv and FFmpeg with
`nix build --option max-jobs 1 --option cores 8 .#sdImage .#touch-launcher .#video-player .#video-ffmpeg --no-link --print-out-paths`.
[Exact paths, image SHA-256 and closure sets](integration-host.json) record
30 added and 15 removed store paths compared with the current persistent-Wi-Fi
system, a net 23,886,968 NAR bytes. These are host build results; image installation
and physical acceptance are separate.

The image installs a `Terminal=true` Video desktop entry through the existing
Foot bridge. Its Python controller runs the pinned mpv and FFmpeg from
`nix/video-probe.nix`, with software H.264, `wlshm`, `sw-fast`, audio disabled,
480×270 geometry and public BBB DASH track 6. The source is
`https://dash.akamaized.net/akamai/bbb_30fps/bbb_30fps.mpd` (Blender Foundation,
Big Buck Bunny, CC BY 3.0). An explicit `run-mvx` command selects the measured
silent 30-fps demo profile, track 7, point scaling and the documented CFR
workaround. The empty-capture patch is not enabled in this image.

## Runtime URL boundary

Apps starts `k230-video-session run`; `k230-video-session stop` requests bounded
controller and child-group cleanup. Stop is also exposed in Windows; Home and
Back stop playback before returning to the existing shell controls. Healthy
playback has no arbitrary duration cutoff. Startup and network waits are bounded.

For a private source, provision a one-line playlist in
`/run/shell/k230-video.playlist`, owned by the session user with mode 0600, through
a private input/file channel. The player receives only its pathname. An explicit
`--url-file /run/shell/NAME.playlist` is also accepted; it must be a regular,
non-symlink, owner-only file inside that runtime directory. Do not put its
contents in a command argument, environment URL, Nix expression or desktop file.
The session consumes and removes the playlist when it finishes, cancels or fails.
Private-source player output is discarded so URLs cannot enter playback logs.
MVX is restricted to the public demo; private sources use software decode.

Tracked source and newly added closure files were scanned against the privately
preserved Wi-Fi PSK and supplicant SSID assignment without printing either value;
no protected material was found. Neither credential nor private media input is a
Nix build input. Existing Wi-Fi provisioning remains independent.

## Tests run

- `python3 -m unittest discover -s tests -p 'test_video_*.py'`: 24 passed,
  including actual descendant cleanup, startup cancellation, EOF/error cleanup,
  healthy playback beyond the startup limit, private-file validation and
  cancellation in the dead-child interval before MVX fallback.
- `python3 tests/test_touch_menu.py`: 7 passed, including Stop/Home and retained
  keyboard controls.
- `python3 tests/test_launcher_navigation.py`: 3 compiled suites passed,
  including the production-client fixture, with no dependency skip.
- `python3 tests/test_window_catalog.py` and `python3 tests/test_desktop_catalog.py`:
  3 passed each.
- `openspec validate --all --strict`: 20 items passed.

The host tests use fake player processes for deterministic lifecycle faults.
They do not prove video decoding, live Apps launch, network recovery or the final
image's sustained presentation. Those board tasks remain open.
