# Guarded exec-return candidate staging

Root staged the restored `5f2j…` bundle from revision `69d7cbb3`, using the
reviewed private operator wrapper `python3 PRIVATE_STAGE_GUARD` and the exact
eight-path delta export. [Receipt](result.json) binds the payload, wrapper,
command and complete private UART hashes. HTTP addresses/URLs, operator tokens
and runtime boot IDs remain private. This is physical UART staging proof.

Attempt1 failed before transfer: the preflight helper checks both normal state
and staged candidate, so checking the new candidate before installing it failed
the staged-system assertion. Source/log/failure remain preserved privately.
No complete preflight, staging command or reboot occurred in that attempt.

The reviewed correction uses existing p2 for the full before-stage guard and
new5f2 for the full after-stage guard. After a fresh root prompt and complete
protected preflight, an acknowledged JSON upload reconstructs the exact script
with each serial line under2000 bytes. The transfer checks the compressed NAR
SHA256, imports it, retains a separate candidate GC root, copies only trial
files/metadata, and verifies staged checksums. No normal profile or boot file
is replaced. One exact fresh-token RC0 frame after a renewed prompt is required
before postcheck; duplicate, partial, malformed and nonzero frames stop input.

Attempt2 returned0. Independent complete UART review PASS: unique ordered
before/result/after records, five upload ACKs, transfer archive plus four bundle
checksums, and completed new staged metadata/closure validation. The protected
normal identities/eight boot hashes/three active services/registration absence
are identical before and after on the same boot. The report was updated only
after success. Staging issued no reboot or bootm.

This does not prove candidate execution, ordinary root, automatic recovery,
display or glass interaction. Those remain **UNVERIFIED**. Root's separately
guarded ONE180-second physical capture is a distinct evidence class; a zero
exec return alone does not prove userspace ran or its output call returned.
