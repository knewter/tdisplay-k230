# Current-image ordinary-init physical comparison

Physical UART evidence, captured 2026-10-05 01:46:26–01:49:52 UTC with controller
revision `8982b4988d55a43839633ecb69752665677c91eb`. The 206.345-second
invocation includes preparation/loading; the passive login-readiness bound was
180 seconds. Exit 1 records **ordinary init login readiness unverified**.

Fresh protected recovery after the autonomous PID1 run passed exact normal
system/profile/kernel/init, a distinct boot, eight unchanged boot hashes,
three active shell services and registration absence. Its safe
[receipt](../../mainline-autonomous-bash-pid1/physical-2026-10-05/recovery.json)
precedes this run. Historical anchors did not replace that recovery.

Executed [host preparation](prepare-ordinary.py) and
[artifact qualification](artifact-host-result.json) checked the unchanged p2
bundle/24h kernel development output/0l4 source, config, Image, DT, archive,
manifest, loader and prior native parser receipt. Archived systemd `/init`
matches the selected system init digest. [Ordinary policy](ordinary-host-result.json)
retains 299 argument bytes / 317 literal command bytes, the sole console,
two existing masks, fsck skip and synchronous initramfs; no reporter, trace,
alternate PID1 or new build was selected. This is host proof only.

One board/UART reservation ran:

```sh
python3 tools/mainline-drm-system-trial.py begin \
  --wait-initramfs-in-initcall --without-boot-markers \
  --bundle /nix/store/p2kdar89q7dhwdajjy0mrhmxxzcgsalw-k230-mainline-drm-trial-boot-files \
  --manifest PRIVATE_MANIFEST --normal-report NEW_PRIVATE_NORMAL \
  --state NEW_PRIVATE_STATE --log NEW_PRIVATE_LOG --result NEW_PRIVATE_RESULT
```

Independent full private-transcript review passed all five exact load sizes and
CRCs, exact volatile arguments and fresh received kernel commandline. The
candidate showed systemd 261.2, completed coldplug, initrd root targets,
**Mounted /sysroot**, and **Starting Find NixOS closure**. No closure completion,
switch-root or login followed within the readiness bound. These status messages
do not establish a guarded mount, closure or usable stage-2 identity, nor locate
a blocked syscall. Chunked replay of the unchanged readiness parser returned
false. Reviewed command annotations and source show no candidate input after
`bootm`; this is not an independent electrical direction measurement.

[Fixed observations](fixed-observations.txt) are explicitly derived public facts,
not a raw transcript. [Result](result.json) preserves hashes of protected private
logs and their limits. A separately reserved camera photograph appeared dark
and reflective with no readable content; glare, focus and angle prevent any
claim that userspace or scanout was absent. The photograph remains private.

A subsequent NEW operator reset passed [protected normal recovery](recovery.json):
distinct boot, exact identities, eight matching boot hashes, three active
services and registration absence. No prior reset was reused, no fallback
command was sent and no automatic return is claimed.
Usable ordinary root, panel/glass acceptance, unmasked production boot and task
5b.5 remain **UNVERIFIED**. The next bounded comparison is
[fixed initrd manager logging](../../../research/mainline-initrd-debug-logging-2026-10-05.md).
