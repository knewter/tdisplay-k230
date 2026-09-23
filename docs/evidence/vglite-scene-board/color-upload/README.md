# Private-buffer source-format comparison

The diagnostic cross-build passed with `nix build .#k230-vglite-color-probe
--max-jobs 1 --cores 2 --no-link --print-out-paths`. On the unchanged board,
`timeout 15s /run/card-tools/vglite-color-probe` completed all 18 cases and
returned 3 (completed comparison with mismatches). `rgba-rgbx.json` retains its
structured output, exact artifact and source hash. No process held the GPU
device before the run; normal shell and seatd remained active afterwards.

Each case uses private 256x8 allocations, point sampling, blend NONE, and an
actual Pixman SRC conversion to RGB565 as reference. Rows include all 256
values of each channel, grayscale, mixed colors, the scene fixture's two
problem colors, and black/white. Three rounds rotate the gradients. Both RGBA
and RGBX upload formats produce 660 differing pixels out of 2,048 for every
round and each alpha byte (255, 128, 0). The first differing red input is 136:
Pixman yields red code 17, GPU code 16. Merely switching to RGBX does not fix
the mismatch, and changing the alpha byte does not change it.

The initial preflight refused to execute because `fuser` is not installed.
The successful run instead checked `/proc/*/fd` using the already-installed
Python. The executable transfer was verified on the board before running it.

This diagnoses private-buffer conversion only. It proves neither compositor
pixels nor general cache, scale, clip, service-access or performance acceptance.
No DRM node is opened by this probe, the shell stays on Pixman, and all existing
physical acceptance tasks remain open.


## Exact RGB565 upload result

The extended diagnostic adds `VG_LITE_BGR565` sources prepared by the same
Pixman SRC conversion. `rgb565.json` retains all 27 cases. Every RGB565-source
case matches exactly (nine cases, 18,432 pixels); the RGBA/RGBX negative controls
still produce their original 660 mismatches each. The process therefore still
returns 3, preserving those known failures rather than reporting an overall
pass. Shell and seatd remain active on the same boot.

This supports testing RGB565 preconversion in the opt-in renderer. It is not
yet proof of scaled/cropped compositor output or a rendering speedup.


## Opt-in renderer correction

The renderer now prequantizes its immutable RGBA snapshot to RGB565 when
uploading an already-eligible texture. Existing blend eligibility is unchanged:
NONE ignores source alpha at the RGB target; SRC_OVER is admitted only for
opaque content. Unsupported blending still replays the whole pass in Pixman.
The host test device now consumes actual 16-bit uploads, and the production
renderer is compared against pinned wlroots/Pixman across channel gradients,
source crops, scales, padded rows, metadata rejection and failure/quarantine.

`TMPDIR=/mnt/MediaVolume/home/jadams WLROOTS_SOURCE=/nix/store/r2zcb3d3dgmz09qjaqsy945inal2h41r-source VGLITE_SOURCE=/nix/store/pvpqrg3diyi9mcgmqjc0f80hpdmk699p-source/buildroot-overlay/package/vg_lite tools/test-vglite-renderer.sh`
passes with ASan/UBSan. `nix build .#shell-compositor-vglite --max-jobs 1
--cores 8 --no-link --print-out-paths` passes, producing
`/nix/store/rfqwba7pf9mcbwrkx2ypdaidy7bmwp0m-sway-1.12`.
Actual compositor results are recorded below. Conversion adds CPU work; a
speedup is not assumed.


## Corrected compositor captures

On 2026-09-23 at 19:01:46 UTC (GPU) and 19:03:03 UTC (forced Pixman), the
bounded root scene harness ran renderer source
`d46333f2b838a3440c9ee87ac05dd940cf153284` on the unchanged board. Both trials
completed successfully and restored the normal shell and seatd. Each observed
one Sway process and DRM RGB565 scanout with the same padded allocator.
`scene/scene-check.py` records the actual executable/client paths and invocation;
the two `scene/*/result.json` files retain artifacts, timestamps and recovery.

| Mode | GPU frames | Pixman replays | Recovery |
| --- | --- | --- | --- |
| RGB565 upload | 182 | 0 | Normal shell active |
| Forced Pixman, same allocator | 0 | 573 | Normal shell active |

`python3 docs/evidence/vglite-scene-board/color-upload/scene/analyze-palette.py`
passes without a tolerance: both captures per mode have exactly matching
parent and child palettes. The formerly differing bright colors now read
(33, 113, 181) and (231, 146, 33) in both modes. Root and independent child
counters advance in both. The coordinator visually inspected the two later
captures: both show the expected blue parent and orange child bands.

This resolves the observed palette discrepancy for this scene. Different
animation frames prevent a full-image equality claim. This is native capture
and synthetic-client evidence, not a camera or finger interaction test. Frame
totals still show fewer completions under GPU; startup/capture/animation
sequences differ, so this is not the matched performance benchmark. Scaling,
bounds, broader cache proof, normal-service access and all control routes still
need their named board evidence. No GPU task is marked complete by this sample.
