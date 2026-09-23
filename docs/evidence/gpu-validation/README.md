# Bounded GPU validation

The initial failure and corrected run were captured on the physical board on
2026-09-22 while the shell, seatd, and persistent Wi-Fi remained active.
Their service invocation IDs match before and after the corrected run.

- `initial-format-failure.txt`: the vendor `VG_LITE_RGB565` layout reversed
  red/blue relative to DRM/Pixman RGB565; exact checks failed as intended.
- `corrected-format-pass.txt`: source at `8850144`, executable
  `/nix/store/78mysi1vsrk7rzgikwggqkx87dpvjkim-k230-vglite-validation-riscv64-unknown-linux-gnu-0-1104236db4d1e47873bd68924f912747b820228c/bin/k230-vglite-validation`.
  Vendor `VG_LITE_BGR565` matches the DRM/Pixman memory layout. RGB565 sampled
  scale output, one premultiplied-alpha case, and a private DRM dumb-buffer
  export/import with a full CPU pixel check pass. The probe does not modeset.

The matched full-panel nearest-scale case measured 1.969 ms per GPU operation
with a finish, 1.876 ms batched, and 1.950 ms for Pixman. These single-run wall
times do not establish a useful speedup. A subsequent benchmark revision adds
three rounds of process-CPU time as well as wall time; its board results remain
pending. Broad RGBA fidelity and live compositor/scanout integration remain
unproven. Sway still uses Pixman.

The corrected transcript removes console command echo, prompts and ANSI
formatting; the marked command output is retained. Neither a passed private
buffer test nor an alpha sample proves general compositor compatibility.
