# Mainline DRM derivation build attempt

## Result

On 2026-09-29, the requested candidate outputs were not built. Both
attempts failed before Nix evaluated or realized a derivation; there are no
output paths and this is not build evidence. The complete output of the
retry is in `mainline-display-nix-build.log`.

The first invocation attempted to use the default Nix fetcher-lock directory
under `/home/jadams/.cache`, which is read-only in this execution environment:

```sh
flock /tmp/k230-nix-build.lock nix build \
  .#kernelMainlineDrm .#deviceTreeMainlineDrm .#kernelMainlineDrmBootFiles \
  --print-out-paths --max-jobs 2 --cores 4
```

It failed opening a fetcher lock file with `Read-only file system`. I then
redirected `XDG_CACHE_HOME` to this checkout's ignored `.scratch/nix-cache`
and retried under the same shared build lock:

```sh
mkdir -p .scratch/nix-cache
flock /tmp/k230-nix-build.lock bash -c \
  'XDG_CACHE_HOME="$PWD/.scratch/nix-cache" nix build \
   .#kernelMainlineDrm .#deviceTreeMainlineDrm .#kernelMainlineDrmBootFiles \
   --print-out-paths --max-jobs 2 --cores 4'
```

That passed the cache-directory step but failed connecting to
`/nix/var/nix/daemon-socket/socket` with `Operation not permitted`. The
shared lock was held for the attempt and released on exit. No board or serial
port was used. The derivation tasks remain unchecked; retry when the Nix
service is accessible from this execution environment.
