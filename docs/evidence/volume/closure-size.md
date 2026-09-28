# Closure-size delta: enabling PipeWire/WirePlumber/pipewire-pulse

Three `nix build .#nixosConfigurations.k230-coherent-shell.config.system.
build.toplevel --max-jobs 1 --cores 6 --no-link --print-out-paths` runs, all
against the same base revision, cross-compiled for `riscv64-unknown-linux-
gnu`, all in the foreground on this dev host (not the board):

1. **Before trimming** -- `nix/shell.nix`'s `pipewireLean`/`wireplumberLean`
   overrides not yet applied (plain `pkgs.pipewire`/`pkgs.wireplumber`
   everywhere): `/nix/store/gwl36r94h1vjh0038d0nm3c7ikzlgl6m-nixos-system-
   nixos-26.11.20260919.20b1ddd`.
2. **`pipewire` alone trimmed, `wireplumber` left stock** (an intermediate
   step, kept here because the result itself is the reason step 3 exists):
   `/nix/store/qcd1vqsip5ha0cdv3ag30qc8j7laxjzs-nixos-system-nixos-
   26.11.20260919.20b1ddd`.
3. **Both trimmed** (`wireplumberLean = pkgs.wireplumber.override { pipewire
   = pipewireLean; }`, design.md Decision 9's final form): `/nix/store/
   2yhpy7fg6l5hl0dij41si99xfw0spyj5-nixos-system-nixos-26.11.20260919.
   20b1ddd`.

## Method, and a real measurement pitfall found along the way

`nix path-info -rS <path>` (recursive, with sizes) is the obvious command,
but on this shared, heavily-concurrent-build store it reported wildly wrong
per-path sizes for at least one path directly checked here -- `nix path-info
-S` on a ~1.7 KB rendered `unit-pipewire.service` file reported **497361416**
bytes (~474 MiB). `du -sh` on the same path showed 8.0K, and `nix-store -q
--size` (the older, differently-implemented query) reported 2000 bytes,
matching reality. `nix store verify` on that path found no content
corruption, so this reads as a `path-info -S` reporting bug or a stale/
inconsistent size field in this local Nix database, not a bad store path.
**Every number in this file was therefore computed via `nix-store -qR
<path>` for the closure list, then summing `nix-store -q --size` over that
list** (a Python loop, not shell arithmetic on `path-info`'s own column),
not `path-info -rS`. Anyone re-deriving these numbers should use the same
method or independently cross-check `path-info`'s output the way this file's
own discovery of the discrepancy did, rather than trust it blindly on this
machine.

## Results

| Build | Closure paths | Closure bytes | Closure GiB |
| --- | --- | --- | --- |
| 1. Before trimming | 808 | 2,131,580,912 | 1.985 |
| 2. `pipewire` trimmed only | 809 | 2,144,112,440 | 1.997 |
| 3. Both trimmed | 809 | 2,144,112,440 | 1.997 |

**Build 2 is *larger* than build 1**, not smaller -- the opposite of what
disabling six optional PipeWire backends should do on its own. Investigated
directly rather than assumed: build 2's closure contains *two* full
`pipewire-riscv64-unknown-linux-gnu-1.6.8` packages side by side --
`3xi5pr6wi4j61qv7p6dfmzrlg75ljk6x` (the new, trimmed one, correctly
referenced by every `ExecStart`/`PATH` entry this change itself writes) and
`qj7jj4c9r1kybvsphi4s092sph4a6qf5` (the original, untrimmed one, still
present). The second one is pulled in by `wireplumber`: its own nixpkgs
`package.nix` takes `pipewire` as a plain override argument and links
against it directly (confirmed by reading
`pkgs/by-name/wi/wireplumber/package.nix` at the pinned `nixpkgs` revision),
and build 2's `nix/shell.nix` only overrode `pipewire` itself, leaving
`pkgs.wireplumber` -- and therefore its own `pipewire` build input -- at the
stock, untrimmed package. Two full copies of a similarly-sized package cost
more than the (much smaller, since `bluez`/`vulkan`/`libx11`/`roc-toolkit`/
`avahi`/`openssl` all remained reachable via other paths in this closure
regardless -- see below) savings the trimmed flags themselves produced.
Build 3 (`wireplumberLean = pkgs.wireplumber.override { pipewire =
pipewireLean; }`) exists specifically to close this gap by making
`wireplumber` link against the same trimmed package instead of a second,
separate one -- confirmed directly (`wireplumberLean`'s own store path no
longer references the untrimmed pipewire hash at all). **It made no
measurable difference to the total** (809 paths, 2,144,112,440 bytes,
identical to build 2): the untrimmed `qj7jj4c9r1kybvsphi4s092sph4a6qf5`
pipewire is *still* present in build 3's closure, now reached through a
third path this change does not own or control -- a NixOS/nixpkgs-internal
`all-plugins` aggregate (its own build inputs are `alsa-plugins` and the
stock `pipewire`, confirmed via `nix-store -q --references`), most likely
an ALSA-plugins-search-path aggregation nixpkgs assembles automatically once
any PipeWire package appears anywhere in the image -- traced two levels
deep (`alsa-plugins`'s own `pkgs/by-name/al/alsa-plugins/package.nix` at the
pinned revision takes no `pipewire` input at all, so `all-plugins` itself is
the NixOS-module-level aggregation point, not something either `pipewireLean`
or `wireplumberLean` feeds into or could redirect by overriding either
package). Fully eliminating this third reference would mean tracing which
NixOS module builds `all-plugins` and whether it can be told to use
`pipewireLean` instead, or accepting that this particular aggregate always
pulls in the stock package regardless of what any individual service unit
runs -- left open here as a specific, named follow-up rather than
declared solved.

**Net, honest conclusion**: this change's `pipewireLean`/`wireplumberLean`
overrides are real and correct (every service this change itself starts,
and the persistent `pw-cli`/`pw-dump` children `pipewire_ipc.rs` spawns,
run the trimmed package, not the stock one), but they produced **no
measured reduction in this board's actual system closure size**, because
of the two independent reasons above (shared dependencies already present
via `hardware.bluetooth.enable`, and a NixOS-internal ALSA-plugins
aggregate this change does not control). The closure grew by 12,531,528
bytes (~12.0 MiB) end to end, entirely accounted for by the duplicate-
pipewire-then-fixed-to-single-but-still-duplicate-via-a-third-path
situation above, not by anything in the Rust client or the systemd units
this change actually authors.

**Even accounting for the duplicate package, the disabled backends'*
own* dependencies (`bluez`, `vulkan-loader`/`vulkan-headers`, `libx11`,
`roc-toolkit`, `avahi`, `openssl`) show up an identical number of times
(6 each, `nix-store -qR <path> | grep -c` on both build 1 and build 2's
closures) whether or not `pipewire` itself asks for them -- they are already
reachable from elsewhere in this system regardless of this change**, most
directly `hardware.bluetooth.enable = true` (`nix/hardware.nix`, landed by
the separate, already-merged `the-handheld-talks-bluetooth` change) for
`bluez` specifically. This means the *only* thing `pipewireLean`'s six
disabled flags can honestly be credited with removing from this board's
actual image is whatever PipeWire-specific plugin/codec glue (the Bluetooth
A2DP codec libraries PipeWire itself needs for its own bluez5 backend --
`sbc`/`libfreeaptx`/`liblc3`/`ldacbt`/`fdk_aac`) is not already needed by
anything else in the closure -- real, but a materially smaller saving than
"disables Bluetooth/Vulkan/X11 support" first suggests on a board that
already has Bluetooth enabled for an unrelated reason. `ffmpeg`/`gstreamer`
support (the two backends nixpkgs 1.6.8 hardcodes on, not exposed as
override parameters -- design.md Decision 9) remain a real, unaddressed
cost either way; not quantified separately here beyond what the whole-
closure totals above already include.

## What this file does not establish

Every number here is a dev-host cross-build closure size, not an installed
SD-card image size (the SD image applies its own compression/layout on top)
and not a measurement of this board's actual flash usage. No board task in
`tasks.md` is ticked from this file alone.
