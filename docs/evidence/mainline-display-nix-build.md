# Mainline DRM derivation build attempt

## Result

On 2026-09-29, the first two invocations in this checkout could not reach a
build: the default cache path was read-only, and a checkout-local cache still
hit `Operation not permitted` connecting to the Nix daemon. Those attempts
are recorded in `mainline-display-nix-build.log`.

The coordinator then ran the three requested outputs under the shared build
lock. The candidate kernel compiled through the final link, where vmlinux
failed because Canaan DSI referenced `drm_bridge_connector_init` while the
selected config omitted the helper object. The full captured output is in
`mainline-display-full-build-failure.log`; this was not a successful kernel
build and the boot-files output was not produced. The DTB derivation was
requested in the same command, but its output path was not printed, so its
build gate remains unchecked. Source review against the exact pinned Kconfig
and Makefile identified the missing `DRM_DISPLAY_HELPER` and
`DRM_BRIDGE_CONNECTOR` selects. They are now added, pending another build.

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
coordinator's later full-build attempt is described above. Kernel, device
Tree, and boot-files tasks remain unchecked until their requested derivations
complete successfully. No board or serial port was used.
