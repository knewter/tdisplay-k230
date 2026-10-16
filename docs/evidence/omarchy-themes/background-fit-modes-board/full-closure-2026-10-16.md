# Background chooser: full system closure (task 3.1)

Evidence class: a host build only.

```
nix build "git+file://$PWD?rev=64481159d84b3628f8d63b98db7586c5753797db#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel" \
  --max-jobs 1 --cores 4 --option substituters https://cache.nixos.org --fallback
```

- Source: master `64481159d84b3628f8d63b98db7586c5753797db`, which contains
  the fit-mode commits `681bd4d8` and `05f63ff3`.
- Result: `/nix/store/zjdyp4mvzlq48a5r5q7zcah57nzy44bh-nixos-system-nixos-26.11.20260919.20b1ddd`.
  `nix path-info -S` gives a closure size of 4014675488 bytes, 1183 paths.
- The same output path came from an earlier build at a docs-only-different
  revision, so the closure does not depend on the evidence files.

## Ordering

The task asks for this build *before* board time. It was run after the 3.2
and 3.4 board runs, which used the landscape HDMI boot files
(`kernelMainlineDrmShellLandscapeHdmiBootFiles`) built from the same source
commits (see `README.md`). This record shows that the full `k230-coherent-shell`
closure builds with those commits. It does not change what 3.2 and 3.4
observed.
