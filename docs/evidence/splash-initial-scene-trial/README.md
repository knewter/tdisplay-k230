# First compositor logo scene trial

The first opt-in Sway scene-seed image no longer reproduces the earlier
approximately 1.1–1.2 second dark interval in the sampled handoff frames.
It also exposes a cleanup defect: the seed is logged, but its removal is not.
The diagnostic source `06cd7a8` incorrectly required a top-layer bar, whereas
our normal Swaybar uses a bottom-layer surface with namespace `panel`.
This image is a partial result, not the daily default or final acceptance.

[Build provenance](build.txt) identifies the exact image and compositor.
[Flash transcript](image-flash.txt) records a routine full write, reset, Linux
boot and USB-host checks passing, with full readback skipped. No saved home
state was restored. [Runtime inspection](inspection.txt) records active shell,
seatd and firewall, the successful immutable DRM-owner release, the initial
scene seed, and first-enable VO/DSI preservation.

The [automatic boot recording](20260922T221824Z-initial-scene-automatic-boot.mp4)
and [independent sampled-frame audit](video-audit.md) place the visible
logo-to-shell transition at about 72.6–72.7 seconds. Dense samples do not
contain a dark frame at that transition. This does not exclude a shorter
sub-frame event, and it is a warm-reset observation rather than a battery
power-on test. The [late physical image](shell-physical.jpg) and
[native screenshot](shell-native.png) show the resulting shell.

The follow-up code uses public Wayland surface readiness and Swaybar's actual
mapped `panel` bottom-layer surface before matching a compositor presentation
event. That corrected code requires its own build and physical recording;
this video does not prove it was deployed.

## Invalid-asset behavior

A temporary runtime-only service override first points Sway at a missing
initial-scene asset and then at a three-byte file. The
[missing-file inspection](invalid-missing-inspection.txt) and
[wrong-size inspection](invalid-size-inspection.txt) show specific diagnostics
while the shell remains active. Native images
[after missing file](invalid-missing-native.png) and
[after wrong size](invalid-size-native.png) record the resulting shell.
This tests Sway's optional asset loader, not U-Boot's missing-logo path.

The override and temporary file are removed in `invalid-restore.txt`;
`invalid-cleanup.txt` records the restored immutable environment. These runtime
experiments do not change the image's defaults or retain user configuration.

Sampled camera frames from the invalid-asset recording at approximately 20,
45 and 70 seconds also show the portrait shell after the restarts. They do
not establish a seamless restart; runtime display teardown is expected here.
