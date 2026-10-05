# PID1 return and first userspace syscall — actual host proof

Worktree `/home/jadams/tmp/k230-mainline-probe-integration`, branch
`integrate/mainline-probe-path`, base `ea54f9e0f367e04c8a8baba8d11a2f6c5ebb37b9`.
Root owns integration, build and evidence. All artifacts use frozen code revision
`a60b0eaee3a56631060f857e3e7fbb39dac1a911`; later commits change only planning/evidence. The exclusive
`/tmp/k230-nix-build.lock` covered the sequential source, kernel/dev, bundle and
system build. No UART, board staging, reboot, live preflight or deployment of
these artifacts occurred during these host checks.

[Full build receipt](build-result.json) records return0 and exact evaluated
outputs for every step: kernelMainlineInitExecTransition.src (2.10s); kernelMainlineInitExecTransition.dev (3145.00s); kernelMainlineInitExecTransitionTrialBootFiles (68.56s); toplevel-mainline-init-exec-transition (28.96s). Each output was retained with a persistent
indirect GC root. Full logs remain private with their hashes in the receipt.
Commands pin the Git revision and use max-jobs1/cores4. No failed build is
relabelled as successful.

Actual same-derivation new dev headers compiled the three selected patched
RISC-V sources with GCC15.3 and W=1. [Object receipt](new-header-object.json)
records all four source hashes, object/readelf hashes, exact installed and
post-compilation config/autoconf hashes and zero compiler warnings;
[compile log](new-header-compile.log) retains compiler/status output; the exact
command is in the object receipt.
[Section/reference inspection](new-header-sections.json) verifies four one-byte
runtime flags in ordinary `.sbss`, both witness helpers in `.text`, setup in
`.init.text`, and matching process/traps undefined-call relocations. Reference
proof does not establish instruction order; pinned sources and the separately
reviewed native site tests establish placement and consumption before output.

[Actual qualification command](qualification-command.json) returned0.
[Positive artifact receipt](positive-host-result.json) binds selected
source/kernel/dev/config/Image, unique compiled setup/format bytes, matching
bundle Image, SHA256SUMS, manifest size/hash/CRC loads, original hardware DT,
original system init and archived init/systemd/Bash/common-loader/helper bytes.
Its strict archive comparison permits only the byte/mode-identical module-tree
relocation. Host Python3.14 inspected the actual Zstandard archive.
Argument lengths are 299 →
323 → 351 bytes;
the complete literal command is 369 bytes.
Only the exact parent and transition gate tokens are added to the established
synchronous marker-free policy. The normal report is an historical host anchor,
not fresh board preflight or recovery.

The earlier implementation [publication receipt](implementation-publication.json)
verifies the exact landed revision and successful site deployment. Publication
of this host packet is a separate coordinator step.

Two independent actual-host reviews PASS. The source reviewer independently
rehashed the four pinned sources, confirmed config/autoconf equality, matched
actual object/readelf digests and re-ran readelf on the actual objects. The
controller reviewer independently re-prepared the saved packet byte-equal and
matched source/config/Image/init/archive/DT/checksum/manifest entries, the
351/369-byte arguments and transport, the frozen build receipt, retained roots
and these public receipts. Neither reviewer rebuilt or used UART. Physical records,
print-call return, userspace execution, ordinary root and physical glass remain
**UNVERIFIED**. Task5b.5 remains open. One guarded physical trial follows actual
host review and protected normal staging; no diagnostic record alone authorizes
input. Missing records do not identify an instruction or cause.
