# Video audit: real-touch keyboard trial

The source is [`20260923T000200Z-keyboard-real-touch.mp4`](20260923T000200Z-keyboard-real-touch.mp4), SHA-256
`891ff11bac41d4153ed044baf6d72cfab2f78437187d5590b84239255f5db27c`.
`ffprobe` reports H.264, 1920x1080, 30/1 fps, and 85.033 seconds. The JSON
manifest records 180 seconds as the requested maximum and 85.033333 seconds
as the actual duration. The capture ended after the operator reported done and
SIGINT finalized the container. The manifest also identifies the interaction as operator-declared real touch;
that field is not itself proof of finger input.

## Camera observations

I reviewed the full recording at one frame per second and inspected the
show/typing portions at the native 30-fps cadence. The camera visibly records
a finger/hand contacting the panel at several points while the terminal remains
on screen. The opening frame shows the terminal with no legible keyboard keys.
Later frames show the hand over the lower display and a dim lower-screen region,
but glare, angle, and the hand prevent reliable key-grid or key-label reading.
The camera therefore supports visible hand contact and terminal state changes,
but does not independently establish each keyboard show/hide/show transition.

The native captures provide a clearer state check: [`during-test-native.png`](during-test-native.png)
and [`after-test-native.png`](after-test-native.png) both show the keyboard
visible. No native hidden-state capture is present in this directory, so the
complete show/hide/show sequence remains only partially evidenced by the
artifacts.

Representative physical frames are [`physical-keyboard-hidden.png`](physical-keyboard-hidden.png)
(video 0 s, SHA-256
`699a0eb71ddfd1a16cc438ba9476960cd64da7da64474ba81705b5d8fec17534`),
[`physical-keyboard-shown.png`](physical-keyboard-shown.png) (video 15 s,
SHA-256 `6930b7368e408187b3d9a320f608909aee2b93f8bfb6653c639f1fe65295f3ca`),
and [`physical-typed-output.png`](physical-typed-output.png) (video 80 s,
SHA-256 `7168cfc491aba317481d812179ef49c50ff4019a301c1002be40e843090035f9`).
The last frame is deliberately described as camera evidence of terminal text;
the text is too blurred there for character-by-character transcription.

## Input and text evidence

[`input-mapping-json.txt`](input-mapping-json.txt) identifies the Goodix touch
input and reports `send_events: enabled` with the identity calibration matrix
(lines 18–31). [`touch-events.txt`](touch-events.txt) contains real evdev
contacts from that device, including touch-down/up sequences and movement in
the lower device range (for example lines 107–176). This establishes that the
kernel/libinput path received physical-device contacts during the test. It
does not prove that every contact landed on the intended on-screen key.

The native after-test capture shows two commands: an initial `exho` command
that fails, followed by a successful `echo` command. Its visible argument and
output appear to be `1qazoplm`, using the letter `o`. This asymmetric string is
useful for detecting a rotation or mirror error, but it does not establish the
requested `1qaz0plm` string with a zero. The initial `exho` typo and this
letter-versus-zero discrepancy keep per-key accuracy/calibration open; treat
the successful follow-up as output evidence only.

The recording does not prove a full calibrated touch workflow, complete key
accuracy, or a power-on/cold-boot scenario.
