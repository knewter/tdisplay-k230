# Video audit: real-touch system controls and reboot

The source is [`20260923T000520Z-system-controls-real-touch.mp4`](20260923T000520Z-system-controls-real-touch.mp4), SHA-256
`91880c8fa17a7933936e95327c51c5d6dc6820109864be059dc79eccd1271ebd`.
`ffprobe` reports H.264, 1920x1080, 30/1 fps, and 180.000 seconds.

## Camera observations

The recording begins with the running shell/monitor view. During the control
interaction, fingers are visibly placed on the panel while the monitor view is
active. The panel changes to a bright, overexposed state around video 46–49 s,
followed by a dark panel and the K230 boot logo around 50–55 s. The camera
exposure and glare do not establish the bright state's UI structure or make
the words “Power off”, “Cancel”, “Reboot”, or “Reboot now” legible. The footage
therefore supports the user-directed touch sequence followed by a reboot,
while the exact confirmation labels and earlier cancellation choice remain
unverified by camera text.

The later recording returns to the shell view. Representative physical frames
are [`system-pre-touch.png`](system-pre-touch.png) (video 0 s, SHA-256
`d8323e6e649fe56333be64aab1ed9c36ce8884ac8651b1aeca5f0917dcf71f79`),
[`system-boot-logo.png`](system-boot-logo.png) (video 55 s, SHA-256
`c4ef2ed1c0d302148e97350183116b889a00892b90fe68b9936d57f57225e294`), and
[`system-post-reboot.png`](system-post-reboot.png) (video 170 s, SHA-256
`378020ceb726f240276649c34bfc646c22b9f141386ed2be3e8a68d90fd36493`). The
middle frame is the clearly visible boot-logo state; the preceding bright
state is not classified as a particular UI page.

## Corroborating reboot evidence

[`reboot-console.txt`](reboot-console.txt) records the shutdown and reboot
without injected serial commands. [`post-reboot.txt`](post-reboot.txt) reports
boot ID `8915db67-9428-4b87-95fa-f83f075bc7cf`, active `shell`, `seatd`, and
`firewall`, and Sway's initial splash seed/removal. The native returned-shell
capture is [`after-reboot-native.png`](after-reboot-native.png). Together with
the late camera frames, these establish return to a working shell after the
control-triggered reboot.

This is a warm, touch-triggered reboot with host cables attached. It is not a
power-on, battery, or standalone cold-boot test, and the camera does not prove
finger calibration or exact hit targets.
