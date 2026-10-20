# Rejected first landscape capture

Installed source221bbcf3 at 1280×800 normal, one Foot, 24 direct IPC drags,
35moves/nominal 0.7 s motion and 0.8 s rest. Journald reported61 suppressed shell
messages. Input IDs609–612 (including gesture 17 release) are missing; the
collector correctly emitted `INCOMPLETE` with an empty run manifest. This
capture is preserved for diagnosis and is not a measured baseline or acceptance.
`cleanup.json` confirms benchmark stopped, Home requested, original one app
and output preserved, both services active. The retry lengthens rest to1.6 s;
no compositor, resolution, transform, input route or motion sample count changes.
Only allowlisted numeric diagnostic rows are retained in `capture.log`.
