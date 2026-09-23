# Physical application and window controls

The [72.033-second camera clip](20260923T000357Z-apps-windows-real-touch.mp4)
records the user following an Apps/Windows/Terminal-recovery test. The
[operator report](operator-report.txt) says done; the
[camera audit](video-audit.md) distinguishes the steps actually visible from
any missing acceptance evidence. The [final native frame](after-test-native.png)
shows Monitor with the keyboard, so it is not proof of Terminal recovery.

The coordinator injected no touch or keyboard events. After the user reported
done, the verified FFmpeg process received SIGINT to finalize the recording;
the manifest distinguishes its planned maximum from actual duration. The
running image is identified in the preceding
[keyboard preflight](../shell-real-touch-keyboard/preflight.txt).

## Operator confirmation

After the camera review, the user explicitly confirmed Home recovery:
"home works too it's all good". This supplies the direct hands-on result for
the Home step that the video does not resolve. The earlier "done" followed
the requested Apps/Windows/exit/Home sequence. Keep these operator reports
separate from the audit's narrower camera claims; no further retake is
requested for the confirmed Home behavior. The
[previous-session journal](previous-session-actions.txt) records focus
commands but does not identify the tapped menu labels.
