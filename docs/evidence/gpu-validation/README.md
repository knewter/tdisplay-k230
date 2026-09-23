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
times do not establish a useful speedup. The follow-up three-round process-CPU results are recorded below. Broad RGBA
fidelity and live compositor/scanout integration remain unproven. Sway still
uses Pixman.

The corrected transcript removes console command echo, prompts and ANSI
formatting; the marked command output is retained. Neither a passed private
buffer test nor an alpha sample proves general compositor compatibility.

## Three-round completion and integration decision

`cpu-timing-pass.txt` records the final four-subtest run on the same physical
board, source revision `576471b`. The optional package was rebuilt with
`nix build .#k230-vglite-validation --max-jobs 1 --cores 4 --no-link --print-out-paths`
and resolved to:

```
/nix/store/sd5qy0s03hzy8mqf507bi9zx586wrnxq-k230-vglite-validation-riscv64-unknown-linux-gnu-0-1104236db4d1e47873bd68924f912747b820228c
```

The source-built closure was transferred over the existing Wi-Fi link, its
export SHA256 checked, and imported into the running Nix store. It was not
added to the system closure. The board still ran system
`/nix/store/0sbdslp3na1y1bkjm30wdz24ivcn6rgd-nixos-system-nixos-26.11.20260919.20b1ddd`.
Boot ID was `4f33a8c4-5824-4998-913c-c1307defa6c5`; Linux had one online CPU.
There was no video player running. No reboot, service restart, display commit,
permission change, or image flash was performed.

The coordinator ran each `rgb565`, `alpha`, `dmabuf`, and `benchmark` mode with
`timeout --signal=TERM --kill-after=3s 25s <package>/bin/k230-vglite-validation "$mode" /dev/dri/card0`.
Every mode exited zero. The console records `systemctl is-active shell seatd
k230-wifi` and each unit's `InvocationID` before/after; all remain active with
identical IDs. The probe source calls only allocation, PRIME export, mapping,
and destruction DRM APIs: it does not request master, modeset, add a framebuffer,
or submit a plane/atomic update. The shell retained display ownership.

Median of three successive rounds, milliseconds per operation:

| Geometry | GPU finish wall | GPU finish process CPU | GPU batch wall | GPU batch process CPU | Pixman wall | Pixman process CPU |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 128x128 → 256x256 | 0.192292 | 0.031133 | 0.157448 | 0.004690 | 0.170406 | 0.163621 |
| 284x616 → 568x1232 | 1.968375 | 0.101825 | 1.882701 | 0.017740 | 1.781209 | 1.704792 |

Each GPU-finish round contains 20 operations; batched GPU and Pixman each
contain 200. Validation and warmups precede timing. Both implementations use
the same nonuniform quadrant pattern, RGB565 output, and nearest-neighbor 2x
transform. Sixteen boundary/corner samples match before timings are accepted.
The imported dumb-buffer test additionally checks every CPU-visible pixel.

The full-panel per-operation GPU path used about **94% less process CPU time**
while taking about **11% longer elapsed time** than Pixman. This is repeatable
CPU offload in this workload, not a frame-rate improvement. Process CPU time
excludes interrupt work and other processes. Repeated operations use private
warm buffers; these numbers omit application-buffer import/copy, general
texture operations, scanout synchronization and compositor integration costs.
Batched throughput does not describe per-frame interactive latency.

**Decision:** keep Pixman in the default shell and pursue a separate opt-in
renderer experiment. The CPU result justifies that experiment, but switching
renderers now is blocked by unproved compositor buffer import/cache/fence
ownership, general RGBA fidelity, complete renderer operations, and physical
scanout/regression/performance evidence. An exact premultiplied blend sample
is not a full alpha/color conformance suite. A successful private DRM-buffer
import is not proof of scanout or video zero-copy. The follow-up must test
these boundaries and retain a working Pixman fallback before any default
change. The bounded validation proposal itself is complete.
