# Stage 1 splash DMA-request trial

Status: **source cross-build and direct installed-baseline artifact checks pass;
candidate installed with direct readback and a clean filmed warm-boot trial**.
Task4.1 is now complete for the qualified warm-boot proof in `final/README.md`.
Two candidate warm boots showed no earlier garbled-logo frame; cold boot and
second-card results remain unverified.

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

At the initial backup/calibration checkpoint no raw firmware write had occurred.
Normal services, executable hashes,
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

## Candidate build and installed-byte comparison

`build.json` records the successful `nix build .#stage1` invocation and SPL
size check. `artifact-inspection.json` verifies firmware SHA-256 and legacy
header/data CRCs, the unchanged environment/OpenSBI artifact references and
the exact installed OpenSBI boot-file hash. The candidate's SPL is identical
to both installed copies. The decompressed U-Boot binaries are both 765480
bytes: 30 bytes differ, consisting solely of the embedded build-output path
(29 bytes) and the intended instruction at byte offset35564:
`addi a4,zero,64` (`13070004`) becomes `addi a4,zero,79` (`1307f004`). After
normalizing only the exact single build-output path, the sole differing byte
is offset35566. The installed original is the physical backup, rather than
an assumed source baseline.

The initial comparison-build command selected its `.drv` file, not the output;
the attempted inspection correctly failed before deployment. An output build
was queued correctly, then cancelled while still waiting with no descendants:
the direct comparison above establishes the needed instruction change without
another rebuild. No successful baseline rebuild is claimed.

`deployment.json` records a once-only 385932-byte write at offset2097152 to
`/dev/mmcblk1`. Before writing, the driver required the saved boot ID/system,
partition start, every original boot-file hash and a direct4MiB read matching
the complete backup. After fsync, a separate `dd iflag=direct` read matched the
expected candidate bytes and every byte outside them. The remaining raw slot
tail, SPL, environment and partition table were untouched. The recovery backup
and exact slot-only restore command remain available on the board and host.
This receipt proves installation, not boot success or defect removal.

## First candidate warm boot: no earlier garbled-logo frame observed

A once-only normal SSH warm reboot at2026-10-21T01:08:33.860666Z returned
ordinary boot `327f8e02-899a-4637-aab0-4785c8aa732f`: current, booted and
persistent systems all remain p501, with the same kernel notes and Sway/Rust
executable hashes. Normal services, native Settings and landscape270°/
logical1232×568 were verified (`postboot-normal-controls.json`). This is SSH
runtime verification, not a new physical gesture acceptance. The bright
post-handoff camera image is the normal light Foot terminal; a private
read-only screencopy confirmed the terminal prompt.

The complete240s recording has7193frames/399970278rawbytes, no sequence gaps,
error flags, regressing/changing timestamps or incomplete summary. All camera
controls were restored. Post-boot direct readback matched the deployed first
4MiB hash `df7e9b6ab78879374cd0c2c503dd1a04ab5e6d0513cd30d7e09f9b13e495a5a4`;
every protected boot-file hash remained unchanged.

`candidate-boot.mp4` is a first3600frame/120s,640×480 nominal30fps viewing
proxy covering the reboot through the shell's first visible replacement.
`candidate-frames.jsonl.gz` contains the original metadata for all7193frames;
use those camera timestamps rather than proxy PTS. The full raw MJPEG stays
in protected host scratch, with its exact hash in `candidate-capture.json`.

The same selector used on the reproduced baseline found no score≥0.8 in the
interior dark-panel interval. Its highest score is0.553334 atframe1494,
camera49.800835s; the unmodified original JPEG and ±5frame neighbors are
committed. Visual inspection shows the logo intact in each. A full timeline
and interval-boundary frames were reviewed; persistent transitions at initial
panel lighting and takeover are distinct from transient garbled-logo frames.
The dark-panel criterion includes initial black and final replacement-black
frames, so its bounds are not asserted to be exact logo/compositor timestamps.
This is one successful filmed sample at30fps, not a guarantee about every
52Hz panel refresh or every future boot. No FIFO/underrun mechanism is proved.

At that checkpoint, task4.3's install/readback/warm-boot proof was complete and
task4.1 remained open:
this recording still lacks the final qualified ±0.1s kernel/video mapping.
The subsequent normal warm-boot film with contemporaneous host raw-clock sampling
and **post-handoff** optical calibration is now complete in `final/README.md`,
with a reviewed±75.244ms physical timing interval. No archive or cold-boot/second-card claim is made.

## Final closeout

`final/qualification-review.json` and `final/README.md` record the second clean
warm boot and completed timing/source/counter proof. Task4.1 and all11 tasks
are complete. The raw recorder's conservative false qualification flags remain
unchanged; only the later evidence review qualifies this measured recording.
The corrected bootloader remains installed with verified rollback backups.
