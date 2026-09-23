# Card capacity and boot-time growth

## Original capacity limit

The read-only commands in [preflight.json](preflight.json) found a
127,934,660,608-byte card with a 117,440,512-byte boot partition and a
2,173,693,952-byte root partition. Only 77,070,336 filesystem bytes were
available. The built RVV system added 16 paths / 112,720,944 NAR bytes relative
to the running normal system, so it did not fit. The original audit changed
neither the installed system nor storage. Its 62 unrooted store paths were
reported, not collected.

The guarded system growth implementation and seven actual disposable RISC-V
QEMU filesystem cases are described in [implementation.md](implementation.md).
[image-build.json](image-build.json) identifies the complete system and compact
2,308,960,256-byte image. QEMU is separate from physical-board evidence.

## Physical trial preparation

[staging.json](staging.json) preserves an unexpected staging failure: the card
ran out of **inodes**, despite available bytes. Only this trial's failed partial
`system-path` import was removed. `nix-store --optimise` then shared 8,599
identical files, reported 92.1 MiB saved, and allowed the complete closure import
to succeed. This was an operator preparation step; no new garbage-collection
policy or automatic deletion service was added.

[board-selection.json](board-selection.json) identifies the deployment method:
the complete system closure from the built image was imported and its exact
boot files selected on the existing compact root. All eight selected boot-file
hashes match the image. The kernel and initrd were already identical; only
`bootargs.txt` and `k230-tdisplay.dtb` needed replacement. Their old contents
remain under `/var/lib/k230-root-growth-evidence/` with `.before` suffixes, and
the prior Nix system generation remains available. This was **not a full-image
reflash** and did not restore a home directory or manually resize the root.

The preserved recovery image is
`/nix/store/b384ag314xp1gprqy3i5h7sbsci3fmm0-k230-sd-image.img`, pinned with a host
GC root. Its SHA256 still matches the previously tested artifact in
[the offline Wi-Fi image evidence](../offline-wifi-image/README.md):
`c510362955d208bc449fcb62f9d419e597c337e873512eb4f95e65c84b00f867`.
The normal system image was also rebuilt at its original store path; its new
filesystem-container bytes do not match the historical image checksum, so it
is not substituted for the byte-verified recovery artifact above.

[board-before.json](board-before.json) records the physical compact layout,
root/boot identity, MBR boot-code hash, firmware-gap hash (bytes 512 through
4 MiB), all eight boot-file hashes and a public root-file sentinel. The baseline
was captured **after** deliberate boot selection and **before** reboot/growth.
It confirms the old system still running, the new system selected, normal shell,
Wi-Fi association and HTTPS over `wlan0`, and protected credential permissions.
The credential contents, network names and private addresses are never emitted
by the checker and never enter the repository.

The first checker attempt is retained as
[board-before-control-path-failure.json](board-before-control-path-failure.json).
HTTPS succeeded, but its WPA association query used the wrong client socket
location. The corrected checker uses both of the service-specific control and
client paths documented by the credential procedure. The failed report remains
failed; the subsequent capture passed.

The host checker refuses stale boot IDs, missing/failed growth service results,
changed protected data and failed recovery checks. Its three host tests exercise
first/repeat acceptance and more than twenty rejection cases. Those tests
validate the evidence checker; they do not substitute for board observations.

Runtime rollback never shrinks root: restore the backed-up boot selection and
old system profile, then reboot. The previously tested U-Boot UMS flashing route
and the pinned recovery image remain the full-image fallback. Provision Wi-Fi
only through [the protected credential procedure](../../wifi-persistent-credential.md).
No routine whole-image readback was performed.

## First physical boot

[board-after.json](board-after.json) passes against the pre-boot capture with a
new boot ID and the exact selected system running. The boot service reported
`grown`: root expanded from 4,245,496 to 249,610,207 sectors without changing
its start or identity. Ext4 grew from 2,173,693,952 to 127,800,422,400 bytes.
`statvfs` reported 125,742,698,496 total usable filesystem bytes,
118,826,979,328 available bytes and 7,540,210 available inodes.

The service exited successfully; all protected hashes and the root sentinel
matched, shell and seatd were active, and Wi-Fi association plus HTTPS through
`wlan0` passed. Credential permissions remained root:root `0600`. The checker
captures the actual current-boot service journal record, rather than inferring
a resize from the resulting capacity alone.

[first-boot-selected.log](first-boot-selected.log) contains selected actual
serial kernel/service/login observations; [provenance](first-boot-provenance.json)
identifies the complete private transcript by its hash and command. Serial login
alone is not treated as growth completion. These observations prove a normal
system boot and recovery, not physical-finger input, a camera observation, RVV
execution or GPU/card-shell performance.

## Second physical boot

[board-repeat.json](board-repeat.json) passes with another new boot ID. The
service reported `no-change`; root boundaries and filesystem size were stable.
The firmware, MBR boot code, all eight boot files and sentinel still matched.
The selected system, shell, seatd, Wi-Fi association and HTTPS over `wlan0`
returned successfully. [Selected serial lines](repeat-boot-selected.log) and
[their provenance](repeat-boot-provenance.json) accompany the current-boot
journal result. No manual grow command was run on the physical board.

## Reproduce the evidence capture

Use `tools/check-root-growth.py --board` with the helper and system store paths
recorded by `image-build.json`. The checker holds `/tmp/k230-board.lock` across
its UART upload and capture. It never resizes or changes boot selection. Before
capture creates one public preservation sentinel; later captures only read it.

```sh
growth_helper=/nix/store/6sca423wcjlq1v9ynjpbv4ai48jf53l9-k230-root-growth
growth_system=/nix/store/gnr36q39hmy4pq7ipwac1r1rpfbyqxd4-nixos-system-nixos-26.11.20260919.20b1ddd
python3 tools/check-root-growth.py --board --phase before \
  --helper "$growth_helper" --target-system "$growth_system" \
  --recovery-image /path/to/preserved/recovery-image \
  --recovery-sha256 c510362955d208bc449fcb62f9d419e597c337e873512eb4f95e65c84b00f867 \
  --output NEW_EVIDENCE/board-before.json
# Reboot with serial capture; wait for the selected system and shell.
python3 tools/check-root-growth.py --board --phase after \
  --helper "$growth_helper" --target-system "$growth_system" \
  --before NEW_EVIDENCE/board-before.json --output NEW_EVIDENCE/board-after.json
# Reboot again with serial capture.
python3 tools/check-root-growth.py --board --phase repeat \
  --helper "$growth_helper" --target-system "$growth_system" \
  --before NEW_EVIDENCE/board-after.json --output NEW_EVIDENCE/board-repeat.json
```

A `before` capture deliberately refuses an already-expanded root. Repeating the
entire growth experiment requires a compact starting card; it must not be
simulated by shrinking the live filesystem or editing earlier proof. The checker
also refuses to overwrite a prior evidence file.
