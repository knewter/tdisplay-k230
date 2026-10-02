# Explicit candidate selection: host proof, 2026-10-02

Task 5b.5 controller preparation was performed in
`/home/jadams/tmp/k230-mainline-root-path`, branch `audit/mainline-root-path`,
from `f950dafdc1df5271d23030983152d38987d7b257`. Owned paths are
`tools/mainline-drm-initrd-shell-trial.py`,
`tests/test_mainline_drm_initrd_shell_trial.py`, and this note. No board,
serial port, staging operation, reboot, or build slot was used.

The controller accepts `--bundle` and `--normal-report`. Existing invocations
retain the historical gf3 bundle and `after.json` defaults. The selected bundle's
`system` symlink determines the candidate system; the manifest and the sole
`init=` argument must select that exact system. Identities are passed through
the preparation and trial functions without changing the global defaults.
The minimal and optional survey command protocols are unchanged; no label or
clock mode was added.

Before importing serial or opening a board lock/session, preparation requires:

- Direct, existing, read-only `/nix/store` bundle and system directories, an
  explicit system symlink, and an executable system `init`.
- The exact five manifest load artifacts, positive integer sizes, valid hashes
  and CRCs, and nonoverlapping load intervals within the board's 1 GiB RAM.
  Each of the four bundle payloads must be a read-only regular file whose
  actual size, SHA-256 and CRC32 match its manifest record. The stage-one
  wrapper's identity remains anchored to the protected normal baseline.
- Nonempty, read-only regular registration, store-paths and SHA256SUMS metadata.
- A structured normal report matching the protected p1 system/profile, kernel,
  all eight committed boot-file sizes and hashes, three active services and a
  valid boot ID. Boot-file records retain the original `{bytes, sha256}` shape;
  a later report containing only flat digests is not accepted as a substitute.

Existing protected normal preflight/postflight and U-Boot size/CRC checks remain
in place. The printed U-Boot bootargs must be one complete matching assignment;
an echoed substring or duplicate assignment cannot satisfy that check.

## Host commands and results

The following checks passed on 2026-10-02 (UTC observation
`2026-10-02T15:58:18Z`), in the worktree above:

```sh
python3 -m unittest discover -s tests -p test_mainline_drm_initrd_shell_trial.py
python3 -m py_compile tools/mainline-drm-initrd-shell-trial.py tests/test_mainline_drm_initrd_shell_trial.py
openspec validate the-board-runs-a-mainline-kernel --strict
git diff --check
python3 tools/mainline-drm-initrd-shell-trial.py --help
```

The suite passed all 36 tests, retaining the previous 21 protocol tests. The 15
additional tests exercise changed candidate selection, CLI defaults and explicit
arguments, manifest/system mismatch, missing artifacts and metadata, unsafe
store selections, invalid sizes/hashes/CRCs, actual sparse-file overlap, malformed
bootargs, and normal-report identity failures. Negative trial tests assert that
neither the private serial session nor `os.open` is reached. Positive candidate
preparation uses a separate read-only test store without serial access or changes
to the historical BUNDLE/SYSTEM constants.

Pure preparation also succeeded against the actual historical immutable bundle
and committed manifest using the committed structured normal baseline:

```sh
python3 - <<'PY'
import importlib.util
from pathlib import Path
p = Path('tools/mainline-drm-initrd-shell-trial.py')
s = importlib.util.spec_from_file_location('initrd_trial', p)
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
v = m.prepare_trial(
    Path('docs/evidence/mainline-display/physical-2026-10-01/manifest.json'),
    m.BUNDLE, m.NORMAL_BASELINE,
)
assert v['system'] == m.SYSTEM
assert v['normal']['candidate_system'] == m.SYSTEM
print('PASS: exact historical immutable bundle, manifest, init, metadata, ranges and protected normal identities')
for name, _, address, _ in m.LOADS:
    size = v['manifest']['files'][name]['bytes']
    print(name, hex(int(address, 16)), hex(int(address, 16) + size), size)
PY
```

The bundle was
`/nix/store/gf3aqks2dg0z3ksz33ysfprnlbk83vw3-k230-mainline-drm-trial-boot-files`;
its resolved system was
`/nix/store/k9f4r2i9k9qj58z8z4l2kssy9rpwxxm1-nixos-system-nixos-26.11.20260919.20b1ddd`.
Verified sizes yielded these half-open load intervals:

| Artifact | Start | End | Bytes |
| --- | --- | --- | ---: |
| bootargs.txt | 0x7000000 | 0x70000d3 | 211 |
| fw_jump_add_uboot_head.bin | 0x8000000 | 0x80421d8 | 270808 |
| Image-mainline-drm | 0x200000 | 0x26bee00 | 38530560 |
| k230-tdisplay-mainline-drm.dtb | 0x8400000 | 0x8402b11 | 11025 |
| initrd.uimg | 0x9000000 | 0xaa0c7b1 | 27314097 |

## Remaining physical gate

UNVERIFIED: this preparation does not demonstrate serial reception, corrected
proc setup, reboot recovery, root mounting, root login, or behavior of a newly
built restart candidate. Task 5b.5 and the optional restart physical gate remain
open. Using the committed normal report in the pure host check proves schema
and pinned identities; it does not assert the board's current boot identity.

After the operator has reserved the board, reviewed a matching new immutable
bundle/manifest, and prepared a fresh structured protected normal report, the
existing bounded minimal protocol can be selected with this template (not run):

```sh
python3 tools/mainline-drm-initrd-shell-trial.py \
  --bundle /nix/store/EXACT_NEW_BUNDLE \
  --manifest /path/to/MATCHING_MANIFEST.json \
  --normal-report /path/to/STRUCTURED_PROTECTED_NORMAL.json \
  --mode minimal
```

The placeholder paths must be replaced with reviewed actual artifacts. Existing
reception retry limits, stage timeouts, stop-on-missing-marker behavior, private
log handling, and protected normal recovery checks remain applicable. A failed
marker is not root-cause evidence and does not authorize further probe input.
Review, merge and push remain with the coordinator; no physical claim is added.
