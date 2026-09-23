# Space preflight for the next board trial

The read-only board commands in `preflight.json` found a 127,934,660,608-byte
card with a 117,440,512-byte boot partition and a 2,173,693,952-byte root
partition. `/` had only 77,070,336 bytes available. The already-built RVV system
adds 16 paths / 112,720,944 NAR bytes relative to the current system closure,
so importing it without making room would be premature. The root filesystem
still has its compact image size; `nix/hardware.nix` currently declares ext4
by label without automatic partition/filesystem growth.

The audit also found 62 unrooted store paths. They have not been deleted:
unrooted diagnostics can still be needed for ongoing comparisons. Read-only
`--print-dead` is not a garbage-collection execution. No boot, partition,
filesystem, installed system or credential was changed. The normal shell was
active after the preceding GPU tests. Raw console transcripts remain private;
this selected report retains command provenance, timestamps and original hashes.

The proposed durable correction belongs to
`the-system-uses-the-card-space`. These observations prove the capacity gap,
not the proposed resize behavior. Existing card/GPU acceptance gates stay open.
