# RVV candidate identity contract

This directory describes host guard work for OpenSpec task 3.2. It contains no
candidate manifest or physical observation. The host tests below use temporary
files and mocked store-path validation; their PASS result is not board proof.

Both `tools/pixman-rvv-compare.py` and `tools/card-shell-rvv-benchmark.py`
require `--manifest` for every mode. The manifest is a JSON object with schema
`k230-rvv-candidate-v1`, exactly these absolute immutable store paths:

| Key | Meaning |
| --- | --- |
| `system` | Candidate NixOS toplevel directory |
| `kernel` | Kernel output directory containing `Image` |
| `context_probe` | Exact vector-context executable |
| `pixman_library` | Exact `libpixman-1.so` file |
| `pixel_probe` | Pixel-probe package directory |
| `card_package` | Card-shell package directory |
| `sway_executable` | Exact Sway executable |
| `normal_config` | Exact Sway configuration file |
| `client` | Exact card workload client executable |
| `python` | Exact board Python executable |

The required `sha256` object contains lowercase 64-character SHA-256 values
for `kernel_image` (`kernel/Image`), `context_probe`, `pixman_library`,
`pixel_probe` (`pixel_probe/bin/k230-pixman-rvv-pixel-probe`),
`sway_executable`, `normal_config`, `client`, and `python`. The producer must
fill these fields from the **completed candidate outputs**, not copy the old
trial identities. The validator rejects missing or extra fields, malformed
paths, absent files, differing hashes, and a `system/boot.json` whose kernel
or toplevel differs from the manifest. On the physical board it additionally
requires the exact `/run/current-system` target and model. The candidate
kernel hash binds an **artifact**, not the executing kernel: a one-time boot
loads `kernel/Image` from root while preserving the normal `/boot/Image`.
Reconcile the separate boot controller's candidate load record and boot ID
with physical evidence before claiming running-kernel provenance. The card
runner checks the Sway process executable,
dispatch policy, service cgroup, and exact mapped Pixman library. The pixel
runner checks the probe ELF's Pixman soname and unique immutable RUNPATH on
the host, then glibc's observed Pixman initialization path for every physical
run. It retains the context probe, RVV dispatch counters, scalar control,
192-case equality check, and deliberate corruption control.

The pixel host runner stages its own script, `rvv-candidate-identity.py`, and
the selected manifest using `tools/push-file.py`; the board command includes
the manifest and helper SHA-256 values and the returned report must echo
them with the fresh token. The card runner executes on the board, so its
operator must stage the helper **and the exact same manifest** alongside
`card-shell-rvv-benchmark.py`, `card-shell-board-session.py`,
`card-shell-acceptance.py`, and `card-shell-benchmark.py`. Omission fails
before a board workload. The operator records the manifest bytes/hash with
the resulting evidence; no example path here is a candidate identity.

Narrow host guard command (using the pinned already-present Pixman source):

```sh
PIXMAN_SOURCE_TAR=/nix/store/s2cifkjf074cwcim1p9lij646fi3p3zy-pixman-0.46.4.tar.gz \
  python3 tests/test_pixman_rvv_probe.py && \
  python3 tests/test_card_shell_rvv_benchmark.py
```

The first test also compiles and runs the patched Pixman hwprobe detector on
the host. The manifest tests exercise valid, missing, stale, unbound-kernel,
and mismatched-library cases; one mocked pixel host run checks that all
three required transfer files and the exact manifest hash reach its remote
command. A one-time boot test confirms the guard accepts a candidate running
system while the persistent `/boot/Image` remains old. Candidate image build,
QEMU boot, and physical proofs remain
separate OpenSpec tasks 3.1 and 3.3–3.6.
