# Retaining unchanged cross-build dependencies

The [comparison](dependency-comparison.json) records identical lockfiles,
the same QEMU kernel output and unchanged ICU, systemd, NetworkManager and Samba
derivations between the first passing fixture source and the selected source.
Those sampled heavyweight dependencies were not invalidated by changed inputs.
Their previous outputs were absent locally. This is consistent with garbage
collection, but the available GC journal does not identify a deletion event;
the particular deletion mechanism remains unverified. A separate
[shared-host snapshot](host-build-contention.json) records load and storage
pressure during this build; it does not identify or modify other workloads.

An intermediate validity check found the systemd runtime output present while
its development, man and debug outputs were absent and its derivation was
rebuilding. The retention receipt preserves that snapshot. Retaining only a
runtime system leaves other outputs available for collection; restoring a
missing output can require rebuilding the same multi-output derivation.

The smoke helper realizes artifacts with `--no-link`. This host reports
`keep-derivations = true` and `keep-outputs = false`: retained recipes and
runtime system roots do not protect all build-only outputs. Nix documents this
distinction in its [keep-outputs setting](https://nix.dev/manual/nix/2.35/command-ref/conf-file.html#conf-keep-outputs).

The [retention receipt](build-retention.json) records registered durable roots
for the selected artifacts, all available outputs of both kernels, the built
board system, the unchanged normal mainline system, and a link farm referencing
all valid paths found in their derivations' build-input closures. The farm's
references were checked against every retained path. No missing output was
rebuilt just to retain it. The receipt preserves the command, actual completion
time, store identities, retained count and omitted unrealized count.

The roots are under
`/home/jadams/.local/state/tdisplay-k230/retained-builds/card-overview-2026-10-09/`.
Keep this directory and its registered symlinks to preserve the snapshot.
They retain development outputs, sources and host tools as well as runtime
dependencies. The private path list and `retain.nix` there allow inspection;
the committed evidence includes their receipt rather than thousands of paths.

This is a host-local cache retention snapshot. Genuine source, configuration
or input changes can still create new derivations that need building. It does
not change the global GC policy or provide deployment, board or guest proof.
