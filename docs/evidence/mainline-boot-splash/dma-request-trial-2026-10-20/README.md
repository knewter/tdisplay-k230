# Stage 1 splash DMA-request trial

Status: **authorized source candidate; build and deployment pending**.
Task 4.1 remains open. This report does not claim the flicker is fixed.

The operator explicitly authorized extending the boot-splash change to test
`0x40` → `0x4f` in the existing RM69A10 OSD DMA-control write. Plan revision
`30dacf01` records the bounded scope and retains the ±0.1 s full-film gate.
The pinned vendor function sets bits 3:0 to `0xf`; it does not ground a claim
about a particular burst length. Existing source grounding and the reproduced
bad frame are in `../current-baseline-2026-10-20/board/README.md`.

## Protected backup and unchanged default

Under the exclusive board lease, SSH confirmed the accepted p501 system,
ordinary boot `3d59df47-0267-4ab3-8c1e-42a38ae4ae1e`, boot partition beginning
at sector 8192 and root at sector 262144 on `/dev/mmcblk1`. The first 4 MiB
were backed up on the board and copied to the host, with matching SHA-256
`b4bac2e8c8513d37a95b6ce0aac8efb3043c755ee5f36410256b9384f744367e`.
`backup-preflight.json` records the raw U-Boot slot (2 MiB offset, 1 MiB
limit) and exact restore command. Backups remain outside Git because the
region includes the saved environment. Firmware-header hashes were verified
for both matching SPL copies and U-Boot; the latter was decompressed for the
pending artifact comparison (`original-firmware-inspection.json`).

No raw firmware write has occurred. Normal services, executable hashes,
accepted system/kernel and landscape controls were checked after calibration.
The board lease was released while the build waits for the shared heavy lock.

## Optical timing experiment

`camera-calibration.json` and `camera-calibration-analysis.json` retain all
40 clock brackets and eight reversible brightness transitions (255 ↔ 32)
on the accepted system, including delayed SSH replies. The 960×720 MJPEG
recording has 533 frames, no sequence gaps/errors and a complete summary.
The panel's original brightness 255 and camera's original 640×480 YUYV/30 fps
and automatic controls were restored. Source recordings are hash-pinned in
`source-artifacts.json` and retained in protected host scratch.

The fixed central panel ROI (x350:600, y300:480) separates each transition
at the midpoint of the before/after median luminance. Direct host command
brackets alone give bounds as wide as 582 ms because some SSH replies were
delayed. Under a **constant raw/host offset over this short calibration**, all
40 software clock brackets intersect within 4.360 ms, and the largest mapped
last-old/first-new frame bound is 76.791 ms. No samples were discarded.
This checks the observed camera/panel path in this mode; it does not establish
the early kernel clock origin or qualify extrapolation across a reboot.
**Final boot/video timing remains UNVERIFIED.**

The adjacent scripts preserve the capture/analysis method; they require
protected SSH configuration and their raw scratch input directory. The first
analysis attempt hit a NumPy integer JSON-serialization error; converting the
selected frame index to a Python integer fixed it without recapturing or
changing raw evidence. This is a separate calibration, not a default boot
film or proof that the boot defect is removed.

The complete 533-frame calibration is also committed as
`camera-calibration.mp4` (640×480/nominal30fps viewing proxy), with the original
per-buffer sequence/clock/source/timestamp metadata in
`calibration-frames.jsonl.gz`. Use those original timestamps, not proxy PTS,
for timing calculations. Proxy encoding preserves the original camera orientation.
