# System closure delta: Portfolio-only build vs. master

## Method

Per coordinator request: not `nix path-info -rS` (a single aggregate
query), but an independent per-path sum: `nix-store -q --requisites <path>`
enumerated, then `nix-store -q --size <path>` summed over every requisite.

```
for p in $(nix-store -q --requisites "$path"); do
  nix-store -q --size "$p"
done | awk '{s+=$1} END {print s}'
```

## Inputs compared

- **master baseline**: `origin/master` at `292ee81624fd131608dd546a3198a106e3d5169f`
  ("Research and propose HDMI output..."), the same `k230-coherent-shell`
  NixOS configuration, evaluated via
  `builtins.getFlake "git+file://<repo>?rev=292ee81624fd131608dd546a3198a106e3d5169f"`
  so no working-tree changes leak in. Store path
  `/nix/store/l44jarwkb9li8cdr9rph8grb1g0lqjxr-nixos-system-nixos-26.11.20260919.20b1ddd`
  was already fully built in this machine's shared store (0 derivations
  built on this run -- substituted entirely from local cache built by
  other concurrent work on this host).
- **Portfolio-only system**: this change's branch (`feat/files-app`,
  rebased onto the same master revision), `k230-coherent-shell` with
  `k230.shell.filesAppNautilus` at its default (`false`), built with
  `nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel --max-jobs 1 --cores 6 --no-link --print-out-paths`.
  Store path
  `/nix/store/jv44pdh4al448zfl7h33l87pl3n4wmbq-nixos-system-nixos-26.11.20260919.20b1ddd`.

## Result

| | requisite paths | summed size |
| --- | ---: | ---: |
| master baseline | 1041 | 3.196 GiB (3,432,123,872 bytes) |
| Portfolio-only system | 1114 | 3.576 GiB (3,840,008,000 bytes) |
| **delta** | **+73 net** | **+389.0 MiB / +0.380 GiB (+407,884,128 bytes)** |

The net path delta (+73) is smaller than the raw "new paths present"
count (97) because 24 paths were **superseded** (same conceptual
derivation, new hash, because the closure feeding them changed): `dbus-1`,
`etc`, `foot`'s wrapper, and this repo's own `k230-foot`,
`k230-handheld-desktop-entries`, `k230-launcher-action`, `k230-shell-rust`,
`k230-supervised-keyboard`, `k230-sway.conf`, `k230-touch-launcher`,
`xdg-terminal-exec`, `X-Restart-Triggers-dbus-broker`, `system-path`,
`system-units`, `user-units`, and five `unit-*.service` derivations. None
of those are new weight; they are the same small wrapper/unit derivations
this repo already had, rebuilt because `environment.systemPackages` (and
therefore `system-path`, and therefore everything that references it)
changed hash.

The 73 genuinely new packages (present in the new build, with no
same-named predecessor at all) are, almost entirely, **not
Portfolio-specific** -- they are GTK4's own default GStreamer media-backend
closure, forced the moment any GTK4 package enters this system, confirming
`design.md`'s "closure weight is intrinsic to GTK4 on this nixpkgs pin, not
something either app's choice changes" with an itemized list instead of an
estimate:

- **GTK4/libadwaita/Portfolio themselves**: `gtk4-riscv64-unknown-linux-gnu-4.22.4`,
  `libadwaita-riscv64-unknown-linux-gnu-1.9.3`,
  `portfolio-1.0.3-riscv64-unknown-linux-gnu`, `k230-portfolio` (this
  change's launcher wrapper).
- **GStreamer's default plugin set** (`gst-plugins-bad`) and its own
  hardware/codec integrations: `libdc1394`/`libraw1394` (FireWire camera),
  `libdvdnav`/`libdvdread`/`libdvdcss` (DVD), `gupnp`/`gupnp-igd` (UPnP),
  `webrtc-audio-processing`, `openh264`, `libnice`/`libsrtp` (WebRTC/ICE),
  `chromaprint`, `libmodplug`, `game-music-emu`, `soundtouch`, `libbs2b`,
  `rtmpdump`, `mjpegtools`, `libajantv2`, `vo-aacenc`, `gsm`, `flite`,
  `fluidsynth`+`freepats`+`wildmidi` (MIDI synthesis), `neon`, `zxing-cpp`,
  `zint`, `mailcap`.
- **GLib/GObject-Introspection dev closure**: `gobject-introspection`
  (+`-dev`, +`-wrapped` variants), `glib-*-dev`, `glibc-*-dev`,
  `libffi-*-dev`, `zlib-*-dev`, `libxmlb`, `libxslt`, `libfyaml`,
  `raptor2`, `popt`, `appstream`, `mpdecimal`, `readline`, `ncurses`,
  `gdbm`, `gettext`.
- **PyGObject stack** (Portfolio is a Python/PyGObject app):
  `python3.14-pygobject` (+`-dev`), `python3.14-pycairo`,
  `python3.14-mako`/`markdown`/`markupsafe`/`setuptools`,
  `python3-3.14.7`(+`-env`).
- **Search indexing**: `tinysparql` -- present even for Portfolio alone,
  because it is part of GTK4/GNOME's default media-backend build, not
  something Portfolio itself requests.
- `openexr`, `imath`, `openal-soft`, `libsoup`, `lrdf`, `gssdp`.

## What this does not measure

- Board RAM/RSS or launch time -- coordinator task, not this change's.
- Nautilus's own marginal cost -- see the "both apps" build and its own
  `closure-delta.md` companion once that finishes.
- Whether the GStreamer codec/hardware-integration stack above is ever
  actually exercised at runtime by Portfolio (it almost certainly is not;
  GTK4 links its default media backend unconditionally regardless of
  whether an app displays video).
