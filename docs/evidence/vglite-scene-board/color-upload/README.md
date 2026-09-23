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
