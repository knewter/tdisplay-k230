# Final integrated image flash and boot

This is a sanitized board-coordinator record for the final integrated image.
It is derived from `/tmp/k230-final-image-status.txt` and the coordinator's
reviewed flash transcripts. The raw transcripts are deliberately not committed:
they can contain host network and device-identifying details. This record does
not reproduce private Wi-Fi configuration or inspect credential-file contents.

## Artifact and source

- Source revision: `03cbade499827b6dac43d55187e73d90186beb73`
  (`03cbade`), supplied by the coordinator and verified as a local Git commit.
- Flashed image: `/nix/store/d7r354bnsnffxnwnqblaf3raqvd15190-k230-sd-image.img`.
- Booted system: `/nix/store/568vf3220mpvdmgjgfnz5ln0qn09934r-nixos-system-nixos-26.11.20260919.20b1ddd`.

## Flash and boot result

The reviewed flash transcript reports a successful `flash.sh` exit status of
zero after writing 2,308,960,256 bytes. Its end-to-end duration, including the
script's confirmation and final sync, was 183.0 seconds (the script also
reports 182.819020085 seconds for the write). The board then booted the stated
system.

Full-device readback was intentionally skipped by policy. No home-directory
restore was performed.

## Sanitized runtime status

The status record reports three expected services active. It reports two
credential-containing runtime directories with mode `0700` and the persistent
credential file with mode `0600`, all owned by UID/GID 0. The Wi-Fi daemon
reported `wpa_state=COMPLETED`, and the public HTTP check returned `200`.

These status values establish a successful boot and credential-protected Wi-Fi
connection for this board run. They do not disclose, validate, or preserve the
network name, credential contents, network address, MAC address, or a raw
flash transcript.
