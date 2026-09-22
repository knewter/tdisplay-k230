# Console option: paired evaluation and current image inspection

These host checks used source `828485dd4d01b3ca0a9ea9c40ab958414e58eac8`
with only documentation/evidence changes in the worktree. No implementation
or configuration was changed, and no image was flashed for these checks.

[Both-state evaluation](both-states.json) records successful toplevel
derivation evaluation for the canonical configuration (`panelConsole=true`)
and an `extendModules` override setting it to false. The equivalent
[evaluation command](evaluate.sh) can be run from the repository root.
Only the true state includes `console=tty0`. Both retain ordinary Sway
(`initialSplash=false`); the false state here is not the separately tested
initial-scene candidate.

The current canonical image was built successfully with:

```sh
nix build .#sdImage --out-link result-console-acceptance \
  --option max-jobs 1 --option cores 8 \
  --option substituters https://cache.nixos.org
```

[Build output](build.txt) records three packaging derivations. The
[read-only inspection](console-image.json), produced by
[inspect-image.py](inspect-image.py), reads the 112 MiB boot partition at
offset 4 MiB and verifies that `logo.xrgb` is absent, `console=tty0` is present,
and `init` names the evaluated current system. It records the full image
SHA-256 and size. This is host artifact inspection, not a flashed-card
readback or physical boot claim.

This fills the two-state evaluation and current console-image inspection
gaps in task 6.1. The module default is false, but `flake.nix` still explicitly
sets the canonical image to true. The change's required final default is
therefore not yet delivered. Task 6.1 stays open until that selection is
reconciled with the physical acceptance gates. Earlier splash-image asset
inspection remains in
[the preservation trial](../splash-preserve-trial/image-contents.txt);
the corrected initial-scene image has separate
[build and deployment evidence](../splash-initial-scene-ready/README.md).
