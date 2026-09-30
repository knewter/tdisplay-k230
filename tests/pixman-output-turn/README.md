# Pixman final output-turn render-pass probe

`pixman-output-turn-render-pass.c` drives the public wlroots render-pass API
with a real Pixman renderer and in-memory `wlr_buffer` implementations. It
compares ordinary texture transforms against normal-orientation scene draws
followed by `.output_transform` on pass submit. It does not create a Wayland
display, connect a socket, or require a board.

Build the patched pinned wlroots source first, with the rounded-clip patch,
quarter-turn patch, and their helper headers in place. Then compile and run
from the repository root, substituting the absolute wlroots source directory:

```sh
cc -std=c11 -D_POSIX_C_SOURCE=200809L -Wall -Wextra -Werror \
  -I/path/to/wlroots/include -I/path/to/wlroots/builddir/include \
  -I/usr/include/libdrm -I/usr/include/pixman-1 \
  tests/pixman-output-turn-render-pass.c \
  -L/path/to/wlroots/builddir -Wl,-rpath,/path/to/wlroots/builddir \
  -l:libwlroots-0.20.so -o /tmp/pixman-output-turn-render-pass
LD_LIBRARY_PATH=/path/to/wlroots/builddir /tmp/pixman-output-turn-render-pass
```

The probe covers both wl_output transform enums, ARGB8888 and RGB565 output,
asymmetric source corners, a scene rectangle, nearest and bilinear filtering,
full and cropped source boxes, scaling, and texture alpha. Nearest output must
match byte-for-byte over the complete 28×18 target; it also checks that the
source top-left corner lands at `(3,15)` for enum 90 and `(24,2)` for enum 270.
The scaled bilinear rows are diagnostic rather than exact gates because Pixman
fixed-point scaling differs slightly when the quarter turn moves from each
texture draw to the final output copy.

On the native host run against wlroots 0.20.2, Wayland 1.26.0, and Pixman
0.46.4, all four nearest combinations matched exactly. The whole-frame scaled
bilinear comparison found:

| Format | Transform | Case | Changed bytes | Max 8-bit channel delta |
| --- | ---: | --- | ---: | ---: |
| ARGB8888 | 90 | scaled | 7 / 2016 | 1 |
| ARGB8888 | 90 | cropped + alpha | 2 / 2016 | 1 |
| ARGB8888 | 270 | scaled | 7 / 2016 | 1 |
| ARGB8888 | 270 | cropped + alpha | 0 / 2016 | 0 |
| RGB565 | 90 | scaled | 3 / 1008 | 9 |
| RGB565 | 90 | cropped + alpha | 0 / 1008 | 0 |
| RGB565 | 270 | scaled | 1 / 1008 | 4 |
| RGB565 | 270 | cropped + alpha | 0 / 1008 | 0 |

RGB565 channel deltas are decoded from 5:6:5 and expanded to 8-bit before
comparison. These small-surface measurements demonstrate the API behavior;
they do not establish full-resolution bilinear equivalence or runtime scene
correctness.
