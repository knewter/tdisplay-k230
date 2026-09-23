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
Actual compositor captures using this correction remain pending. Conversion
adds CPU work; a speedup is not assumed.
