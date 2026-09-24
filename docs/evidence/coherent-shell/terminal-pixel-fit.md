# Foot fills the available output in pixels

On 2026-09-24 the user reported an exposed wallpaper strip at the right edge.
The installed `aab74fb7` system (`25x0q5b2jxg4pgv53085xvszipsfzv5a`) reported
ordinary terminal client rectangles of 564×1224 on its 568×1232 output through
`swaymsg -rt get_tree`. Foot 1.28.0 defaults `resize-by-cells=yes` for floating
windows; its pinned source `doc/foot.ini.5.scd` explains that this rounds to
character-cell multiples. The coherent shell intentionally uses floating
ordinary apps, so its 100-ppt resize request was rounded down.

Source `2954ef07` adds `--override resize-by-cells=no` to the coherent shell's
managed Foot launcher. This covers fresh and already-selected theme generations
without mutating theme files or overriding video/dialog geometry.

```sh
nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel --max-jobs 1 --cores 4 --no-link --print-out-paths
```

PASS candidate `/nix/store/m6nsp8gwsxq2lbi0cr6dyrv0f76hcr09-nixos-system-nixos-26.11.20260919.20b1ddd`.
The wrapper change has not yet been installed in this record.

Under the coordinator's exclusive serial reservation, the existing board Foot
binary was invoked with the exact override and public temporary app ID:

```text
foot --override resize-by-cells=no --app-id k230-edge-check -e /run/current-system/sw/bin/sleep 120
```

The probe ran as the shell user in its home and existing Wayland session.
`python3 tools/console.py /dev/ttyACM0 --wait=3` collected `swaymsg -rt get_tree`;
the reviewed public geometry was:

```json
{"app_id":"k230-edge-check","rect":{"x":0,"y":0,"width":568,"height":832},"window_rect":{"x":0,"y":0,"width":568,"height":832}}
```

The keyboard occupied the other 400 pixels. This proves the live terminal can
fill the exact available width/height with the override. The temporary app was
closed by its exact app ID; existing terminals were preserved. Installed-wrapper
verification and the user's optical retry remain separate from this invocation.
