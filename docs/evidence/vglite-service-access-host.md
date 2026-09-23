# Normal-service VG-Lite access: host evidence

2026-09-23 UTC, branch `apply/vglite-composition`, base
`e0dbcf6b1f213322571f604bb7d078998baa1276`. No board access, unit activation,
device open, or hardware GPU result was performed for this checkpoint.

## Narrow commands and observed results

```sh
VGLITE_SOURCE=/tmp/k230-sdk-vglite-src/buildroot-overlay/package/vg_lite \
  tools/test-vglite-access.sh
```

PASS with AddressSanitizer/UndefinedBehaviorSanitizer. The actual patched SDK
source is compiled against its pinned headers. Fake ioctl results allocate real
anonymous mappings; actual Linux fork/exec/fcntl/madvise/mincore verify private
fd revocation, CLOEXEC independently of atfork, exclusion of command/tessellation/
power/pixel mappings, and child exit 127 after mapping-protection failure.

The actual C client uses real Unix sockets and SCM_RIGHTS. Only server root
credentials are injected. Success, untrusted peer, bad reply, missing fd,
multiple fds, ancillary truncation, SDK adoption failure and unavailable socket
are exercised. Received descriptors are CLOEXEC, PR_GET_DUMPABLE is zero, and
`/proc/self/fd` counts verify cleanup after each case.

Seven Python broker tests PASS. Actual socket credentials, peer pidfds and
SCM_RIGHTS are used; systemd/proc metadata are fixtures. Tests cover every policy
field, same-UID wrong MainPID, changed MainPID, missing proc access, unavailable
Yama protection, malformed request, rejected device modes, repeat grant, and
socket transfer after its creator exits. They do not prove production root
service credentials or actual driver transfer.

```sh
WLROOTS_SOURCE=/nix/store/r2zcb3d3dgmz09qjaqsy945inal2h41r-source \
VGLITE_SOURCE=/tmp/k230-sdk-vglite-src/buildroot-overlay/package/vg_lite \
  tools/test-vglite-renderer.sh
```

PASS: production renderer vs pinned Pixman pixels plus recording/submission/
completion failure tests, ASan/UBSan. This test stubs the broker denial boundary;
real client transport is covered separately above. No hardware result inferred.

```sh
nix build .#shell-compositor-vglite-service --no-link --print-out-paths
```

PASS, cross-built optional wrapper and VG-Lite/renderer/Sway dependency chain:
`/nix/store/3rgdggbm2qds0g7x16zh9yyb4yshs1xd-sway`.
Built wrapper inspection confirms its final action is `exec` of the exact
unwrapped Sway named in broker policy with an existing session bus, preserving compositor MainPID.
The wrapper was not executed on the board.

Nix evaluation separately checks default renderer/option/broker absence and the
trial service user, executable, broker restrictions and socket ownership. The
normal default remains Pixman; trial runtime credentials and task 2.5 stay
**UNVERIFIED**, with source contract and operator gates documented in
`docs/research/vglite-service-access.md`.

Final built wrapper and evaluated broker both name:
`/nix/store/bn4kknllz69447c1m2w4lgd2xa4dkplk-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`. Exact path equality was asserted after inspection.

`openspec validate the-shell-trials-vglite-composition --strict` passed.
`./tools/blob-scan.py --no-vendor` passed (committed-tree scan).
